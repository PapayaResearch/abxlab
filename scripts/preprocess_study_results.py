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
This script processes the results of the user study to make it ready for analysis in R.
"""

import argparse
import pandas as pd
from pathlib import Path

def clean_rating(s):
    return int(s.strip().replace("%", ""))

def clean_price(s):
    return float(s.strip().replace("$", "").replace(",", ""))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("study_csv", type=Path, help="Path to the study CSV")
    parser.add_argument("results_csv", type=Path, help="Path to the results CSV")

    args = parser.parse_args()

    study = pd.read_csv(args.study_csv)
    results = pd.read_csv(args.results_csv)

    merged = pd.merge(results, study, on="exp", how="inner")

    merged = merged.rename(columns={
        "intervention": "nudge_text",
        "nudge_index": "nudged_idx",
        "exp": "trial_id",
    })

    merged["nudge_trial"] = merged["nudged_idx"] != -1
    merged["chose_idx"] = (merged["choice"] == merged["url_1"]).astype(int)
    merged["model_family"] = "human"
    for i in range(1, 11):
        merged[f"step_{i}.url"] = ""

    r0 = merged["rating_0"].map(clean_rating)
    r1 = merged["rating_1"].map(clean_rating)
    p0 = merged["price_0"].map(clean_price)
    p1 = merged["price_1"].map(clean_price)

    merged["ratings"] = list(map(list, zip(r0, r1)))
    merged["prices"]  = list(map(list, zip(p0, p1)))
    merged["avg_price"]  = sum(p1 + p0) / 2

    merged["better_rated_idx"] = (r1 > r0).astype(int)
    merged["cheaper_idx"] = (p1 < p0).astype(int)

    merged["choose_right"] = merged["choice"] == merged["url_1"]

    out_path = args.study_csv.parent / "study_data_all_regular_results_processed.csv"
    merged.to_csv(out_path, index=False)

if __name__ == "__main__":
    main()
