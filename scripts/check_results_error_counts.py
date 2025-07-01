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
