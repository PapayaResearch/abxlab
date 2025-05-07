# Copyright (c) 2025
# Manuel Cherep <mcherep@mit.edu>

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

import os
import argparse
import string
import yaml
import pandas as pd
import numpy as np
import itertools
from tqdm import tqdm

N_REPEATS = 6
N_SUBSAMPLE = 1000
SEED = 42
EXP_DIR = "conf/experiment"

def main():
    parser = argparse.ArgumentParser(description="Generates all experiment configs.")
    parser.add_argument(
        "--n-repeats",
        type=int,
        default=N_REPEATS,
        help="Number of repetitions for category and home tasks"
    )

    parser.add_argument(
        "--n-subsample",
        type=int,
        default=N_SUBSAMPLE,
        help="Number of tasks to subsample for products"
    )

    parser.add_argument(
        "--exp-dir",
        type=str,
        default=EXP_DIR,
        help="Directory to store experiment configs"
    )

    parser.add_argument(
        "--seed",
        type=str,
        default=SEED,
        help="Seed for the random subsampling"
    )

    args = parser.parse_args()
    generate_experiments(args.n_repeats, args.n_subsample, args.exp_dir, args.seed)

def generate_experiments(n_repeats, n_subsample, exp_dir, seed):
    # Load CSV files
    df_intents = pd.read_csv("tasks/intents.csv")
    df_interventions = pd.read_csv("tasks/interventions.csv")
    df_products = pd.read_csv("tasks/products.csv").drop(columns=["Notes"])
    df_categories = pd.read_csv("tasks/categories.csv").drop(columns=["Notes"])
    df_home = pd.read_csv("tasks/home.csv").drop(columns=["Notes"])

    # Include the intent template ID
    df_intents = df_intents.reset_index().rename(columns={"index": "Intent Template ID"})

    # Expand the supported nudges into multiple rows
    df_intents["Supported Nudges"] = df_intents["Supported Nudges"].str.split(", ")
    df_intents = df_intents.explode("Supported Nudges")
    df_intents = df_intents.reset_index(drop=True).rename(columns={"Supported Nudges": "Nudge"})

    # Expand the modules into multiple rows
    df_interventions["Module"] = df_interventions["Module"].str.split(",")
    df_interventions = df_interventions.explode("Module")
    df_interventions = df_interventions.reset_index(drop=True)
    mapping = {
        "nudgelab.choices.shop.product": "Product",
        "nudgelab.choices.shop.category": "Category",
        "nudgelab.choices.shop.home": "Home"
    }
    df_interventions["Starting Point"] = df_interventions["Module"].map(mapping)

    # Combine intents and interventions
    df_tasks = df_intents.merge(
        df_interventions,
        left_on=("Nudge", "Starting Point"),
        right_on=("Nudge", "Starting Point"),
        how="left"
    )

    # Convert Start URLs from a list within a string, to a list of strings
    df_products["Start URLs"] = df_products["Start URLs"].str.strip('[]').str.split(',')
    df_products["Start URLs"] = df_products["Start URLs"].apply(
        lambda lst: [item.strip() for item in lst]
    )

    # Get all possible combinations of 2 elements (ignores order, but can be done with permutations instead)
    df_products["Start URLs"] = df_products["Start URLs"].apply(
        lambda lst: list(itertools.combinations(lst, 2))
    )

    # Explode the combinations to automatically get all tests
    df_products = df_products[["Start URLs"]].explode("Start URLs", ignore_index=True)

    # Subslect by type
    df_tasks_products = df_tasks[df_tasks["Starting Point"] == "Product"].copy()
    df_tasks_categories = df_tasks[df_tasks["Starting Point"] == "Category"].copy()
    df_tasks_home = df_tasks[df_tasks["Starting Point"] == "Home"].copy()

    # Combine with start urls in other dataframe
    df_tasks_products_all = df_tasks_products.merge(df_products, how="cross")
    df_tasks_categories_all = df_tasks_categories.merge(df_categories, how="cross")

    # Subsample product tasks
    df_tasks_products_all = df_tasks_products_all.sample(
        n=n_subsample,
        random_state=seed
    )

    # Set home url and create the intent dictionary
    df_tasks_home.loc[:, "Start URLs"] = "${env.wa_shopping_url}"
    df_tasks_home_all = df_tasks_home.merge(df_home, on="Intent Variables")
    df_tasks_home_all["Intent Dictionary"] = df_tasks_home_all.apply(
        lambda row: str({row["Intent Variables"]: row["Intent Value"]}),
        axis=1
    )

    # Clean up a few columns
    df_tasks_products_all.drop(inplace=True, columns=["Intent Variables"])
    df_tasks_categories_all.drop(inplace=True, columns=["Intent Variables"])
    df_tasks_home_all.drop(inplace=True, columns=["Intent Variables", "Intent Value"])

    # Empty intent dictionary for products and categories
    df_tasks_products_all["Intent Dictionary"] = "{}"
    df_tasks_categories_all["Intent Dictionary"] = "{}"

    # Set Nudge Index to NaN
    df_tasks_products_all["Nudge Index"] = np.nan
    df_tasks_categories_all["Nudge Index"] = np.nan
    df_tasks_home_all["Nudge Index"] = np.nan

    # We need to duplicate the product tasks to nudge different tabs and none at all
    # Create duplicated rows with Nudge Index 0..N (number of elements in Start URLs - 1)
    duplicates = df_tasks_products_all.loc[
        df_tasks_products_all.index.repeat(
            df_tasks_products_all["Start URLs"].str.len()
        )
    ].copy()
    duplicates["Nudge Index"] = df_tasks_products_all.groupby(
        df_tasks_products_all.index
    ).apply(
        lambda x: list(range(len(x.iloc[0]["Start URLs"])))
    ).explode().astype(int).values

    # Combine original + duplicated
    df_tasks_products_all = pd.concat(
        [df_tasks_products_all, duplicates],
        ignore_index=True
    ).reset_index(drop=True)

    # We need to duplicate the category tasks to nudge different (random) products and none at all
    # Repeat each row N times
    repeats = df_tasks_categories_all.loc[
        df_tasks_categories_all.index.repeat(n_repeats)
    ].copy()
    repeats["Nudge Index"] = 0
    df_tasks_categories_all = pd.concat(
        [df_tasks_categories_all, repeats],
        ignore_index=True
    ).reset_index(drop=True)

    # We need to duplicate the category tasks to nudge different (random) products and none at all
    # Repeat each row N times
    repeats = df_tasks_home_all.loc[df_tasks_home_all.index.repeat(n_repeats)].copy()
    repeats["Nudge Index"] = 0
    df_tasks_home_all = pd.concat(
        [df_tasks_home_all, repeats],
        ignore_index=True
    ).reset_index(drop=True)

    # Create final dataframe with all task details
    df_tasks_all = pd.concat(
        [df_tasks_products_all, df_tasks_categories_all, df_tasks_home_all],
        ignore_index=True
    )

    # Generate config YAMLs
    if not os.path.exists(exp_dir):
        os.makedirs(exp_dir)

    for idx, row in tqdm(df_tasks_all.iterrows(), total=len(df_tasks_all)):
        if np.isnan(row["Nudge Index"]):
            choices = []
        else:
            if isinstance(row["Start URLs"], tuple):
                url = row["Start URLs"][int(row["Nudge Index"])]
            else:
                url = row["Start URLs"]

            choices = [{
                "url": url,
                "nudge": row["Nudge"],
                "functions": [{
                    "module": row["Module"],
                    "name": row["Name"],
                    "args": {"value": row["Intervention"]}
                }]

            }]
        intent = string.Template(row["Intent"]).substitute(eval(row["Intent Dictionary"]))

        name = "exp" + str(idx)
        data = {
            "task": {
                "name": name,
                "config": {
                    "task_id": idx,
                    "start_urls": list(row["Start URLs"] if isinstance(row["Start URLs"], tuple) else [row["Start URLs"]]),
                    "intent_template": row["Intent"],
                    "instantiation_dict": eval(row["Intent Dictionary"]),
                    "intent": intent,
                    "choices": choices,
                    "intent_template_id": row["Intent Template ID"]
                }
            }
        }

        # Save to a YAML file
        with open(f"{exp_dir}/{name}.yaml", "w") as f:
            f.write("# @package _global_\n\n")
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2
            )

if __name__ == "__main__":
    main()
