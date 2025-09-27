import logging
import argparse
import pandas as pd
from urllib.parse import urlparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_files", type=str, nargs='+', required=True, help="Input CSV file paths")
    parser.add_argument("--output_file", type=str, required=True, help="Output CSV file path for processed data")
    parser.add_argument("--num_workers", type=int, default=8, help="(Maximum) number of parallel workers for fetching data")
    parser.add_argument("--product_list", type=str, help="Optional list of product URLs to include metadata.")
    args = parser.parse_args()

    df_list = [pd.read_csv(file) for file in args.input_files]
    df = pd.concat(df_list, ignore_index=True)
    
    # Filter to pairs
    df["cfg.task.config.start_urls"] = df["cfg.task.config.start_urls"].map(eval)
    df = df[df["cfg.task.config.start_urls"].map(len) == 2].copy()
    logger.info("Found %d pairs with exactly 2 start URLs", len(df))
    
    if args.product_list:
        df_products = pd.read_csv(args.product_list)
        product_map = df_products.set_index("product_url")["category"].to_dict()
        product_map = {urlparse(url).path: category for url, category in product_map.items()}
        df["category"] = df["cfg.task.config.start_urls"].map(lambda urls: product_map[urlparse(urls[0]).path])

    df["choices"] = df["cfg.task.config.choices"].map(eval)

    # Identify nudged choice
    nudge_types_to_ignore = ["Matching Review Count", "Matching Price"]
    
    df["nudged_choice_url"] = df["choices"].map(
        lambda x: x[0]["url"] if ((len(x) > 0) and (x[0]["nudge"] not in nudge_types_to_ignore)) else None
    )
    df["nudge_type"] = df["choices"].map(
        lambda x: x[0]["nudge"] if ((len(x) > 0) and (x[0]["nudge"] not in nudge_types_to_ignore)) else None
    )
    
    df["nudge_text"] = df["choices"].map(
        lambda x: x[0]["functions"][0]["args"]["value"] if ((len(x) > 0) and (x[0]["nudge"] not in nudge_types_to_ignore)) else None
    )
    
    df["chose_nudged_product"] = df.apply(
        lambda row: row["final_step.url"] == row["nudged_choice_url"],
        axis=1
    )

    # Fetch product data
    df = fetch_product_data_parallel(df, max_workers=args.num_workers)

    # Prepare data for regression
    # df_reg = df[df["nudged_choice_url"].notnull()].copy()
    df_reg = df.copy()
    df_reg["nudge_trial"] = df_reg["nudged_choice_url"].notnull()

    # Get product indices
    df_reg["nudged_idx"] = df_reg.apply(
        lambda row: row["cfg.task.config.start_urls"].index(row["nudged_choice_url"]) if row["nudge_trial"] else None,
        axis=1
    ).astype("Int64")
    df_reg["chose_idx"] = df_reg.apply(
        lambda row: row["cfg.task.config.start_urls"].index(row["final_step.url"]) if row["final_step.url"] in row["cfg.task.config.start_urls"] else None,
        axis=1
    ).astype("Int64")
    df_reg["other_idx"] = 1 - df_reg["nudged_idx"]
    
    # Remove any invalid choices
    df_reg = df_reg[df_reg["chose_idx"].notnull()]
    df_reg = df_reg[df_reg["final_step.elem_info.attrs.id"].notnull()]
    df_reg = df_reg[df_reg["final_step.elem_info.attrs.id"].map(lambda x: "addtocart" in x)]

    # Extract prices and ratings based on nudged/other product
    df_reg["price_nudged"] = df_reg.apply(lambda row: row["prices"][row["nudged_idx"]] if row["nudge_trial"] else None, axis=1)
    df_reg["price_other"] = df_reg.apply(lambda row: row["prices"][row["other_idx"]] if row["nudge_trial"] else None, axis=1)
    df_reg["rating_nudged"] = df_reg.apply(lambda row: row["ratings"][row["nudged_idx"]] if row["nudge_trial"] else None, axis=1)
    df_reg["rating_other"] = df_reg.apply(lambda row: row["ratings"][row["other_idx"]] if row["nudge_trial"] else None, axis=1)
    
    df_reg["avg_price"] = df_reg["prices"].apply(lambda x: sum(x) / len(x))
    df_reg["price_diff_lr"] = df_reg["prices"].apply(lambda x: abs(x[1] - x[0]))
    df_reg["price_diff_lr_pct"] = df_reg["price_diff_lr"] / df_reg["avg_price"]
    
    df_reg["chose_cheaper"] = df_reg.apply(
        lambda row: row["prices"][row["chose_idx"]] < row["prices"][1 - row["chose_idx"]],
        axis=1
    )
    df_reg["cheaper_idx"] = df_reg.apply(
        lambda row: min(enumerate(row["prices"]), key=lambda x: x[1])[0],
        axis=1
    )
    df_reg["better_rated_idx"] = df_reg.apply(
        lambda row: max(enumerate(row["ratings"]), key=lambda x: x[1])[0],
        axis=1
    )
    df_reg["chose_better_rated"] = df_reg.apply(
        lambda row: row["ratings"][row["chose_idx"]] > row["ratings"][1 - row["chose_idx"]],
        axis=1
    )

    # Calculate differences
    df_reg["price_diff"] = df_reg["price_nudged"] - df_reg["price_other"]
    df_reg["rating_diff"] = df_reg["rating_nudged"] - df_reg["rating_other"]
    
    # Get nudge type
    df_reg["nudge_type"] = df_reg["choices"].map(lambda x: x[0]["nudge"] if len(x) > 0 else None)

    # Create model_family column
    df_reg["model_family"] = df_reg["study.chat_model_args.model_name"]
    
    # Save the processed data for further inspection
    df_reg.to_csv(args.output_file, index=False)
    logger.info("Saved preprocessed data to %s", args.output_file)


def fetch_single_product_data(url: str) -> tuple[str, float, float]:
    try:
        rating = float(get_rating_for_product(url).replace("%", ""))
        price = float(get_price_for_product(url).replace("$", "").replace(",", ""))
        return url, rating, price
    except Exception as error:
        logger.warning("Failed to fetch data for %s: %s" % (url, error))
        return url, 0.0, 0.0


def fetch_product_data_parallel(df: pd.DataFrame, max_workers: int = 8) -> pd.DataFrame:
    logger.info("Fetching product ratings and prices with %d workers", max_workers)

    all_urls = set()
    for urls in df["cfg.task.config.start_urls"]:
        all_urls.update(urls)
    all_urls = list(all_urls)

    url_data = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_single_product_data, url): url for url in all_urls}

        with tqdm(total=len(futures), desc="Fetching product data") as pbar:
            for future in as_completed(futures):
                url, rating, price = future.result()
                url_data[url] = {"rating": rating, "price": price}
                pbar.update(1)

    df["ratings"] = df["cfg.task.config.start_urls"].map(
        lambda urls: [url_data[url]["rating"] for url in urls]
    )
    df["prices"] = df["cfg.task.config.start_urls"].map(
        lambda urls: [url_data[url]["price"] for url in urls]
    )

    return df


if __name__ == "__main__":
    main()
