# Copyright (c) 2025
# Manuel Cherep <mcherep@mit.edu>
# Nikhil Singh <nikhil.u.singh@dartmouth.edu>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
This script generates all the data needed for the user study based on the
information in conf/config.yaml.
"""

import os
import dotenv
dotenv.load_dotenv()
import hydra
from hydra import compose, initialize_config_dir
from hydra.utils import get_original_cwd
from hydra.core.global_hydra import GlobalHydra
from omegaconf import OmegaConf, DictConfig
from abxlab.browser import ABxLabBrowserEnv
from abxlab.task import StaticPageTask
from tqdm import tqdm
import pandas as pd
import multiprocessing
import random
import glob
from scripts.page_utils import get_rating_for_product, get_price_for_product

def process_experiment(args):
    fname, cfg_dict, base_conf_path, base_url, output_dir, host_path = args
    exp_name = os.path.splitext(fname)[0]

    # Skip if already processed (check CSV instead of images)
    csv_path = os.path.join(output_dir, "study_data_all.csv")
    if os.path.exists(csv_path):
        existing_df = pd.read_csv(csv_path)
        if exp_name in existing_df["exp"].values:
            return None

    # Get cfg information
    GlobalHydra.instance().clear()
    with initialize_config_dir(config_dir=base_conf_path, version_base=None):
        exp_cfg = compose(
            config_name=f"{cfg_dict['study']['experiment_path']}/{exp_name}",
            overrides=[f"+env.wa_shopping_url={cfg_dict['env']['wa_shopping_url']}"]
        )

    start_urls = [url.replace("${env.wa_shopping_url}", base_url)
                  for url in exp_cfg.task.config.start_urls]

    if len(start_urls) <= 1:
        return None

    task = {}
    for idx, url in enumerate(start_urls):
        name = f"{exp_name}_{idx}"

        # Simulate environment
        env = ABxLabBrowserEnv(
            task_entrypoint=StaticPageTask,
            task_kwargs={
                "url": url,
                "config": exp_cfg.task.config
            },
            headless=True,
        )
        env.reset()

        # Save screenshot
        env.page.screenshot(
            path=os.path.join(output_dir, f"{name}.png"),
            full_page=True,
            clip={
                "x": 0,
                "y": 250,
                "width": 1280,
                "height": 900
            },
            scale="device"
        )

        env.browser.close()
        del env

        task[f"image_{idx}"] = os.path.join(host_path, f"{name}.png")
        task[f"url_{idx}"] = url

    task["exp"] = exp_name
    choices = exp_cfg.task.config.choices
    if choices:
        task["nudge"] = choices[0].nudge
        task["intervention"] = choices[0].functions[0].args.value
        choice_url = choices[0].url.replace("${env.wa_shopping_url}", base_url)
        if choice_url == task["url_0"]:
            task["nudge_index"] = 0
        elif choice_url == task["url_1"]:
            task["nudge_index"] = 1
    else:
        task["nudge"] = None
        task["intervention"] = None
        task["nudge_index"] = -1

    return task

def add_extra_metadata(df, products_csv_path):
    """Add rating, price, and category information from products.csv"""
    # Load products data
    products_df = pd.read_csv(products_csv_path)

    # Create lookup dictionaries for faster matching
    product_lookup = products_df.set_index('product_url').to_dict('index')

    # Add metadata for url_0
    df["rating_0"] = df["url_0"].map(lambda url: product_lookup.get(url, {}).get('rating', None))
    df["price_0"] = df["url_0"].map(lambda url: product_lookup.get(url, {}).get('price', None))

    # Add metadata for url_1
    df["rating_1"] = df["url_1"].map(lambda url: product_lookup.get(url, {}).get('rating', None))
    df["price_1"] = df["url_1"].map(lambda url: product_lookup.get(url, {}).get('price', None))

    # Add category (same for both URLs in a pair, so use url_0)
    df["category"] = df["url_0"].map(lambda url: product_lookup.get(url, {}).get('category', None))

    return df

def generate_survey_data(df, seed, output_dir):
    """Generate partitions of the study data with full coverage and randomization"""
    random.seed(seed)

    # Group by unique URL pairs
    df_grouped = df.groupby(["url_0", "url_1"])
    unique_pairs = list(df_grouped.groups.keys())
    num_pairs = len(unique_pairs)

    # Calculate number of participant groups
    total_rows = len(df)
    num_groups = total_rows // num_pairs

    # Create a matrix where each row is a participant and each column is a pair
    # We'll fill this with condition indices to ensure full coverage
    assignment_matrix = []

    # For each pair, get all available conditions and shuffle them
    pair_conditions = {}
    for pair, group in df_grouped:
        conditions = group.reset_index(drop=True)
        # Shuffle the conditions for this pair
        shuffled_indices = list(range(len(conditions)))
        random.shuffle(shuffled_indices)
        pair_conditions[pair] = {
            "data": conditions,
            "shuffled_indices": shuffled_indices
        }

    # Assign conditions to participants
    for participant_idx in range(num_groups):
        participant_data = []

        for pair in unique_pairs:
            # Get the condition for this participant and pair
            condition_idx = pair_conditions[pair]["shuffled_indices"][participant_idx]
            condition_row = pair_conditions[pair]["data"].iloc[condition_idx]
            participant_data.append(condition_row.to_dict())

        assignment_matrix.append(participant_data)

    # Save each participant's data to a separate CSV
    for i, participant_data in enumerate(assignment_matrix):
        filename = os.path.join(output_dir, f"study_data_{i+1}.csv")
        pd.DataFrame(participant_data).to_csv(filename, index=False)

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg: DictConfig):
    host_path = cfg.study.host
    base_conf_path = os.path.join(get_original_cwd(), "conf")
    experiment_path = os.path.join(base_conf_path, cfg.study.experiment_path)
    base_url = os.getenv("SHOPPING")
    output_dir = cfg.study.output_dir
    products_csv_path = cfg.study.products_csv
    os.makedirs(output_dir, exist_ok=True)

    # Setup CSV file
    csv_path = os.path.join(output_dir, "study_data_all.csv")

    # Prepare arguments for multiprocessing
    cfg_dict = OmegaConf.to_container(cfg, resolve=False)
    fnames = [f for f in os.listdir(experiment_path) if f.endswith(".yaml")]
    args = [(fname, cfg_dict, base_conf_path, base_url, output_dir, host_path) for fname in fnames]

    # Use multiprocessing to process experiments
    with multiprocessing.Pool(processes=cfg.study.n_workers) as pool:
        for result in tqdm(pool.imap_unordered(process_experiment, args), total=len(args)):
            if result is not None:
                pd.DataFrame([result]).to_csv(csv_path, mode='a', header=not os.path.exists(csv_path), index=False)

    # Include extra metadata info and save it
    df = pd.read_csv(csv_path)
    df = add_extra_metadata(df, products_csv_path)
    df.to_csv(csv_path, index=False)

    # Generate survey data
    generate_survey_data(df, cfg.study.seed, output_dir)

if __name__ == "__main__":
    main()
