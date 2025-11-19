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
This script generates experiment configuration files based on provided data files.
"""

import os
import argparse
import string
import yaml
import pandas as pd
import numpy as np
import random
import dspy
import dotenv
from tqdm import tqdm

SEED = 42
EXP_DIR = "conf/experiment"
MODEL = "gpt-4.1-mini"

class VariableSubstitution(dspy.Signature):
    """Given an intervention with a variable placeholder, a variable name, and a product category, generate an appropriate replacement value for that variable. The intervention must be coherent when replacing the variable with a value. The category name must be simplified to ensure the intervention sounds as natural as possible. Pay attention to the category context, some categories are ambigious."""

    intervention: str = dspy.InputField(desc="Intervention text containing the variable to replace")
    variable: str = dspy.InputField(desc="Variable name to replace (appears as ${} in intervention)")
    category: str = dspy.InputField(desc="Product category context")
    category_context: str = dspy.InputField(desc="Additional context about the categories")
    value: str = dspy.OutputField(desc="Replacement value for the variable")

def generate_experiments(
        exp_dir,
        products,
        match_price,
        match_review_count,
        no_nudges,
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
    df_interventions = pd.read_csv("tasks/interventions.csv")

    # Include the intent template ID
    df_intents = df_intents.reset_index().rename(columns={"index": "Intent Template ID"})

    # Expand the supported nudges into multiple rows
    if not no_nudges:
        df_intents["Supported Nudges"] = df_intents["Supported Nudges"].str.split(", ")
        df_intents = df_intents.explode("Supported Nudges")
        df_intents = df_intents.reset_index(drop=True).rename(columns={"Supported Nudges": "Nudge"})

    # Expand the modules into multiple rows
    df_interventions["Module"] = df_interventions["Module"].str.split(",")
    df_interventions = df_interventions.explode("Module")
    df_interventions = df_interventions.reset_index(drop=True)
    df_interventions["Starting Point"] = df_interventions["Module"].map(
        {
            "abxlab.choices.shop.product": "Product"
        }
    )

    # Combine intents and interventions
    if no_nudges:
        df_tasks = df_intents.copy()
    else:
        df_tasks = df_intents.merge(
            df_interventions,
            left_on=("Nudge", "Starting Point"),
            right_on=("Nudge", "Starting Point"),
            how="left"
        )

    df_products = pd.read_csv(products)

    # Default to group_size=2 if column doesn't exist (backward compatibility)
    if 'group_size' not in df_products.columns:
        df_products['group_size'] = 2

    print("=" * 50)
    print(f"Loaded {len(df_products)} product groups")
    print(f"Loaded {len(df_tasks[df_tasks['Starting Point'] == 'Product'])} interventions")

    # Create Start URLs dynamically based on group_size
    def extract_product_urls(row):
        n = int(row['group_size'])
        urls = [row[f'product{i+1}_url'] for i in range(n)]
        return tuple(random.sample(urls, len(urls)))  # Shuffle

    df_products["Start URLs"] = df_products.apply(extract_product_urls, axis=1)

    # Calculate average price and review count dynamically
    def calculate_average_price(row):
        n = int(row['group_size'])
        prices = [row[f'product{i+1}_price'] for i in range(n)]
        return sum(prices) / n

    def calculate_average_reviews(row):
        n = int(row['group_size'])
        reviews = [row[f'product{i+1}_reviews'] for i in range(n)]
        return sum(reviews) // n

    df_products["Average Price"] = df_products.apply(calculate_average_price, axis=1)
    df_products["Average Review Count"] = df_products.apply(calculate_average_reviews, axis=1)

    # Subselect by type
    df_tasks_products = df_tasks[df_tasks["Starting Point"] == "Product"].copy()

    # Combine with start urls in other dataframe
    df_tasks_products_all = df_tasks_products.merge(df_products, how="cross")

    # Empty intent dictionary
    df_tasks_products_all["Intent Dictionary"] = "{}"

    # Set Nudge Index to NaN
    df_tasks_products_all["Nudge Index"] = np.nan

    # Process variable substitutions with an LLM
    print(f"Generating interventions with LLM calls...")
    llm_call = dspy.ChainOfThought(VariableSubstitution)

    if not no_nudges:
        unique_intervention_category = df_tasks_products_all[
            ~df_tasks_products_all["Variables"].isna()
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
        df_tasks_products_all["Intervention"] = df_tasks_products_all.apply(
            lambda row: substitution_map.get(
                (row["category"], row["Intervention"]),
                row["Intervention"]
            ),
            axis=1
        )

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

    print(f"Generating {len(df_tasks_products_all)} product configs")
    print("=" * 50 + "\n")

    if not dry_run:
        # Save configs
        save_configs(df_tasks_products_all, exp_dir, match_price, match_review_count)


def save_configs(df, exp_dir, match_price=False, match_review_count=False):
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        if np.isnan(row["Nudge Index"]):
            choices = []
        else:
            url = row["Start URLs"][int(row["Nudge Index"])]
            choices = [
                {
                    "url": url,
                    "nudge": row["Nudge"],
                    "functions": [
                        {
                            "module": row["Module"],
                            "name": row["Name"],
                            "args": {"value": row["Intervention"]}
                        }
                    ]
                }
            ]

        # If matching price, then always create the intervention
        if match_price:
            for url in row["Start URLs"]:
                choices.append(
                    {
                        "url": url,
                        "nudge": "Matching Price",
                        "functions": [
                            {
                                "module": row["Module"],
                                "name": "price",
                                "args": {"value": row["Average Price"]}
                            }
                        ]
                    }
                )

        # If matching review count, then always create the intervention
        if match_review_count:
            for url in row["Start URLs"]:
                choices.append(
                    {
                        "url": url,
                        "nudge": "Matching Review Count",
                        "functions": [
                            {
                                "module": row["Module"],
                                "name": "review_count",
                                "args": {"value": row["Average Review Count"]}
                            }
                        ]
                    }
                )

        intent = string.Template(row["Intent"]).substitute(eval(row["Intent Dictionary"]))

        name = "exp" + str(idx)
        data = {
            "task": {
                "name": name,
                "config": {
                    "task_id": idx,
                    "start_urls": list(row["Start URLs"]),
                    "intent_template": row["Intent"].replace("$", "\\$"),
                    "instantiation_dict": eval(row["Intent Dictionary"]),
                    "intent": intent,
                    "choices": choices,
                    "intent_template_id": row["Intent Template ID"]
                }
            }
        }

        if "coverage_type" in row:
            data["task"]["config"]["metadata"] = {"coverage_type": row["coverage_type"]}
        if "user_preference" in row:
            data["task"]["config"]["metadata"] = {"user_preference": row["user_preference"]}

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
        help="Path to product groups CSV (e.g. tasks/product_groups.csv)"
    )

    parser.add_argument(
        "--match-price",
        action="store_true",
        help="Flag to generate configs with price matching to average"
    )

    parser.add_argument(
        "--match-review-count",
        action="store_true",
        help="Flag to generate configs with review count matching to average"
    )

    parser.add_argument(
        "--no-nudges",
        action="store_true",
        help="Flag to generate configs without nudges"
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
        args.match_price,
        args.match_review_count,
        args.no_nudges,
        args.dry_run,
        args.seed
    )

if __name__ == "__main__":
    main()
