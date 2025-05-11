import os
import dotenv
import glob
import json
import pandas as pd
from tqdm.auto import tqdm


FILE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv.load_dotenv(os.path.join(FILE_DIR, "../.env"))


def main():
    results_dir = os.path.join(
        FILE_DIR,
        "..",
        os.getenv("AGENTLAB_EXP_ROOT", os.path.join(FILE_DIR, "../results"))
    )

    summary_files = glob.glob(
        os.path.join(
            results_dir,
            "**",
            "*",
            "summary_info.json"
        ),
        recursive=True
    )

    summaries = []
    for file in tqdm(summary_files):
        with open(file) as json_file:
            summaries.append(json.load(json_file))

    df = pd.DataFrame(summaries)
    print(df["err_msg"].isna().value_counts())
    print(df["stack_trace"].isna().value_counts())

    df.loc[~df["err_msg"].isna(), "err_msg"].to_csv("err_msg.csv", index=False)
    df.loc[~df["stack_trace"].isna(), "stack_trace"].to_csv("stack_trace.csv", index=False)


if __name__ == "__main__":
    main()
