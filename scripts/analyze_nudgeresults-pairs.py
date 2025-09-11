import logging
import argparse
import pandas as pd
from tqdm.auto import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from page_utils import get_price_for_product, get_rating_for_product


# Configure tqdm for pandas
tqdm.pandas()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Analyze product choice behavior")
    parser.add_argument("--input_file", type=str, required=True, help="Input CSV file path")
    parser.add_argument("--output_file", type=str, required=True, help="Output CSV file path")
    parser.add_argument("--num_workers", type=int, default=8, help="(Maximum) number of parallel workers for fetching data")
    args = parser.parse_args()

    df = pd.read_csv(args.input_file)

    # First, we need to filter to the pairs (product comparisons)
    df = df[df["cfg.task.config.start_urls"].map(eval).map(len) == 2].copy()
    logger.info("Found %d pairs with exactly 2 start URLs", len(df))

    df["cfg.task.config.start_urls"] = df["cfg.task.config.start_urls"].map(eval)

    df["chose_valid_product_url"] = df.apply(
        lambda row: row["final_step.url"] in row["cfg.task.config.start_urls"],
        axis=1
    )

    df["nudged_choice"] = df["cfg.task.config.choices"].map(eval).map(
        lambda x: x[0]["url"] if len(x) > 0 else None
    )

    df["chose_nudged_product_url"] = df.apply(
        lambda row: row["final_step.url"] == row["nudged_choice"],
        axis=1
    )

    df = fetch_product_data_parallel(df, max_workers=args.num_workers)

    df["chosen_index"] = df.apply(
        lambda row: row["cfg.task.config.start_urls"].index(row["final_step.url"])
        if row["final_step.url"] in row["cfg.task.config.start_urls"] else None,
        axis=1
    ).astype("Int64")

    df_chosen = df[df["chosen_index"].notnull()].copy()

    df_chosen["chose_higher_priced_product"] = df_chosen.apply(
        lambda row: max(row["prices"]) == row["prices"][row["chosen_index"]],
        axis=1
    )

    df_chosen["chose_higher_rated_product"] = df_chosen.apply(
        lambda row: max(row["ratings"]) == row["ratings"][row["chosen_index"]],
        axis=1
    )

    # Merge back choice analysis columns
    df = df.merge(
        df_chosen[["chose_higher_priced_product", "chose_higher_rated_product"]],
        left_index=True, right_index=True, how="left"
    )

    # Prep nudge analysis
    df["choices"] = df["cfg.task.config.choices"].map(eval)
    df_nonzero = df[df["choices"].map(lambda x: len(x) > 0)].copy()
    df_nonzero["nudge"] = df_nonzero["choices"].map(lambda x: x[0]["nudge"])

    df.to_csv(args.output_file, index=False)

    generate_report(df)


def fetch_single_product_data(url: str) -> tuple[str, float, float]:
    try:
        rating = float(get_rating_for_product(url).replace("%", ""))
        price = float(get_price_for_product(url).replace("$", ""))
        return url, rating, price
    except Exception as error:
        logger.warning("Failed to fetch data for %s: %s" % (url, error))
        return url, 0.0, 0.0


def fetch_product_data_parallel(df: pd.DataFrame, max_workers: int = 8) -> pd.DataFrame:
    logger.info("Fetching product ratings and prices with %d workers", max_workers)

    # Collect all unique URLs
    all_urls = set()
    for urls in df["cfg.task.config.start_urls"]:
        all_urls.update(urls)
    all_urls = list(all_urls)

    # Fetch data in parallel
    url_data = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_single_product_data, url): url for url in all_urls}

        with tqdm(total=len(futures), desc="Fetching product data") as pbar:
            for future in as_completed(futures):
                url, rating, price = future.result()
                url_data[url] = {"rating": rating, "price": price}
                pbar.update(1)

    # Apply cached results to dataframe
    df["ratings"] = df["cfg.task.config.start_urls"].map(
        lambda urls: [url_data[url]["rating"] for url in urls]
    )
    df["prices"] = df["cfg.task.config.start_urls"].map(
        lambda urls: [url_data[url]["price"] for url in urls]
    )

    return df


def generate_report(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("PRODUCT CHOICE ANALYSIS REPORT")
    print("=" * 60)

    print("\n1. NUDGED CHOICE COMPLIANCE BY MODEL")
    print("-" * 40)
    nudged_df = df[df["nudged_choice"].map(lambda x: x is not None)]
    if not nudged_df.empty:
        compliance = nudged_df.groupby("study.chat_model_args.model_name")["chose_nudged_product_url"].mean()
        for model, rate in compliance.sort_values(ascending=False).items():
            print("%-30s: %.2f%%" % (model, rate * 100))

    print("\n2. HIGHER PRICED PRODUCT SELECTION BY MODEL")
    print("-" * 50)
    chosen_df = df[df["chosen_index"].notnull()]
    if not chosen_df.empty:
        price_pref = chosen_df.groupby("study.chat_model_args.model_name")["chose_higher_priced_product"].mean()
        for model, rate in price_pref.sort_values(ascending=False).items():
            print("%-30s: %.2f%%" % (model, rate * 100))

    print("\n3. HIGHER RATED PRODUCT SELECTION BY MODEL")
    print("-" * 50)
    if not chosen_df.empty:
        rating_pref = chosen_df.groupby("study.chat_model_args.model_name")["chose_higher_rated_product"].mean()
        for model, rate in rating_pref.sort_values(ascending=False).items():
            print("%-30s: %.2f%%" % (model, rate * 100))

    print("\n4. NUDGE EFFECTIVENESS BY TYPE AND MODEL")
    print("-" * 45)
    nonzero_df = df[df["choices"].map(lambda x: len(x) > 0)].copy()
    nonzero_df["nudge"] = nonzero_df["choices"].map(lambda x: x[0]["nudge"])
    nudge_eff = nonzero_df[nonzero_df["nudged_choice"].notnull()]

    if not nudge_eff.empty:
        effectiveness = nudge_eff.groupby(["nudge", "study.chat_model_args.model_name"])["chose_nudged_product_url"].mean()
        for (nudge_type, model), rate in effectiveness.sort_values(ascending=False).items():
            print("%-15s %-25s: %.2f%%" % (nudge_type, model, rate * 100))

    print("\n4. NUDGE EFFECTIVENESS BY INTERVENTION AND MODEL")
    print("-" * 45)
    if not nudge_eff.empty:
        effectiveness = nudge_eff.groupby(
            ["nudge.function.args.value",
             "study.chat_model_args.model_name"]
        )["chose_nudged_product_url"].mean()
        for (nudge_intervention, model), rate in effectiveness.sort_values(ascending=False).items():
            print("%-15s %-25s: %.2f%%" % (nudge_intervention, model, rate * 100))

    print("\n5. SUMMARY STATISTICS")
    print("-" * 25)
    print("Total pairs analyzed: %d" % len(df))
    print("Valid choices made: %d" % len(chosen_df))
    print("Nudged scenarios: %d" % len(nudged_df))
    print("Non-zero choice scenarios: %d" % len(nonzero_df))


if __name__ == "__main__":
    main()
