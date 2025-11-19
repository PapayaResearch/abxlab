#!/usr/bin/env python3

import argparse
import csv
import json
import os
import re
from collections import defaultdict

FACTORS = ["rating", "price", "nudge", "other"]

MODEL_FILENAME_RE = re.compile(
    r"aggregated_results-(?P<model>.*?)_llm_analysis\.json$", re.IGNORECASE
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Aggregate LLM mentions and deciding factors from JSON files."
    )
    parser.add_argument("top_dir", help="Top directory with setup subdirectories.")
    parser.add_argument(
        "-o",
        "--output",
        default="judge_results.csv",
        help="Output CSV file path (default: judge_results.csv)",
    )
    return parser.parse_args()


def extract_model_from_filename(filename: str):
    match = MODEL_FILENAME_RE.match(filename)
    return match.group("model") if match else None


def get_setup_name(top_dir: str, dirpath: str) -> str:
    rel = os.path.relpath(dirpath, top_dir)
    return "" if rel == "." else rel.split(os.sep)[0]


def aggregate_from_json(data, agg_entry):
    mentions = data.get("mentions", []) or []
    deciding_factors = data.get("deciding_factors", []) or []

    # Count how many mention entries (i.e., experiments with mentions)
    agg_entry["n_mentions"] += len(mentions)

    # Count how many deciding_factors entries (i.e., experiments with decisions)
    agg_entry["n_deciding"] += len(deciding_factors)

    # Factor-level counts for mentions
    for mention in mentions:
        for factor in FACTORS:
            if mention.get(factor):
                agg_entry[f"mentions_{factor}"] += 1

    # Factor-level counts for deciding factors
    for dec in deciding_factors:
        for reason in dec.get("reasons", []) or []:
            if reason in FACTORS:
                agg_entry[f"deciding_{reason}"] += 1


def main():
    args = parse_args()
    top_dir = os.path.abspath(args.top_dir)
    aggregates = defaultdict(lambda: defaultdict(int))

    for dirpath, _, filenames in os.walk(top_dir):
        setup = get_setup_name(top_dir, dirpath)
        if setup == "":
            continue

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Determine model name
            model = (
                extract_model_from_filename(filename)
                or data.get("model")
                or os.path.splitext(filename)[0]
            )

            key = (setup, model)
            agg_entry = aggregates[key]

            aggregate_from_json(data, agg_entry)

    # ---- CSV fields ----
    fieldnames = (
        ["setup", "model"]
        + ["n_mentions"]
        + [f"mentions_{f}" for f in FACTORS]
        + ["n_deciding"]
        + [f"deciding_{f}" for f in FACTORS]
    )

    with open(args.output, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for (setup, model) in sorted(aggregates.keys()):
            agg_entry = aggregates[(setup, model)]

            row = {
                "setup": setup,
                "model": model,
                "n_mentions": agg_entry.get("n_mentions", 0),
                "n_deciding": agg_entry.get("n_deciding", 0),
            }

            for factor in FACTORS:
                row[f"mentions_{factor}"] = agg_entry.get(f"mentions_{factor}", 0)
                row[f"deciding_{factor}"] = agg_entry.get(f"deciding_{factor}", 0)

            writer.writerow(row)

    print(f"CSV written to {args.output}")


if __name__ == "__main__":
    main()
