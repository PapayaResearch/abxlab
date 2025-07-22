import random
import argparse
import multiprocessing
import functools
import pandas as pd
import dspy
from tqdm import tqdm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", default="products.csv", help="Path to the input products CSV file.")
    parser.add_argument("--output_file", default="product_pairs.csv", help="Path to the output CSV file for product pairs.")
    parser.add_argument("--max_rating_diff", type=float, default=0.1, help="Maximum allowed rating difference (e.g., 0.1 for 10%%).")
    parser.add_argument("--strategy", choices=["sequential", "random"], default="sequential", help="Pairing strategy.")
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
            sorted_data = data.sort_values(by="price").to_dict("records")
            for i in range(len(sorted_data) - 1):
                all_pairs.append((sorted_data[i], sorted_data[i + 1]))
        elif args.strategy == "random":
            products = data.to_dict("records")
            for _ in range(len(products)):
                pair = random.sample(products, 2)
                all_pairs.append(tuple(pair))

    print(f"Generated {len(all_pairs)} initial pairs.")

    # Filter pairs
    final_pairs = []
    for p1, p2 in tqdm(all_pairs, desc="Filtering pairs"):
        if abs(p1["rating"] - p2["rating"]) > args.max_rating_diff * 100:
            continue
        final_pairs.append((p1, p2))

    # Convert to DataFrame and save
    pair_records = []
    for p1, p2 in final_pairs:
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
                "product2_rating": p2["rating"]
            }
        )

    output_df = pd.DataFrame(pair_records)
    output_df.to_csv(args.output_file, index=False)

    print(f"Saved {len(output_df)} product pairs to {args.output_file}")
    

def filter_products_chunk(df_chunk: pd.DataFrame, llm_model: str) -> pd.DataFrame:
    lm = dspy.LM(model=llm_model)
    dspy.settings.configure(lm=lm)
    title_checker = TitleChecker()

    try:
        process_num = int(multiprocessing.current_process().name.split("-")[-1])
    except:
        process_num = 1
        
    tqdm.pandas(desc=f"Filtering titles in chunk-{process_num}", position=process_num, leave=False)
    contains_suggestion, is_multipack = zip(
        *df_chunk["product_name"].progress_apply(lambda title: filter_title_with_llm(title, title_checker))
    )
    df_chunk["contains_suggestion"] = contains_suggestion
    df_chunk["is_multipack"] = is_multipack
    return df_chunk[~(df_chunk["contains_suggestion"] | df_chunk["is_multipack"])]
    
    
class CheckTitle(dspy.Signature):
    """Detect if a product title contains a 'nudge' or other leading phrase, and is a multi-pack.
    
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
    """

    title: str = dspy.InputField(desc="The product title to inspect.")
    contains_suggestion: bool = dspy.OutputField(desc="A boolean indicating if suggestion language is present.")
    is_multipack: bool = dspy.OutputField(desc="A boolean indicating if the product is a multi-pack or bundle.")


class TitleChecker(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.chain_of_thought = dspy.ChainOfThought(CheckTitle)

    def forward(self, title: str) -> dspy.Prediction:
        return self.chain_of_thought(title=title)


def filter_title_with_llm(title: str, title_checker: TitleChecker) -> bool:
    try:
        prediction = title_checker(title)
        return prediction.contains_suggestion, prediction.is_multipack
    except Exception as error:
        print(f"Error processing title '{title}': {error}")
        return False, False


if __name__ == "__main__":
    main()
