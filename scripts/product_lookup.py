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

import argparse
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs_file", default="product_pairs.csv", help="Path to the input product pairs CSV file.")
    parser.add_argument("--products_file", default="products.csv", help="Path to the input products CSV file.")
    parser.add_argument("--column", default="reviews", help="Which column to copy.")
    args = parser.parse_args()

    df_products = pd.read_csv(args.products_file)
    df_pairs = pd.read_csv(args.pairs_file)

    if args.column not in df_products.columns:
        raise ValueError(f"Column '{args.column}' not found in products file.")

    url_cols = [col for col in df_pairs.columns if col.endswith("_url") and col.startswith("product")]
    ref_col = "product_url"
    print(f"Found URL columns: {url_cols}")

    for col in url_cols:
        new_col = col.replace("_url", f"_{args.column}")

        df_pairs[new_col] = df_pairs[col].map(
            df_products.set_index(ref_col)[args.column]
        )

        print(f"Copied {args.column} data from products to {new_col} in pairs")

    output_file = args.pairs_file.replace(".csv", "-withreviews.csv")
    df_pairs.to_csv(output_file, index=False)


if __name__ == "__main__":
    main()
