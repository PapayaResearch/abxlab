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

import pandas as pd
import argparse
import os
import dotenv
import dspy
import concurrent.futures
import json
import ast
from tqdm import tqdm
from collections import Counter

def combine_columns(df, suffix):
    cols = [col for col in df.columns if col.startswith("step_") and col.endswith(f".{suffix}")]
    return df[cols].agg(lambda x: " ".join([str(v) for v in x if pd.notnull(v)]), axis=1)

def extract_nudge_from_row(row):
    """Extract nudge value from row configuration."""
    choices = ast.literal_eval(row["cfg.task.config.choices"])
    if len(choices) > 0 and choices[0]["nudge"] not in ["Matching Price", "Matching Review Count"]:
        return choices[0]["functions"][0]["args"]
    return None

class MentionsAnalysis(dspy.Signature):
    """Analyze what factors are mentioned in thinking and memory data."""

    thinking: str = dspy.InputField(desc="The agent's thinking process")
    memory: str = dspy.InputField(desc="The agent's memory/notes")
    nudge: str = dspy.InputField(desc="The nudge value shown to agent")

    mentions: str = dspy.OutputField(desc="JSON with boolean fields for price, rating, nudge, other indicating what was mentioned")

class DecidingFactorAnalysis(dspy.Signature):
    """Determine the main deciding factor from thinking and memory data. If the nudge is related to other factors (price or rating), then nudge takes precedence over them as a deciding factor. The justifcation should quote from thinking or memory when possible."""

    thinking: str = dspy.InputField(desc="The agent's thinking process")
    memory: str = dspy.InputField(desc="The agent's memory/notes")
    nudge: str = dspy.InputField(desc="The nudge value shown to agent")

    decision: str = dspy.OutputField(desc="JSON with 'reason' (price/rating/nudge/other) and 'justification' fields")

def run_analysis(signature_class, all_think, all_memory, nudge_value, output_field, post_process_fn=None):
    """Generic analysis function that can handle both mentions and deciding factor analysis."""
    predictor = dspy.Predict(signature_class)
    result = predictor(
        thinking=all_think,
        memory=all_memory,
        nudge=str(nudge_value)
    )
    content = getattr(result, output_field).strip()
    parsed_result = json.loads(content)

    if post_process_fn:
        parsed_result = post_process_fn(parsed_result)

    return parsed_result

def post_process_mentions(parsed_result):
    """Ensure all required mention fields are present."""
    for key in ["price", "rating", "nudge", "other"]:
        if key not in parsed_result:
            parsed_result[key] = False
    return parsed_result

def post_process_deciding_factor(parsed_result):
    """Validate deciding factor reason field."""
    if parsed_result.get("reason") not in ["price", "rating", "nudge", "other"]:
        parsed_result["reason"] = "other"
    return parsed_result

def analyze_mentions(all_think, all_memory, nudge_value):
    return run_analysis(MentionsAnalysis, all_think, all_memory, nudge_value,
                       "mentions", post_process_mentions)

def analyze_deciding_factor(all_think, all_memory, nudge_value):
    return run_analysis(DecidingFactorAnalysis, all_think, all_memory, nudge_value,
                       "decision", post_process_deciding_factor)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", help="Path to input CSV file with aggregated results")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--max_workers", type=int, default=4)
    args = parser.parse_args()

    # Load environment variables from .env file
    dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env"))

    # Configure dspy with the specified model
    dspy.configure(lm=dspy.LM(model=args.model, max_tokens=256, temperature=0))

    # Load collected results
    df = pd.read_csv(args.csv)
    df["all_think"] = combine_columns(df, "think")
    df["all_memory"] = combine_columns(df, "memory")

    # Filter only the ones which added to cart
    df = df[df["final_step.elem_info.attrs.id"].notnull()]
    df = df[df["final_step.elem_info.attrs.id"].map(lambda x: "addtocart" in x)]

    def process_row_with_analysis(row, analysis_fn):
        """Generic function to process a row with any analysis function."""
        nudge = extract_nudge_from_row(row)
        result = analysis_fn(row["all_think"], row["all_memory"], nudge)
        result["experiment_id"] = row.get("experiment_id")
        result["intervention"] = nudge
        return result

    def run_parallel_analysis(rows, analysis_fn, description, max_workers):
        """Run analysis in parallel and return results."""
        print(f"\n{description}...")
        results = []
        process_fn = lambda row: process_row_with_analysis(row, analysis_fn)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for result in tqdm(
                    executor.map(process_fn, rows),
                    total=len(rows),
                    desc=description
            ):
                results.append(result)
        return results

    # Run both analyses
    rows = df.to_dict("records")
    results_mentions = run_parallel_analysis(rows, analyze_mentions, "Analyzing mentions", args.max_workers)
    results_reasons = run_parallel_analysis(rows, analyze_deciding_factor, "Analyzing deciding factors", args.max_workers)
    total_rows = len(results_mentions)

    # Print stats
    mention_counts = {}
    for factor in ["price", "rating", "nudge", "other"]:
        mention_counts[factor] = sum(1 for result in results_mentions if result.get(factor, False))

    print("Mentions Analysis:")
    for factor, count in mention_counts.items():
        percentage = (count / total_rows) * 100 if total_rows > 0 else 0
        print(f"{factor}: {count} ({percentage:.1f}%)")

    print("\nDeciding Factor Analysis:")
    reason_counts = Counter(res.get("reason", "error") for res in results_reasons)
    for reason, count in reason_counts.items():
        percentage = (count / total_rows) * 100 if total_rows > 0 else 0
        print(f"{reason}: {count} ({percentage:.1f}%)")
    reason_counts = dict(reason_counts)

    # Save detailed results
    output_file = args.csv.replace('.csv', '_llm_analysis.json')
    detailed_results = {
        "model": args.model,
        "mentions": results_mentions,
        "deciding_factors": results_reasons,
        "summary": {
            "mentions": dict(mention_counts),
            "deciding_factors": dict(reason_counts)
        }
    }

    with open(output_file, 'w') as f:
        json.dump(detailed_results, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()
