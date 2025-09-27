import random
import argparse
import multiprocessing
import functools
import pandas as pd
import numpy as np
from tqdm import tqdm
from itertools import combinations
from select_product_pairs import filter_products_chunk


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", default="products.csv", help="Path to the input products CSV file.")
    parser.add_argument("--output_file", default="product_pairs.csv", help="Path to the output CSV file for product pairs.")
    parser.add_argument("--k_products", type=int, default=50, help="Number of products to sample from each selected category.")
    parser.add_argument("--min_products_per_category", type=int, default=20, help="Minimum products required in a category to consider it.")
    parser.add_argument("--max_categories", type=int, default=100, help="Maximum number of categories to select (best coverage first).")
    parser.add_argument("--coverage_bins", type=int, default=10, help="Number of bins to use for coverage analysis.")
    parser.add_argument("--price_tolerance_pct", type=float, default=0.10, help="Price tolerance percentage for rating coverage pairs (default: 10%).")
    parser.add_argument("--rating_tolerance_pct", type=float, default=0.0, help="Rating tolerance percentage for price coverage pairs (default: 0%).")
    parser.add_argument("--use_llm_filter", action="store_true", help="Enable LLM-based title filtering.")
    parser.add_argument("--llm_model", default="gpt-4.1-nano", help="LLM model to use for filtering.")
    parser.add_argument("--num_workers", type=int, default=multiprocessing.cpu_count(), help="Number of parallel processes to use.")
    parser.add_argument("--random_seed", type=int, default=42, help="Random seed for reproducibility.")
    args = parser.parse_args()

    # Set random seed for reproducibility
    random.seed(args.random_seed)
    np.random.seed(args.random_seed)

    # Load and preprocess data
    df = load_and_preprocess_data(args)

    print(f"Analyzing {len(df)} products across {df['category'].nunique()} categories...")

    # Create discrete coverage sampler
    sampler = DiscreteCoverageSampler(
        k_products=args.k_products,
        min_products_per_category=args.min_products_per_category,
        max_categories=args.max_categories,
        coverage_bins=args.coverage_bins,
        price_tolerance_pct=args.price_tolerance_pct,
        rating_tolerance_pct=args.rating_tolerance_pct
    )

    # Generate pairs using discrete coverage sampling
    price_pairs, rating_pairs = sampler.generate_discrete_coverage_pairs(df)

    print(f"Generated {len(price_pairs)} price coverage pairs and {len(rating_pairs)} rating coverage pairs.")

    # Convert to DataFrame and save
    output_df = create_output_dataframe(price_pairs, rating_pairs)
    output_df.to_csv(args.output_file, index=False)

    print(f"Saved {len(output_df)} total product pairs to {args.output_file}")
    
    # Print statistics
    sampler.print_coverage_stats(output_df)


def load_and_preprocess_data(args) -> pd.DataFrame:
    """Load and preprocess the product data."""
    df = pd.read_csv(args.input_file)
    df.dropna(subset=["rating", "price"], inplace=True)
    
    # Robust rating parsing
    df["rating"] = pd.to_numeric(df["rating"].astype(str).str.replace("%", "", regex=False), errors="coerce")
    df = df.dropna(subset=["rating"])
    df = df[df["rating"] > 0]

    # LLM Filtering
    if args.use_llm_filter:
        print("Filtering products with LLM...")
        n_workers = max(1, min(args.num_workers, len(df)))
        chunks = [chunk for chunk in np.array_split(df, n_workers) if not chunk.empty]
        with multiprocessing.Pool(processes=n_workers) as pool:
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

    # Clean price data
    df["price"] = pd.to_numeric(
        df["price"].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False),
        errors="coerce"
    )
    df = df.dropna(subset=["price"])
    df = df[~df["has_options"]]
    
    return df


def create_output_dataframe(price_pairs, rating_pairs) -> pd.DataFrame:
    """Convert pairs to output DataFrame format."""
    pair_records = []
    
    # Process price coverage pairs
    for p1, p2, pair_info in price_pairs:
        pair_records.append(_create_pair_record(p1, p2, pair_info, "price_coverage"))
    
    # Process rating coverage pairs
    for p1, p2, pair_info in rating_pairs:
        pair_records.append(_create_pair_record(p1, p2, pair_info, "rating_coverage"))
    
    return pd.DataFrame(pair_records)


def _create_pair_record(p1, p2, pair_info, coverage_type):
    """Create a single pair record."""
    return {
        "coverage_type": coverage_type,
        "category": p1["category"],
        "coverage_score": pair_info["coverage_score"],
        "product1_name": p1["product_name"],
        "product1_url": p1["product_url"],
        "product1_price": p1["price"],
        "product1_rating": p1["rating"],
        "product2_name": p2["product_name"],
        "product2_url": p2["product_url"],
        "product2_price": p2["price"],
        "product2_rating": p2["rating"],
        "product1_reviews": p1["reviews"],
        "product2_reviews": p2["reviews"],
        "price_difference": abs(p1["price"] - p2["price"]),
        "rating_difference": abs(p1["rating"] - p2["rating"]),
        "price_difference_pct": abs(p1["price"] - p2["price"]) / max(p1["price"], p2["price"]),
        "rating_difference_pct": abs(p1["rating"] - p2["rating"]) / max(p1["rating"], p2["rating"]) if max(p1["rating"], p2["rating"]) > 0 else 0
    }


class DiscreteCoverageSampler:
    """Samples products to create discrete price and rating coverage sets."""
    
    def __init__(self, k_products: int, min_products_per_category: int, max_categories: int, 
                 coverage_bins: int, price_tolerance_pct: float, rating_tolerance_pct: float):
        self.k_products = k_products
        self.min_products_per_category = min_products_per_category
        self.max_categories = max_categories
        self.coverage_bins = coverage_bins
        self.price_tolerance_pct = price_tolerance_pct
        self.rating_tolerance_pct = rating_tolerance_pct

    def generate_discrete_coverage_pairs(self, df: pd.DataFrame) -> tuple[list, list]:
        """Generate two discrete sets of pairs: price coverage and rating coverage."""
        
        # Step 1: Find categories with best price coverage
        price_categories = self._select_best_price_coverage_categories(df)
        
        # Step 2: Find categories with best rating coverage
        rating_categories = self._select_best_rating_coverage_categories(df)
        
        print(f"Selected {len(price_categories)} categories for price coverage:")
        for cat_info in price_categories:
            print(f"  {cat_info["category"]}: {cat_info["price_coverage_score"]:.2f} price coverage, "
                  f"price range ${cat_info["price_range"][0]:.2f}-${cat_info["price_range"][1]:.2f}")
        
        print(f"Selected {len(rating_categories)} categories for rating coverage:")
        for cat_info in rating_categories:
            print(f"  {cat_info["category"]}: {cat_info["rating_coverage_score"]:.2f} rating coverage, "
                  f"rating range {cat_info["rating_range"][0]:.1f}%-{cat_info["rating_range"][1]:.1f}%")
        
        # Step 3: Generate price coverage pairs
        price_pairs = self._generate_price_coverage_pairs(df, price_categories)
        
        # Step 4: Generate rating coverage pairs
        rating_pairs = self._generate_rating_coverage_pairs(df, rating_categories)
        
        return price_pairs, rating_pairs
    
    def _select_best_price_coverage_categories(self, df: pd.DataFrame) -> list[dict]:
        """Select categories with the best price coverage."""
        category_counts = df.groupby("category").size()
        valid_categories = category_counts[category_counts >= self.min_products_per_category].index
        
        category_scores = []
        
        for category in valid_categories:
            category_df = df[df["category"] == category]
            price_coverage_score = self._calculate_price_coverage_score(category_df)
            
            category_info = {
                "category": category,
                "price_coverage_score": price_coverage_score,
                "product_count": len(category_df),
                "price_range": (category_df["price"].min(), category_df["price"].max()),
                "rating_range": (category_df["rating"].min(), category_df["rating"].max())
            }
            category_scores.append(category_info)
        
        # Sort by price coverage score (descending) and select top categories
        category_scores.sort(key=lambda x: x["price_coverage_score"], reverse=True)
        return category_scores[:self.max_categories]
    
    def _select_best_rating_coverage_categories(self, df: pd.DataFrame) -> list[dict]:
        """Select categories with the best rating coverage."""
        category_counts = df.groupby("category").size()
        valid_categories = category_counts[category_counts >= self.min_products_per_category].index
        
        category_scores = []
        
        for category in valid_categories:
            category_df = df[df["category"] == category]
            rating_coverage_score = self._calculate_rating_coverage_score(category_df)
            
            category_info = {
                "category": category,
                "rating_coverage_score": rating_coverage_score,
                "product_count": len(category_df),
                "price_range": (category_df["price"].min(), category_df["price"].max()),
                "rating_range": (category_df["rating"].min(), category_df["rating"].max())
            }
            category_scores.append(category_info)
        
        # Sort by rating coverage score (descending) and select top categories
        category_scores.sort(key=lambda x: x["rating_coverage_score"], reverse=True)
        return category_scores[:self.max_categories]
    
    def _calculate_price_coverage_score(self, category_df: pd.DataFrame) -> float:
        """Calculate how well a category covers the price range."""
        if len(category_df) < self.coverage_bins:
            return 0.0
        
        price_min, price_max = category_df["price"].min(), category_df["price"].max()
        
        if price_max == price_min:
            return 0.0
        
        # Create price bins
        price_bins = np.linspace(price_min, price_max, self.coverage_bins + 1)
        
        # Count filled bins
        filled_bins = 0
        for i in range(self.coverage_bins):
            bin_cond = (category_df["price"] >= price_bins[i]) & (category_df["price"] < price_bins[i + 1])
            if i == self.coverage_bins - 1:  # Handle last bin inclusively
                bin_cond = (category_df["price"] >= price_bins[i]) & (category_df["price"] <= price_bins[i + 1])
            
            if bin_cond.any():
                filled_bins += 1
        
        coverage_ratio = filled_bins / self.coverage_bins
        
        # Bonus for good price range spread
        price_cv = (price_max - price_min) / price_min if price_min > 0 else 0
        score = coverage_ratio + 0.2 * min(price_cv, 2.0)
        
        return score
    
    def _calculate_rating_coverage_score(self, category_df: pd.DataFrame) -> float:
        """Calculate how well a category covers the rating range."""
        if len(category_df) < self.coverage_bins:
            return 0.0
        
        rating_min, rating_max = category_df["rating"].min(), category_df["rating"].max()
        
        if rating_max == rating_min:
            return 0.0
        
        # Create rating bins
        rating_bins = np.linspace(rating_min, rating_max, self.coverage_bins + 1)
        
        # Count filled bins
        filled_bins = 0
        for i in range(self.coverage_bins):
            bin_cond = (category_df["rating"] >= rating_bins[i]) & (category_df["rating"] < rating_bins[i + 1])
            if i == self.coverage_bins - 1:  # Handle last bin inclusively
                bin_cond = (category_df["rating"] >= rating_bins[i]) & (category_df["rating"] <= rating_bins[i + 1])
            
            if bin_cond.any():
                filled_bins += 1
        
        coverage_ratio = filled_bins / self.coverage_bins
        
        # Bonus for good rating range spread
        rating_cv = (rating_max - rating_min) / rating_min if rating_min > 0 else 0
        score = coverage_ratio + 0.2 * min(rating_cv, 2.0)
        
        return score
    
    def _generate_price_coverage_pairs(self, df: pd.DataFrame, price_categories: list[dict]) -> list[tuple[dict, dict, dict]]:
        """Generate price coverage pairs with exact rating matching (0% tolerance)."""
        all_pairs = []
        
        for cat_info in price_categories:
            category = cat_info["category"]
            category_df = df[df["category"] == category]
            
            # Sample k products across price range
            sampled_products = self._sample_k_products_for_price_coverage(category_df, cat_info)
            
            print(f"Sampled {len(sampled_products)} products from {category} for price coverage")
            
            # Generate pairs with exact rating matching
            category_pairs = self._generate_price_pairs_with_rating_constraint(sampled_products, cat_info)
            all_pairs.extend(category_pairs)
            
            print(f"Generated {len(category_pairs)} price coverage pairs from {category}")
        
        return all_pairs
    
    def _generate_rating_coverage_pairs(self, df: pd.DataFrame, rating_categories: list[dict]) -> list[tuple[dict, dict, dict]]:
        """Generate rating coverage pairs with price matching within 10% tolerance."""
        all_pairs = []
        
        for cat_info in rating_categories:
            category = cat_info["category"]
            category_df = df[df["category"] == category]
            
            # Sample k products across rating range
            sampled_products = self._sample_k_products_for_rating_coverage(category_df, cat_info)
            
            print(f"Sampled {len(sampled_products)} products from {category} for rating coverage")
            
            # Generate pairs with price matching constraint
            category_pairs = self._generate_rating_pairs_with_price_constraint(sampled_products, cat_info)
            all_pairs.extend(category_pairs)
            
            print(f"Generated {len(category_pairs)} rating coverage pairs from {category}")
        
        return all_pairs
    
    def _sample_k_products_for_price_coverage(self, category_df: pd.DataFrame, cat_info: dict) -> list[dict]:
        """Sample k products that maximize price range coverage."""
        if len(category_df) <= self.k_products:
            return category_df.to_dict("records")
        
        price_min, price_max = cat_info["price_range"]
        price_bins = np.linspace(price_min, price_max, self.k_products)
        
        sampled_products = []
        
        # Try to get one product from each price percentile
        for i, target_price in enumerate(price_bins):
            # Find closest product to this target price
            price_distances = np.abs(category_df["price"] - target_price)
            closest_idx = price_distances.idxmin()
            
            # Avoid duplicates
            if closest_idx not in [p.get("original_index") for p in sampled_products]:
                product = category_df.loc[closest_idx].to_dict()
                product["original_index"] = closest_idx
                sampled_products.append(product)
        
        return sampled_products[:self.k_products]
    
    def _sample_k_products_for_rating_coverage(self, category_df: pd.DataFrame, cat_info: dict) -> list[dict]:
        """Sample k products that maximize rating range coverage."""
        if len(category_df) <= self.k_products:
            return category_df.to_dict("records")
        
        rating_min, rating_max = cat_info["rating_range"]
        rating_bins = np.linspace(rating_min, rating_max, self.k_products)
        
        sampled_products = []
        
        # Try to get one product from each rating percentile
        for i, target_rating in enumerate(rating_bins):
            # Find closest product to this target rating
            rating_distances = np.abs(category_df["rating"] - target_rating)
            closest_idx = rating_distances.idxmin()
            
            # Avoid duplicates
            if closest_idx not in [p.get("original_index") for p in sampled_products]:
                product = category_df.loc[closest_idx].to_dict()
                product["original_index"] = closest_idx
                sampled_products.append(product)
        
        return sampled_products[:self.k_products]
    
    def _generate_price_pairs_with_rating_constraint(self, products: list[dict], cat_info: dict) -> list[tuple[dict, dict, dict]]:
        """Generate pairs for price coverage with exact rating matching (0% tolerance)."""
        pairs = []
        
        for p1, p2 in combinations(products, 2):
            if p1["product_url"] != p2["product_url"]:
                # Check rating constraint (exact match within tolerance)
                rating_diff_pct = abs(p1["rating"] - p2["rating"]) / max(p1["rating"], p2["rating"]) if max(p1["rating"], p2["rating"]) > 0 else 0
                
                if rating_diff_pct <= self.rating_tolerance_pct:
                    pair_info = {
                        "coverage_score": cat_info["price_coverage_score"],
                        "constraint_met": True,
                        "rating_diff_pct": rating_diff_pct
                    }
                    pairs.append((p1, p2, pair_info))
        
        return pairs
    
    def _generate_rating_pairs_with_price_constraint(self, products: list[dict], cat_info: dict) -> list[tuple[dict, dict, dict]]:
        """Generate pairs for rating coverage with price matching within 10% tolerance."""
        pairs = []
        
        for p1, p2 in combinations(products, 2):
            if p1["product_url"] != p2["product_url"]:
                # Check price constraint (within tolerance)
                price_diff_pct = abs(p1["price"] - p2["price"]) / max(p1["price"], p2["price"])
                
                if price_diff_pct <= self.price_tolerance_pct:
                    pair_info = {
                        "coverage_score": cat_info["rating_coverage_score"],
                        "constraint_met": True,
                        "price_diff_pct": price_diff_pct
                    }
                    pairs.append((p1, p2, pair_info))
        
        return pairs
    
    def print_coverage_stats(self, output_df: pd.DataFrame) -> None:
        """Print statistics about the discrete coverage sampling results."""
        print("\n=== Discrete Coverage Sampling Statistics ===")
        if output_df.empty:
            print("No pairs generated.")
            return
        
        # Split by coverage type
        price_pairs = output_df[output_df["coverage_type"] == "price_coverage"]
        rating_pairs = output_df[output_df["coverage_type"] == "rating_coverage"]
        
        print(f"Price coverage pairs: {len(price_pairs)}")
        print(f"Rating coverage pairs: {len(rating_pairs)}")
        print(f"Total pairs: {len(output_df)}")
        
        if len(price_pairs) > 0:
            print(f"\n=== Price Coverage Pairs ===")
            print(f"Categories: {price_pairs["category"].nunique()}")
            print(f"Average price difference: ${price_pairs["price_difference"].mean():.2f}")
            print(f"Max price difference: ${price_pairs["price_difference"].max():.2f}")
            print(f"Average rating difference: {price_pairs["rating_difference"].mean():.2f}%")
            print(f"Max rating difference: {price_pairs["rating_difference"].max():.2f}% (should be ~0%)")
        
        if len(rating_pairs) > 0:
            print(f"\n=== Rating Coverage Pairs ===")
            print(f"Categories: {rating_pairs["category"].nunique()}")
            print(f"Average rating difference: {rating_pairs["rating_difference"].mean():.2f}%")
            print(f"Max rating difference: {rating_pairs["rating_difference"].max():.2f}%")
            print(f"Average price difference: ${rating_pairs["price_difference"].mean():.2f}")
            print(f"Max price difference pct: {rating_pairs["price_difference_pct"].max()*100:.1f}% (should be ≤10%)")


if __name__ == "__main__":
    main()
