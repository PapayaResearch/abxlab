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
import random
import dspy
import dotenv
from tqdm import tqdm
from generate_experiments import save_configs, VariableSubstitution

SEED = 42
EXP_DIR = "conf/experiment"
MODEL = "gpt-4.1-mini"
NUDGE_PREFERENCES = [
    "The user highly values recommendations from experts.",
    "The user doesn't trust recommendations from experts."
]
NO_NUDGE_PREFERENCES = [
    "The user is on a tight budget.",
    "The user is willing to pay more for a better product.",
    "The user values highly-rated products.",
    "The user doesn't put much stock in what other customers think."
]

def generate_experiments(
        exp_dir,
        products,
        combine,
        dry_run,
        seed
):
    # Apply the seed for reproducibility
    random.seed(seed)

    # Generate config YAMLs
    if not os.path.exists(exp_dir):
        os.makedirs(exp_dir)

    # Load category context
    with open("tasks/categories.yaml", "r") as f:
        category_context = f.read()

    # Load CSV files
    df_intents = pd.read_csv("tasks/intents.csv")
    df_interventions = pd.read_csv("tasks/interventions-preferences.csv")

    # Include the intent template ID
    df_intents = df_intents.reset_index().rename(columns={"index": "Intent Template ID"})
    # Subselect only product intents
    df_intents = df_intents[df_intents["Starting Point"] == "Product"]

    # Expand the modules into multiple rows
    df_interventions["Module"] = df_interventions["Module"].str.split(",")
    df_interventions = df_interventions.explode("Module")
    df_interventions = df_interventions.reset_index(drop=True)
    df_interventions = df_interventions[df_interventions["Module"] == "abxlab.choices.shop.product"]
    df_interventions["Starting Point"] = "Product"

    # Combine intents and interventions
    df_tasks = df_intents.merge(
        df_interventions,
        left_on=("Starting Point"),
        right_on=("Starting Point"),
        how="left"
    )

    df_products = pd.read_csv(products)

    print("=" * 50)
    print(f"Loaded {len(df_products)} product pairs")
    print(f"Loaded {len(df_tasks[df_tasks['Starting Point'] == 'Product'])} interventions")

    # Create pairs of Start URLs
    df_products["Start URLs"] = list(zip(df_products["product1_url"], df_products["product2_url"]))
    df_products["Start URLs"] = df_products["Start URLs"].apply(
        lambda t: tuple(random.sample(t, len(t))) # Shuffle
    )

    # Combine with start urls in other dataframe
    df_tasks_all = df_tasks.merge(df_products, how="cross")

    # Empty intent dictionary
    df_tasks_all["Intent Dictionary"] = "{}"

    # Set Nudge Index to NaN
    df_tasks_all["Nudge Index"] = np.nan

    # Process variable substitutions with an LLM
    print(f"Generating interventions with LLM calls...")
    llm_call = dspy.ChainOfThought(VariableSubstitution)

    unique_intervention_category = df_tasks_all[
        ~df_tasks_all["Variables"].isna()
    ][["category", "Intervention", "Variables"]].drop_duplicates()

    substitution_map = {}
    for _, row in tqdm(unique_intervention_category.iterrows(),
                       total=len(unique_intervention_category)):
        # Generate substituted intervention
        new_intervention = string.Template(row["Intervention"]).substitute(
            {
                row["Variables"]: llm_call(
                    intervention=row["Intervention"],
                    variable=row["Variables"],
                    category=row["category"],
                    category_context=category_context
                ).value
            }
        )

        # Store mapping from original to substituted intervention
        substitution_map[(row["category"], row["Intervention"])] = new_intervention

    # Apply substitutions to original dataframe
    df_tasks_all["Intervention"] = df_tasks_all.apply(
        lambda row: substitution_map.get(
            (row["category"], row["Intervention"]),
            row["Intervention"]
        ),
        axis=1
    )

    if not combine:
        ### NUDGE PREFERENCES

        # We need to duplicate the product tasks to nudge both L/R tabs
        # Create duplicated rows with Nudge Index 0..N (number of elements in Start URLs - 1)
        df_tasks_nudge = df_tasks_all.loc[
            df_tasks_all.index.repeat(
                df_tasks_all["Start URLs"].str.len()
            )
        ].copy()
        df_tasks_nudge["Nudge Index"] = df_tasks_all.groupby(
            df_tasks_all.index
        ).apply(
            lambda x: list(range(len(x.iloc[0]["Start URLs"])))
        ).explode().astype(int).values

        # Duplicate task configs with the NUDGE_PREFERENCES personas
        df_tasks_nudge = pd.concat([
            df_tasks_nudge.assign(user_preference=NUDGE_PREFERENCES[0]),
            df_tasks_nudge.assign(user_preference=NUDGE_PREFERENCES[1])
        ], ignore_index=True)

    ### NO NUDGE PREFERENCES

    # Duplicate task configs with the NO_NUDGE_PREFERENCES personas
    df_tasks_no_nudge = df_tasks_all.copy()
    if combine is not None:
        df_tasks_no_nudge = df_tasks_no_nudge.assign(user_preference=combine)
    else:
        df_tasks_no_nudge = pd.concat([
            df_tasks_no_nudge.assign(user_preference=NO_NUDGE_PREFERENCES[0]),
            df_tasks_no_nudge.assign(user_preference=NO_NUDGE_PREFERENCES[1]),
            df_tasks_no_nudge.assign(user_preference=NO_NUDGE_PREFERENCES[2]),
            df_tasks_no_nudge.assign(user_preference=NO_NUDGE_PREFERENCES[3])
        ], ignore_index=True)

    # Combine all configs
    if combine is not None:
        df_tasks_all = df_tasks_no_nudge
    else:
        df_tasks_all = pd.concat(
            [df_tasks_nudge, df_tasks_no_nudge],
            ignore_index=True
        ).reset_index(drop=True)

    df_tasks_all["Intent"] = df_tasks_all.apply(
        lambda row: row["Intent"] + "\n" + row["user_preference"],
        axis=1
    )

    print(f"Generating {len(df_tasks_all)} product configs")

    if not dry_run:
        # Save configs
        save_configs(df_tasks_all, exp_dir)

    print("=" * 50)

def main():
    parser = argparse.ArgumentParser(description="Generates all experiment configs.")

    parser.add_argument(
        "--exp-dir",
        type=str,
        default=EXP_DIR,
        help="Directory to store experiment configs"
    )

    parser.add_argument(
        "--model",
        type=str,
        default=MODEL,
        help="LLM model to generate variable interventions"
    )

    parser.add_argument(
        "--products",
        type=str,
        required=True,
        help="Path to product pairs CSV (e.g. tasks/product_pairs.csv)"
    )

    parser.add_argument(
        "--combine",
        type=str,
        help="Use a single user preference combining personas"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Just check experiment count without actually writing configs"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help="Seed for the random subsampling"
    )

    args = parser.parse_args()
    dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env"))
    dspy.configure(lm=dspy.LM(args.model, temperature=0.1))

    generate_experiments(
        args.exp_dir,
        args.products,
        args.combine,
        args.dry_run,
        args.seed
    )

if __name__ == "__main__":
    main()
