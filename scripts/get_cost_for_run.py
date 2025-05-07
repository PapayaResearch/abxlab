import os
import json
import argparse
import glob
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results_dir",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results"),
        help="Directory containing the results.",
    )
    args = parser.parse_args()

    results_dir = args.results_dir
    run_summaries = glob.glob(os.path.join(results_dir, "**/*", "summary_info.json"), recursive=True)
    summaries_data = []
    for file in run_summaries:
        with open(file) as json_file:
            data = json.load(json_file)
            summaries_data.append(data)

    df = pd.DataFrame(summaries_data)

    total_inputokens = df["stats.cum_input_tokens"].sum()
    total_outputokens = df["stats.cum_output_tokens"].sum()
    total_cost = df["stats.cum_cost"].sum()

    print("Totals are summed across %d/%d runs" % (len(df[df["stats.cum_input_tokens"] > 0]), len(df)))
    print("Total input tokens: \t\t\t\t %d" % total_inputokens)
    print("Total output tokens: \t\t\t\t %d" % total_outputokens)
    print("\nTotal cost: \t\t\t\t\t $%.2f" % total_cost)


if __name__ == "__main__":
    main()
