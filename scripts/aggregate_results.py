import os
import shutil
import dotenv
import glob
import pandas as pd
import yaml
from datetime import datetime


FILE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv.load_dotenv(os.path.join(FILE_DIR, "../.env"))


def main():
    results_dir = os.path.join(
        FILE_DIR,
        "..",
        os.getenv("AGENTLAB_EXP_ROOT", os.path.join(FILE_DIR, "../results"))
    )
    aggregated_dir = os.path.join(results_dir, "aggregated")
    os.makedirs(aggregated_dir, exist_ok=True)

    study_data = []
    for dir in glob.glob(os.path.join(results_dir, "*/")):
        if not os.path.isdir(dir):
            continue

        with open(os.path.join(dir, "config.yaml"), "r") as yaml_file:
            config = yaml.safe_load(yaml_file)

        study = pd.read_pickle(os.path.join(dir, "study.pkl.gz"))
        study_id = study.uuid.hex
        results, summary, _ = study.get_results()
        results = results.to_dict(orient="records")
        summary = summary.to_dict(orient="records")
        steps = [
            pd.read_pickle(f) for f in glob.glob(os.path.join(dir, "*", "step_*.pkl.gz"))
        ]

        benchmark = study.benchmark.to_dict()

        agent_info = [step.agent_info.__dict__ for step in steps]
        actions = [step.action for step in steps]

        full_results = {
            "study_id": study_id,
            "benchmark": benchmark,
            "config": config,
            "results": results,
            "summary": summary,
            "agent_info": agent_info,
            "actions": actions,
            "dir": os.path.basename(os.path.normpath(dir))
        }

        study_data.append(full_results)

    df = pd.concat(study_data, ignore_index=True)

    datetime_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    aggregated_file = os.path.join(aggregated_dir, "results_%s.parquet" % datetime_str)

    df.to_parquet(aggregated_file, index=False)
    shutil.copyfile(
        aggregated_file,
        os.path.join(aggregated_dir, "results_latest.parquet")
    )


if __name__ == "__main__":
    main()
