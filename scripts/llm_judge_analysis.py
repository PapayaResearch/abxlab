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

class MentionsAnalysis(dspy.Signature):
    """Analyze what factors are mentioned in thinking and memory data."""

    thinking: str = dspy.InputField(desc="The user's thinking process")
    memory: str = dspy.InputField(desc="The user's memory/notes")
    nudge: str = dspy.InputField(desc="The nudge value shown to user")

    mentions: str = dspy.OutputField(desc="JSON with boolean fields for price, rating, nudge, other indicating what was mentioned")

class DecidingFactorAnalysis(dspy.Signature):
    """Determine the main deciding factor from thinking and memory data."""

    thinking: str = dspy.InputField(desc="The user's thinking process")
    memory: str = dspy.InputField(desc="The user's memory/notes")
    nudge: str = dspy.InputField(desc="The nudge value shown to user")

    decision: str = dspy.OutputField(desc="JSON with 'reason' (price/rating/nudge/other) and 'justification' fields")

def analyze_mentions(all_think, all_memory, nudge_value):
    predictor = dspy.Predict(MentionsAnalysis)
    try:
        result = predictor(
            thinking=all_think,
            memory=all_memory,
            nudge=str(nudge_value)
        )
        content = result.mentions.strip()
        try:
            parsed_result = json.loads(content)
        except Exception:
            import re
            json_strs = re.findall(r"\{.*\}", content, flags=re.DOTALL)
            if json_strs:
                parsed_result = json.loads(json_strs[0])
            else:
                parsed_result = {"price": False, "rating": False, "nudge": False, "other": False, "error": f"Could not parse JSON: {content}"}

        for key in ["price", "rating", "nudge", "other"]:
            if key not in parsed_result:
                parsed_result[key] = False

        return parsed_result
    except Exception as e:
        return {"price": False, "rating": False, "nudge": False, "other": False, "error": str(e)}

def analyze_deciding_factor(all_think, all_memory, nudge_value):
    predictor = dspy.Predict(DecidingFactorAnalysis)
    try:
        result = predictor(
            thinking=all_think,
            memory=all_memory,
            nudge=str(nudge_value)
        )
        content = result.decision.strip()
        try:
            parsed_result = json.loads(content)
        except Exception:
            import re
            json_strs = re.findall(r"\{.*\}", content, flags=re.DOTALL)
            if json_strs:
                parsed_result = json.loads(json_strs[0])
            else:
                parsed_result = {"reason": "error", "justification": f"Could not parse JSON: {content}"}
        if parsed_result.get("reason") not in ["price", "rating", "nudge", "other"]:
            parsed_result["reason"] = "other"
        return parsed_result
    except Exception as e:
        return {"reason": "error", "justification": str(e)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", help="Path to input CSV file with aggregated results")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--max_workers", type=int, default=4)
    args = parser.parse_args()

    dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env"))

    dspy.configure(lm=dspy.LM(model=args.model, max_tokens=256, temperature=0))

    df = pd.read_csv(args.csv)
    df["all_think"] = combine_columns(df, "think")
    df["all_memory"] = combine_columns(df, "memory")

    def process_mentions(row):
        choices = ast.literal_eval(row["cfg.task.config.choices"])
        if len(choices) > 0 and choices[0]["nudge"] != "Matching Price":
            nudge = choices[0]["functions"][0]["args"]
        else:
            nudge = None
        return analyze_mentions(
            row["all_think"],
            row["all_memory"],
            nudge
        )

    def process_deciding_factor(row):
        choices = ast.literal_eval(row["cfg.task.config.choices"])
        if len(choices) > 0 and choices[0]["nudge"] != "Matching Price":
            nudge = choices[0]["functions"][0]["args"]
        else:
            nudge = None
        return analyze_deciding_factor(
            row["all_think"],
            row["all_memory"],
            nudge
        )

    rows = df.to_dict("records")

    # Study what is mentioned in the thinking and memory
    print("Analyzing mentions...")
    results_mentions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        for result in tqdm(
                executor.map(process_mentions, rows),
                total=len(rows),
                desc="Mentions analysis"
        ):
            results_mentions.append(result)

    # Study the reason for the decision based on the thinking and memory
    print("\nAnalyzing deciding factors...")
    results_reasons = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        for result in tqdm(
                executor.map(process_deciding_factor, rows),
                total=len(rows),
                desc="Deciding factor analysis"
        ):
            results_reasons.append(result)

    # Print mentions stats
    print("\nMentions Analysis:")
    mention_counts = {"price": 0, "rating": 0, "nudge": 0, "other": 0}
    for result in results_mentions:
        for factor in mention_counts.keys():
            if result.get(factor, False):
                mention_counts[factor] += 1

    total_rows = len(results_mentions)
    for factor, count in mention_counts.items():
        percentage = (count / total_rows) * 100 if total_rows > 0 else 0
        print(f"{factor}: {count} ({percentage:.1f}%)")

    # Print deciding factor stats
    print("\nDeciding Factor Analysis:")
    reason_counts = Counter(res.get("reason", "error") for res in results_reasons)
    for reason, count in reason_counts.items():
        percentage = (count / total_rows) * 100 if total_rows > 0 else 0
        print(f"{reason}: {count} ({percentage:.1f}%)")

    # Save detailed results
    output_file = args.csv.replace('.csv', '_analysis.json')
    detailed_results = {
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
