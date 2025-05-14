import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import argparse
import ast
import logging
import glob
import multiprocessing
import json
import yaml
import dotenv
import pandas
import agentlab
from tqdm.auto import tqdm
from bs4 import BeautifulSoup
from typing import Optional, Any


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results_root",
        type=str,
        required=True,
        help="Root directory containing multiple experiment result folders."
    )
    parser.add_argument(
        "--output_csv",
        type=str,
        default="aggregated_results.csv",
        help="Path to save the aggregated CSV file."
    )
    parser.add_argument(
        "--num_processes",
        type=int,
        default=min(os.cpu_count(), 32),
        help="Number of processes for multiprocessing."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging."
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )

    dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env"))

    results_dir = os.path.abspath(args.results_root)

    summary_files = glob.glob(
        os.path.join(
            results_dir,
            "**",
            "*",
            "summary_info.json"
        ),
        recursive=True
    )

    experiment_dirs = []
    for file in tqdm(summary_files):
        with open(file) as json_file:
            d = json.load(json_file)
            err_msg = d.get("err_msg")
            stack_trace = d.get("stack_trace")
            if err_msg is not None or stack_trace is not None:
                continue
            exp_dir = os.path.dirname(os.path.dirname(file))
            experiment_dirs.append(exp_dir)

    logging.info(f"Found {len(experiment_dirs)} experiment directories to process.")
    if not len(experiment_dirs):
        logging.info("No experiment directories found.")
        return

    all_normalized_dfs = []
    with multiprocessing.Pool(processes=args.num_processes) as pool:
        results_iter = pool.imap_unordered(process_experiment_dir_to_df, experiment_dirs)
        for df_part in tqdm(results_iter, total=len(experiment_dirs)):
            if not df_part.empty:
                all_normalized_dfs.append(df_part)

    df = pandas.concat(all_normalized_dfs, ignore_index=True)

    output_csv_path = os.path.abspath(args.output_csv)
    df.to_csv(output_csv_path, index=False)


def process_experiment_dir_to_df(experiment_dir_path: str) -> pandas.DataFrame:
    experiment_data_dict = collect_results_for_experiment(experiment_dir_path)
    return pandas.json_normalize(experiment_data_dict)


def parse_action(call_string: Optional[str]) -> Optional[dict]:
    if call_string is None:
        return None

    parsed_ast = ast.parse(call_string)
    call_node = parsed_ast.body[0].value

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
        "elem_info": elem_info
    }

def get_info_from_study(study: Any) -> dict:
    return {
        "task_name": study.exp_args_list[0].env_args.task_name,
        "agent_name": study.exp_args_list[0].agent_args.agent_name,
        "chat_model_args": study.exp_args_list[0].agent_args.chat_model_args.__dict__
    }


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


if __name__ == "__main__":
    main()
