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

N_REPEATS = 6
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
        n_repeats,
        exp_dir,
        products,
        categories,
        home,
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
    mapping = {
        "nudgelab.choices.shop.product": "Product",
        "nudgelab.choices.shop.category": "Category",
        "nudgelab.choices.shop.home": "Home"
    }
    df_interventions["Starting Point"] = df_interventions["Module"].map(mapping)

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

    if products:
        df_products = pd.read_csv(products)

        print("=" * 50)
        print(f"Loaded {len(df_products)} product pairs")
        print(f"Loaded {len(df_tasks[df_tasks['Starting Point'] == 'Product'])} interventions")

        # Create pairs of Start URLs
        df_products["Start URLs"] = list(zip(df_products["product1_url"], df_products["product2_url"]))
        df_products["Start URLs"] = df_products["Start URLs"].apply(
            lambda t: tuple(random.sample(t, len(t))) # Shuffle
        )

        # Calculate average price for product pairs
        df_products["Average Price"] = (df_products["product1_price"] + df_products["product2_price"]) / 2
        df_products["Average Review Count"] = (df_products["product1_reviews"] + df_products["product2_reviews"]) // 2

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

    if categories:
        # Load categories CSV
        df_categories = pd.read_csv("tasks/categories.csv")

        print("=" * 50)
        print(f"Loaded {len(df_categories)} categories")
        print(f"Loaded {len(df_tasks[df_tasks['Starting Point'] == 'Category'])} interventions")

        # Subselect category tasks
        df_tasks_categories = df_tasks[df_tasks["Starting Point"] == "Category"].copy()

        # Combine with start urls in other dataframe
        df_tasks_categories_all = df_tasks_categories.merge(df_categories, how="cross")

        # Empty intent dictionary
        df_tasks_categories_all["Intent Dictionary"] = "{}"

        # Set Nudge Index to NaN
        df_tasks_categories_all["Nudge Index"] = np.nan

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

        print(f"Generating {len(df_tasks_categories_all)} category configs")
        print("=" * 50 + "\n")

    if home:
        # Load home CSV
        df_home = pd.read_csv(home)

        print("=" * 50)
        print(f"Loaded {len(df_home)} categories (home)")
        print(f"Loaded {len(df_tasks[df_tasks['Starting Point'] == 'Home'])} interventions")

        # Subselect home tasks
        df_tasks_home = df_tasks[df_tasks["Starting Point"] == "Home"].copy()

        # Set home url and create the intent dictionary
        df_tasks_home.loc[:, "Start URLs"] = "${env.wa_shopping_url}"
        df_tasks_home_all = df_tasks_home.merge(df_home, on="Intent Variables")
        df_tasks_home_all["Intent Dictionary"] = df_tasks_home_all.apply(
            lambda row: str({row["Intent Variables"]: row["Intent Value"]}),
            axis=1
        )

        # Set Nudge Index to NaN
        df_tasks_home_all["Nudge Index"] = np.nan

        # We need to duplicate the category tasks to nudge different (random) products and none at all
        # Repeat each row N times
        repeats = df_tasks_home_all.loc[df_tasks_home_all.index.repeat(n_repeats)].copy()
        repeats["Nudge Index"] = 0
        df_tasks_home_all = pd.concat(
            [df_tasks_home_all, repeats],
            ignore_index=True
        ).reset_index(drop=True)

        print(f"Generating {len(df_tasks_home_all)} home configs")
        print("=" * 50)

    if not dry_run:
        # Save configs
        if products:
            print(f"Generating {len(df_tasks_products_all)} product configs...")
            save_configs(df_tasks_products_all, exp_dir, match_price, match_review_count)
        if categories:
            print(f"Generating {len(df_tasks_categories_all)} category configs...")
            save_configs(df_tasks_categories_all, exp_dir, match_price, match_review_count)
        if home:
            print(f"Generating {len(df_tasks_home_all)} home configs...")
            save_configs(df_tasks_home_all, exp_dir, match_price, match_review_count)


def save_configs(df, exp_dir, match_price=False, match_review_count=False):
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        if np.isnan(row["Nudge Index"]):
            choices = []
        else:
            if isinstance(row["Start URLs"], tuple):
                url = row["Start URLs"][int(row["Nudge Index"])]
            else:
                if row["Starting Point"] == "Home":
                    url = "*"
                else:
                    url = row["Start URLs"]

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
        # Note: For now only available for products
        if match_price and isinstance(row["Start URLs"], tuple):
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
        # Note: For now only available for products
        if match_review_count and isinstance(row["Start URLs"], tuple):
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
                    "start_urls": list(row["Start URLs"] if isinstance(row["Start URLs"], tuple) else [row["Start URLs"]]),
                    "intent_template": row["Intent"].replace("$", "\\$"),
                    "instantiation_dict": eval(row["Intent Dictionary"]),
                    "intent": intent,
                    "choices": choices,
                    "intent_template_id": row["Intent Template ID"]
                }
            }
        }

        if "coverage_type" in row:
            data["task"]["config"]["metadata"] = {"coveragy_type": row["coverage_type"]}
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
        "--n-repeats",
        type=int,
        default=N_REPEATS,
        help="Number of repetitions for category and home tasks"
    )

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
        help="Path to product pairs CSV (e.g. tasks/product_pairs.csv)"
    )

    parser.add_argument(
        "--categories",
        type=str,
        help="Path to categories CSV (e.g. tasks/categories.csv)"
    )

    parser.add_argument(
        "--home",
        type=str,
        help="Path to home CSV (e.g. tasks/home.csv)"
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
        args.n_repeats,
        args.exp_dir,
        args.products,
        args.categories,
        args.home,
        args.match_price,
        args.match_review_count,
        args.no_nudges,
        args.dry_run,
        args.seed
    )

if __name__ == "__main__":
    main()
