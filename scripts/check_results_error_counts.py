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
This script searches in results/ for experiments that have failed.
"""

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
            try:
                summaries.append(json.load(json_file))
            except Exception as error:
                print(f"Error loading {file}: {error}")
                summaries.append({
                    "err_msg": str(error),
                    "stack_trace": str(error),
                    "exp": file.split("/")[-3]
                })
                continue

    df = pd.DataFrame(summaries)
    df["file"] = summary_files
    df["exp"] = df.file.apply(lambda x : x.split("/")[-3])

    df_nem = set(df[df["err_msg"].isna()].exp.tolist())
    df_nst = set(df[df["stack_trace"].isna()].exp.tolist())

    df_em = df[~df["err_msg"].isna()]
    df_st = df[~df["stack_trace"].isna()]

    df_em = df_em[~df_em.exp.isin(df_nem)].err_msg
    df_st = df_st[~df_st.exp.isin(df_nst)].stack_trace

    total_n = len(df.exp.unique())
    print("No error message: %d/%d" % (total_n - len(df_em), total_n))
    print("No stack trace: %d/%d" % (total_n - len(df_st), total_n))

    df_em.to_csv("err_msg.csv", index=False)
    df_st.to_csv("stack_trace.csv", index=False)

    exps_remaining = set(df.exp.unique().tolist()) - (df_nem & df_nst)
    print("\nTotal exps remaining: %d\n" % len(exps_remaining))
    with open("exps_remaining.txt", "w") as outfile:
        outfile.write("\n".join(exps_remaining))


if __name__ == "__main__":
    main()
