import random
import argparse
import multiprocessing
import functools
import pandas as pd
import dspy
from tqdm import tqdm
from typing import Any


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", default="tasks/products.csv", help="Path to the input products CSV file.")
    parser.add_argument("--output_file", default="tasks/product_pairs.csv", help="Path to the output CSV file for product pairs.")
    parser.add_argument("--max_rating_diff", type=float, default=0.1, help="Maximum allowed rating difference (e.g., 0.1 for 10%%).")
    parser.add_argument("--max_price_diff", type=float, default=0.5, help="Maximum allowed price percentage difference (e.g., 0.2 for 20%%).")
    parser.add_argument("--strategy", choices=["sequential", "random", "dynamic"], default="sequential", help="Pairing strategy.")
    parser.add_argument("--neighborhood", type=int, default=1, help="Search neighborhood size for dynamic strategy (1 = consecutive pairs only).")
    parser.add_argument("--max_pairs", type=int, default=50, help="Maximum number of pairs to generate.")
    parser.add_argument("--use_llm_filter", action="store_true", help="Enable LLM-based title filtering.")
    parser.add_argument("--llm_model", default="gpt-4.1-nano", help="LLM model to use for filtering.")
    parser.add_argument("--num_workers", type=int, default=multiprocessing.cpu_count(), help="Number of parallel processes to use.")
    args = parser.parse_args()

    # Load data
    df: pd.DataFrame = pd.read_csv(args.input_file)
    df.dropna(subset=["rating", "price"], inplace=True)
    df["rating"] = df["rating"].map(lambda x: float(x.replace("%", "")))
    df = df[df["rating"] > 0]

    # LLM Filtering
    if args.use_llm_filter:
        print("Filtering products with LLM...")
        chunks = [df_part for _, df_part in df.groupby(df.index // (len(df) // args.num_workers))]
        with multiprocessing.Pool(processes=args.num_workers) as pool:
            results = list(
                tqdm(
                    pool.imap(
                        functools.partial(filter_products_chunk, llm_model=args.llm_model),
                        chunks,
                        chunksize=1
                    ),
                    total=len(chunks),
                    desc="Filtering products",
                    position=0
                )
            )
        df = pd.concat(results)
        print(f"Filtered down to {len(df)} products.")

    df["price"] = df["price"].str.replace("$", "").str.replace(",", "").astype(float)
    df = df[~df["has_options"]]

    # Group by category
    grouped = df.groupby("category")
    all_pairs = []

    print(f"Processing {len(grouped)} categories...")

    for _, data in tqdm(grouped):
        if len(data) < 2:
            continue

        if args.strategy == "sequential":
            pairs = generate_sequential_pairs(data, args.max_rating_diff, args.max_price_diff)
        elif args.strategy == "random":
            pairs = generate_random_pairs(data, args.max_rating_diff, args.max_price_diff)
        elif args.strategy == "dynamic":
            pairs = generate_dynamic_pairs(data, args.max_rating_diff, args.max_price_diff, args.neighborhood)
        
        all_pairs.extend(pairs)

    print(f"Generated {len(all_pairs)} pairs.")

    # Convert to DataFrame and save
    pair_records = []
    for p1, p2 in all_pairs:
        pair_records.append(
            {
                "category": p1["category"],
                "product1_name": p1["product_name"],
                "product1_url": p1["product_url"],
                "product1_price": p1["price"],
                "product1_rating": p1["rating"],
                "product2_name": p2["product_name"],
                "product2_url": p2["product_url"],
                "product2_price": p2["price"],
                "product2_rating": p2["rating"],
                "product1_reviews": p1["reviews"],
                "product2_reviews": p2["reviews"]
            }
        )

    output_df = pd.DataFrame(pair_records)
    
    # Subsample if too many pairs remain
    if len(output_df) > args.max_pairs:
        output_df = output_df.sample(n=args.max_pairs, random_state=42).reset_index(drop=True)
        print(f"Subsampled to {args.max_pairs} pairs.")
    
    output_df.to_csv(args.output_file, index=False)

    print(f"Saved {len(output_df)} product pairs to {args.output_file}")


def is_valid_pair(p1: dict[str, Any], p2: dict[str, Any], max_rating_diff: float, max_price_diff: float) -> bool:
    """Check if two products form a valid pair based on rating and price constraints."""
    # Check rating difference
    if abs(p1["rating"] - p2["rating"]) > max_rating_diff * 100:
        return False
    
    # Check price difference (percentage)
    if max_price_diff != float("inf"):
        min_price = min(p1["price"], p2["price"])
        if min_price > 0:  # Avoid division by zero
            price_diff_pct = abs(p1["price"] - p2["price"]) / min_price
            if price_diff_pct > max_price_diff:
                return False
    
    return True


def generate_sequential_pairs(data: pd.DataFrame, max_rating_diff: float, max_price_diff: float) -> list[tuple[dict, dict]]:
    """Generate consecutive pairs (original behavior)."""
    pairs = []
    sorted_data = data.sort_values(by="price").to_dict("records")
    
    for i in range(len(sorted_data) - 1):
        p1, p2 = sorted_data[i], sorted_data[i + 1]
        if is_valid_pair(p1, p2, max_rating_diff, max_price_diff):
            pairs.append((p1, p2))
    
    return pairs


def generate_random_pairs(data: pd.DataFrame, max_rating_diff: float, max_price_diff: float) -> list[tuple[dict, dict]]:
    """Generate random pairs."""
    pairs = []
    products = data.to_dict("records")
    
    for _ in range(len(products)):
        pair = random.sample(products, 2)
        if is_valid_pair(pair[0], pair[1], max_rating_diff, max_price_diff):
            pairs.append(tuple(pair))
    
    return pairs


def generate_dynamic_pairs(data: pd.DataFrame, max_rating_diff: float, max_price_diff: float, neighborhood: int) -> list[tuple[dict, dict]]:
    """
    Generate pairs using dynamic programming approach.
    
    This finds the maximum number of non-overlapping pairs within the neighborhood constraint
    while respecting rating and price difference limits.
    """
    if len(data) < 2:
        return []
    
    # Sort by price for consistent ordering
    sorted_data = data.sort_values(by="price").to_dict("records")
    n = len(sorted_data)
    
    # Build adjacency list of valid pairs within neighborhood
    valid_pairs = []
    for i in range(n):
        for j in range(i + 1, min(i + neighborhood + 1, n)):
            p1, p2 = sorted_data[i], sorted_data[j]
            if is_valid_pair(p1, p2, max_rating_diff, max_price_diff):
                valid_pairs.append((i, j, p1, p2))
    
    if not valid_pairs:
        return []
    
    # Dynamic programming to find maximum number of non-overlapping pairs
    # Sort pairs by ending index
    valid_pairs.sort(key=lambda x: x[1])
    
    # dp[i] = maximum number of pairs using pairs[0:i+1]
    m = len(valid_pairs)
    dp = [0] * m
    selected_pairs = [[] for _ in range(m)]
    
    # Base case
    dp[0] = 1
    selected_pairs[0] = [(valid_pairs[0][2], valid_pairs[0][3])]
    
    for i in range(1, m):
        current_pair = valid_pairs[i]
        current_start, current_end = current_pair[0], current_pair[1]
        
        # Option 1: Don't include current pair
        dp[i] = dp[i-1]
        selected_pairs[i] = selected_pairs[i-1][:]
        
        # Option 2: Include current pair
        # Find the latest pair that doesn't conflict with current pair
        latest_compatible = -1
        for j in range(i-1, -1, -1):
            prev_start, prev_end = valid_pairs[j][0], valid_pairs[j][1]
            # Check if pairs don't overlap (no shared products)
            if prev_end < current_start or prev_start > current_end:
                if prev_end != current_start and prev_start != current_end:  # No shared endpoint
                    latest_compatible = j
                    break
        
        # Calculate value if we include current pair
        include_value = 1
        include_pairs = [(current_pair[2], current_pair[3])]
        
        if latest_compatible >= 0:
            include_value += dp[latest_compatible]
            include_pairs = selected_pairs[latest_compatible][:] + include_pairs
        
        # Choose better option
        if include_value > dp[i]:
            dp[i] = include_value
            selected_pairs[i] = include_pairs
    
    return selected_pairs[m-1] if m > 0 else []


def filter_products_chunk(df_chunk: pd.DataFrame, llm_model: str) -> pd.DataFrame:
    lm = dspy.LM(model=llm_model)
    dspy.settings.configure(lm=lm)
    title_checker = TitleChecker()

    try:
        process_num = int(multiprocessing.current_process().name.split("-")[-1])
    except:
        process_num = 1

    tqdm.pandas(desc=f"Filtering titles in chunk-{process_num}", position=process_num, leave=False)
    contains_suggestion, is_multipack, mentions_quantity = zip(
        *df_chunk["product_name"].progress_apply(lambda title: filter_title_with_llm(title, title_checker))
    )
    df_chunk["contains_suggestion"] = contains_suggestion
    df_chunk["is_multipack"] = is_multipack
    df_chunk["mentions_quantity"] = mentions_quantity
    return df_chunk[~(df_chunk["contains_suggestion"] | df_chunk["is_multipack"] | df_chunk["mentions_quantity"])]


class CheckTitle(dspy.Signature):
    """Detect if a product title contains a 'nudge' or other leading phrase OR is a multi-pack OR notes the quantity.
    
    This is a subtle prompt or suggestion that influences consumer behavior.
    For example, phrases like:
    - "All-in-one"
    - "Free charger"
    - "Great for X"
    - "Top-rated"

    If the title contains such a phrase, please return True for contains_suggestion. If not, return False.
    If you are unsure, return False.

    You should also flag if the product is a multi-pack or bundle in is_multipack, e.g.:
    - "Set/Pack of 2/3/4+"
    - "Bundle deal"
    - "Multi-pack"
    - "Family pack"
    
    Finally, if the title mentions a quantity in any unit (e.g. "100g", "2L"), please return True for mentions_quantity.
    """

    title: str = dspy.InputField(desc="The product title to inspect.")
    contains_suggestion: bool = dspy.OutputField(desc="A boolean indicating if suggestion language is present.")
    is_multipack: bool = dspy.OutputField(desc="A boolean indicating if the product is a multi-pack or bundle.")
    mentions_quantity: bool = dspy.OutputField(desc="A boolean indicating if the title mentions a quantity.")


class TitleChecker(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.chain_of_thought = dspy.ChainOfThought(CheckTitle)

    def forward(self, title: str) -> dspy.Prediction:
        return self.chain_of_thought(title=title)


def filter_title_with_llm(title: str, title_checker: TitleChecker) -> bool:
    try:
        prediction = title_checker(title)
        return prediction.contains_suggestion, prediction.is_multipack, prediction.mentions_quantity
    except Exception as error:
        print(f"Error processing title '{title}': {error}")
        return False, False, False


if __name__ == "__main__":
    main()
