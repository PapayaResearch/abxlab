import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import time
import argparse
import ast
import logging
import glob
import functools
import multiprocessing
import threading
import json
import yaml
import dotenv
import pandas
import pickle
import hashlib
import browsergym
import agentlab
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, TimeoutError, as_completed
from tqdm.auto import tqdm
from bs4 import BeautifulSoup
from page_utils import compress_html
from typing import Optional, Any


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_root", type=str, required=True)
    parser.add_argument("--output_csv", type=str, default="aggregated_results.csv")
    parser.add_argument("--num_workers", type=int, default=min(os.cpu_count(), 16))
    parser.add_argument("--use_threading", action="store_true")
    parser.add_argument("--cache_dir", type=str, default=".cache")
    parser.add_argument("--skip_cache", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--force_sequential", action="store_true", help="Force sequential processing for debugging")
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

    dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env"))

    results_dir = os.path.abspath(args.results_root)
    cache_dir = os.path.abspath(args.cache_dir)
    os.makedirs(cache_dir, exist_ok=True)

    # Find all experiment dirs
    summary_files = glob.glob(os.path.join(results_dir, "**", "*", "summary_info.json"), recursive=True)

    experiment_dirs = []
    for file in tqdm(summary_files, desc="Filtering valid experiments"):
        with open(file) as json_file:
            try:
                d = json.load(json_file)
                err_msg = d.get("err_msg")
                stack_trace = d.get("stack_trace")
                if err_msg is None and stack_trace is None:
                    exp_dir = os.path.dirname(os.path.dirname(file))
                    experiment_dirs.append(exp_dir)
            except Exception as error:
                logging.warning("Error with %s: %s" % (file, error))

    logging.info(f"Found {len(experiment_dirs)} experiment directories to process.")

    if not experiment_dirs:
        logging.info("No experiment directories found.")
        return

    # Process experiments
    if args.force_sequential:
        logging.info("Using sequential processing for debugging")
        all_normalized_dfs = process_sequentially(experiment_dirs, cache_dir, args.skip_cache)
    elif args.use_threading:
        logging.info(f"Using threading with {args.num_workers} workers")
        all_normalized_dfs = process_with_threading(experiment_dirs, cache_dir, args.num_workers, args.skip_cache)
    else:
        logging.info(f"Using multiprocessing with {args.num_workers} workers")
        all_normalized_dfs = process_with_multiprocessing(experiment_dirs, cache_dir, args.num_workers, args.skip_cache)

    logging.info("Concatenating dataframes")
    df = pandas.concat(all_normalized_dfs, ignore_index=True)

    logging.info("Writing output")
    output_csv_path = os.path.abspath(args.output_csv)
    df.to_csv(output_csv_path, index=False)
    logging.info(f"Saved aggregated results to {output_csv_path}")


def process_with_threading(
    experiment_dirs: list[str],
    cache_dir: str,
    num_workers: int,
    skip_cache: bool,
    timeout: float = 10
) -> list[pandas.DataFrame]:
    all_normalized_dfs = []

    # Use a thread-safe lock (for the cache operations)
    cache_lock = threading.Lock()

    def process_with_lock(exp_dir: str) -> pandas.DataFrame:
        return process_experiment_dir_to_df_cached_threadsafe(
            exp_dir,
            cache_dir,
            skip_cache,
            cache_lock
        )

    completed_count = 0
    total_count = len(experiment_dirs)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks upfront
        future_to_dir = {
            executor.submit(process_with_lock, exp_dir): exp_dir
            for exp_dir in experiment_dirs
        }

        # Use as_completed with explicit timeout handling
        for future in as_completed(future_to_dir, timeout=timeout):
            exp_dir = future_to_dir[future]
            completed_count += 1

            try:
                # Individual task timeout
                df_part = future.result(timeout=timeout)
                if not df_part.empty:
                    all_normalized_dfs.append(df_part)

                # Manual progress update since tqdm can hang
                if completed_count % 10 == 0 or completed_count == total_count:
                    logging.info(f"Completed {completed_count}/{total_count} experiments")
            except TimeoutError:
                logging.error(f"Processing {exp_dir} timed out after {timeout} seconds")
                future.cancel()
            except Exception as error:
                logging.error(f"Error processing {exp_dir}: {error}")

    logging.info(f"Threading completed: {len(all_normalized_dfs)}/{total_count} successful")
    return all_normalized_dfs


def process_with_multiprocessing(
    experiment_dirs: list,
    cache_dir: str,
    num_workers: int,
    skip_cache: bool,
    timeout: float = 10
) -> list[pandas.DataFrame]:
    all_normalized_dfs = []

    # Worker function
    process_func = functools.partial(
        process_experiment_dir_to_df_cached,
        cache_dir=cache_dir,
        skip_cache=skip_cache
    )

    total_count = len(experiment_dirs)
    pbar = tqdm(total=total_count, desc="Processing experiments")

    # Force spawn to avoid pickle issues
    ctx = multiprocessing.get_context("spawn")

    with ProcessPoolExecutor(max_workers=num_workers, mp_context=ctx) as executor:
        # Submit all tasks upfront
        future_to_dir = {
            executor.submit(process_func, exp_dir): exp_dir
            for exp_dir in experiment_dirs
        }

        # Process results with per-task timeout
        for future in as_completed(future_to_dir.keys()):
            exp_dir = future_to_dir[future]
            try:
                # Apply timeout per individual task
                df_part = future.result(timeout=timeout)
                if not df_part.empty:
                    all_normalized_dfs.append(df_part)
            except TimeoutError:
                logging.error(f"Task for {exp_dir} timed out after {timeout} seconds")
            except Exception as error:
                logging.error(f"Error processing {exp_dir}: {error}")

            pbar.update(1)

    pbar.close()
    logging.info(f"Multiprocessing completed: {len(all_normalized_dfs)}/{total_count} successful")
    return all_normalized_dfs


def process_sequentially(
    experiment_dirs: list,
    cache_dir: str,
    skip_cache: bool
) -> list[pandas.DataFrame]:
    all_normalized_dfs = []

    for i, exp_dir in tqdm(enumerate(experiment_dirs), desc="Processing experiments", total=len(experiment_dirs)):
        try:
            df_part = process_experiment_dir_to_df_cached(exp_dir, cache_dir, skip_cache)
            if not df_part.empty:
                all_normalized_dfs.append(df_part)

        except Exception as error:
            logging.error(f"Sequential error processing {exp_dir}: {error}")

    return all_normalized_dfs


def get_experiment_hash(experiment_dir_path: str) -> str:
    exp_name = os.path.basename(experiment_dir_path)
    key_files = ["config.yaml", "nudge_metadata.yaml", "study.pkl.gz"]
    file_info = []

    for key_file in key_files:
        file_path = os.path.join(experiment_dir_path, key_file)
        if os.path.exists(file_path):
            file_info.append(f"{key_file}:{os.path.getmtime(file_path)}")

    step_files = glob.glob(os.path.join(experiment_dir_path, "*/step_*.pkl.gz"))
    if step_files:
        latest_step_mtime = max(os.path.getmtime(f) for f in step_files)
        file_info.append(f"steps:{len(step_files)}:{latest_step_mtime}")

    hash_string = f"{exp_name}:{"|".join(file_info)}"
    return hashlib.md5(hash_string.encode()).hexdigest()


def load_cached_result(experiment_dir_path: str, cache_dir: str) -> Optional[pandas.DataFrame]:
    exp_hash = get_experiment_hash(experiment_dir_path)
    cache_file = os.path.join(cache_dir, f"{exp_hash}.pkl")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception as error:
            logging.warning(f"Failed to load cache for {experiment_dir_path}: {error}")
    return None


def save_cached_result(experiment_dir_path: str, cache_dir: str, df: pandas.DataFrame):
    """Save result to cache."""
    exp_hash = get_experiment_hash(experiment_dir_path)
    cache_file = os.path.join(cache_dir, f"{exp_hash}.pkl")

    try:
        with open(cache_file, "wb") as f:
            pickle.dump(df, f)
    except Exception as error:
        logging.warning(f"Failed to save cache for {experiment_dir_path}: {error}")


def process_experiment_dir_to_df_cached(experiment_dir_path: str, cache_dir: str, skip_cache: bool = False) -> pandas.DataFrame:
    """Process experiment directory with caching support."""
    if not skip_cache:
        cached_result = load_cached_result(experiment_dir_path, cache_dir)
        if cached_result is not None:
            return cached_result

    try:
        experiment_data_dict = collect_results_for_experiment(experiment_dir_path)
        df = pandas.json_normalize(experiment_data_dict)

        if not skip_cache:
            save_cached_result(experiment_dir_path, cache_dir, df)

        return df
    except Exception as error:
        logging.error(f"Error processing {experiment_dir_path}: {error}")
        return pandas.DataFrame()

def process_experiment_dir_to_df_cached_threadsafe(
    experiment_dir_path: str,
    cache_dir: str,
    skip_cache: bool,
    cache_lock: threading.Lock
) -> pandas.DataFrame:
    """Thread-safe cached processing function."""

    if not skip_cache:
        with cache_lock:
            cached_result = load_cached_result(experiment_dir_path, cache_dir)
            if cached_result is not None:
                return cached_result

    experiment_data_dict = collect_results_for_experiment(experiment_dir_path)
    df = pandas.json_normalize(experiment_data_dict)

    if not skip_cache:
        with cache_lock:
            save_cached_result(experiment_dir_path, cache_dir, df)

    return df


def collect_results_for_experiment(results_dir: str) -> dict:
    step_pickle_files = sorted(glob.glob(os.path.join(results_dir, "*/step_*.pkl.gz")))
    steps_info = [get_info_for_step(pandas.read_pickle(step_file)) for step_file in step_pickle_files]

    study_path = os.path.join(results_dir, "study.pkl.gz")
    study_object = pandas.read_pickle(study_path)
    study_info = get_info_from_study(study_object)

    cfg_file = os.path.join(results_dir, "config.yaml")
    with open(cfg_file) as yaml_file:
        cfg = yaml.safe_load(yaml_file)

    nudge_file = os.path.join(results_dir, "nudge_metadata.yaml")
    with open(nudge_file) as yaml_file:
        nudge_metadata_loaded = yaml.safe_load(yaml_file)

    nudge_metadata = nudge_metadata_loaded[0] if isinstance(nudge_metadata_loaded, list) and len(nudge_metadata_loaded) > 0 else {}
    if not isinstance(nudge_metadata, dict) and isinstance(nudge_metadata_loaded, dict):
        nudge_metadata = nudge_metadata_loaded


    summary_file_paths = glob.glob(os.path.join(results_dir, "*/summary_info.json"))
    summary_file_to_load = summary_file_paths[0]
    with open(summary_file_to_load) as json_file:
        summary_info = json.load(json_file)

    experiment_id = os.path.basename(results_dir)

    data_dict = {
        "experiment_id": experiment_id,
        "uuid": study_object.uuid.hex if hasattr(study_object, "uuid") else None,
        "benchmark": study_object.benchmark.to_dict() if hasattr(study_object, "benchmark") and study_object.benchmark else None,
        "study": study_info,
        "cfg": cfg,
        "nudge": nudge_metadata,
        "summary": summary_info,
        **{
            "step_%d" % i: step_info for i, step_info in enumerate(steps_info)
        },
        "final_step": steps_info[-1] if len(steps_info) > 0 else None # Renamed
    }
    return data_dict


def parse_action(call_string: Optional[str]) -> Optional[dict]:
    if call_string is None:
        return None

    parsed_ast = ast.parse(call_string)
    try:
        call_node = parsed_ast.body[0].value
    except:
        logging.error("Failed to parse action call string: %s" % call_string)
        return {
            "name": call_string,
            "args": None
        }

    function_name = call_node.func.id

    arguments = []
    for arg_node in call_node.args:
        if isinstance(arg_node, ast.Constant):
            arguments.append(arg_node.value)

    return {"name": function_name, "args": arguments}


def get_info_for_step(step: Any) -> dict:
    pruned_html = step.obs["pruned_html"]
    soup = BeautifulSoup(pruned_html, "html.parser")
    action = None
    try:
        action = parse_action(step.obs.get("last_action"))
    except Exception as error:
        print("Error parsing action: %s" % error)
        action = None

    elem = None
    if action is not None and action.get("args"):
        try:
            elem = soup.select_one("[bid=\"%s\"]" % action["args"][0])
        except:
            print("Error selecting element with bid: %s" % action["args"][0])
            elem = None

    elem_info = None
    if elem is not None:
        elem_info = {
            "name": elem.name,
            "attrs": elem.attrs,
            "text": elem.text
        }

    url = step.obs["url"]
    focused_bid = step.obs["focused_element_bid"]

    return {
        "url": url,
        "focused_bid": focused_bid,
        "action": action,
        "elem_info": elem_info,
        "pruned_html": compress_html(pruned_html)
    }


def get_info_from_study(study: Any) -> dict:
    return {
        "task_name": study.exp_args_list[0].env_args.task_name,
        "agent_name": study.exp_args_list[0].agent_args.agent_name,
        "chat_model_args": study.exp_args_list[0].agent_args.chat_model_args.__dict__
    }


if __name__ == "__main__":
    main()
