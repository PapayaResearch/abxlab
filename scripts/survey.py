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
import pandas as pd
import random
from tqdm import tqdm

SEED = 42
OUTPUT_DIR = "study"

def generate_survey_data(df, seed, output_dir):
    df_grouped = df.groupby(["url_0", "url_1"])

    g1 = []
    g2 = []
    g3 = []
    for _, df_group in tqdm(df_grouped):
        # Shuffle rows
        shuffled_rows = df_group.sample(frac=1, random_state=seed).reset_index(drop=True)

        # Assign one row to each group
        g1.append(shuffled_rows.iloc[0].to_dict())
        g2.append(shuffled_rows.iloc[1].to_dict())
        g3.append(shuffled_rows.iloc[2].to_dict())

    # Save to CSV
    pd.DataFrame(g1).to_csv(os.path.join(output_dir, "study_1.csv"), index=False)
    pd.DataFrame(g2).to_csv(os.path.join(output_dir, "study_2.csv"), index=False)
    pd.DataFrame(g3).to_csv(os.path.join(output_dir, "study_3.csv"), index=False)

def main():
    parser = argparse.ArgumentParser(description="Generate CSVs for Qualtrics survey.")
    parser.add_argument("--csv", type=str, required=True, help="Path to the CSV file.")
    parser.add_argument("--seed", type=int, help="Seed.", default=SEED)
    parser.add_argument("--output-dir", type=str, help="Output directory.", default=OUTPUT_DIR)
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    generate_survey_data(df, args.seed, args.output_dir)

if __name__ == "__main__":
    main()
