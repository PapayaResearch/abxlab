# Copyright (c) 2025
# Chengtian Ma <chengtian.ma@student-cs.fr>
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
import dotenv
dotenv.load_dotenv()
import hydra
from hydra import compose, initialize_config_dir
from hydra.utils import get_original_cwd
from hydra.core.global_hydra import GlobalHydra
from omegaconf import OmegaConf, DictConfig
from nudgelab.browser import NudgeLabBrowserEnv
from nudgelab.task import StaticPageTask
from tqdm import tqdm
import pandas as pd
import multiprocessing
import random
from scripts.page_utils import get_rating_for_product, get_price_for_product

def process_experiment(args):
    fname, cfg_dict, base_conf_path, base_url, output_dir, host_path = args
    exp_name = os.path.splitext(fname)[0]

    # Get cfg information
    GlobalHydra.instance().clear()
    with initialize_config_dir(config_dir=base_conf_path, version_base=None):
        exp_cfg = compose(
            config_name=f"{cfg_dict['study']['experiment_path']}/{exp_name}",
            overrides=[f"+env.wa_shopping_url={cfg_dict['env']['wa_shopping_url']}"]
        )

    start_urls = [url.replace("${env.wa_shopping_url}", base_url)
                  for url in exp_cfg.task.config.start_urls]

    if len(start_urls) <= 1:
        return None

    task = {}
    for idx, url in enumerate(start_urls):
        name = f"{exp_name}_{idx}"

        # Simulate environment
        env = NudgeLabBrowserEnv(
            task_entrypoint=StaticPageTask,
            task_kwargs={
                "url": url,
                "config": exp_cfg.task.config
            },
            headless=True,
        )
        env.reset()

        # Save screenshot
        width = env.page.evaluate("() => document.documentElement.scrollWidth")
        env.page.screenshot(
            path=os.path.join(output_dir, f"{name}.png"),
            full_page=True,
            clip={
                "x": 0,
                "y": 250,
                "width": width,
                "height": 900
            },
            scale="device"
        )

        env.browser.close()
        del env

        task[f"image_{idx}"] = os.path.join(host_path, f"{name}.png")
        task[f"url_{idx}"] = url

    task["exp"] = exp_name
    choices = exp_cfg.task.config.choices
    if choices:
        task["nudge"] = choices[0].nudge
        task["intervention"] = choices[0].functions[0].args.value
        choice_url = choices[0].url.replace("${env.wa_shopping_url}", base_url)
        if choice_url == task["url_0"]:
            task["nudge_index"] = 0
        elif choice_url == task["url_1"]:
            task["nudge_index"] = 1
    else:
        task["nudge_index"] = -1

    return task

def add_extra_metadata(df):
    """Add rating and price information to the dataframe"""
    tqdm.pandas()

    # Get ratings
    df["rating_0"] = df["url_0"].progress_apply(
        get_rating_for_product
    ).str.replace("%", "").astype(int)
    df["rating_1"] = df["url_1"].progress_apply(
        get_rating_for_product
    ).str.replace("%", "").astype(int)

    # Get prices
    df["price_0"] = df["url_0"].progress_apply(
        get_price_for_product
    ).str.replace("$", "").astype(float)
    df["price_1"] = df["url_1"].progress_apply(
        get_price_for_product
    ).str.replace("$", "").astype(float)

    return df

def generate_survey_data(df, seed, output_dir):
    """Generate partitions of the study data"""
    df_grouped = df.groupby(["url_0", "url_1"])

    g1 = []
    g2 = []
    g3 = []
    for _, df_group in tqdm(df_grouped, desc="Generating survey groups"):
        # Shuffling conditions
        shuffled_rows = df_group.sample(frac=1, random_state=seed).reset_index(drop=True)

        g1.append(shuffled_rows.iloc[0].to_dict())
        g2.append(shuffled_rows.iloc[1].to_dict())
        g3.append(shuffled_rows.iloc[2].to_dict())

    pd.DataFrame(g1).to_csv(os.path.join(output_dir, "study_data_1.csv"), index=False)
    pd.DataFrame(g2).to_csv(os.path.join(output_dir, "study_data_2.csv"), index=False)
    pd.DataFrame(g3).to_csv(os.path.join(output_dir, "study_data_3.csv"), index=False)

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg: DictConfig):
    host_path = cfg.study.host
    base_conf_path = os.path.join(get_original_cwd(), "conf")
    experiment_path = os.path.join(base_conf_path, cfg.study.experiment_path)
    base_url = os.getenv("SHOPPING")
    output_dir = cfg.study.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Prepare arguments for multiprocessing
    cfg_dict = OmegaConf.to_container(cfg, resolve=False)
    fnames = [f for f in os.listdir(experiment_path) if f.endswith(".yaml")]
    args = [(fname, cfg_dict, base_conf_path, base_url, output_dir, host_path) for fname in fnames]

    # Use multiprocessing to process experiments
    with multiprocessing.Pool(processes=cfg.study.n_workers) as pool:
        results = list(tqdm(pool.imap_unordered(process_experiment, args), total=len(args)))

    # Filter out None results
    study = [r for r in results if r is not None]

    # Include extra metadata info and save it
    df = add_extra_metadata(pd.DataFrame(study))
    df.to_csv(os.path.join(output_dir, "study_data_all.csv"), index=False)

    # Generate survey data
    generate_survey_data(df, cfg.study.seed, output_dir)

if __name__ == "__main__":
    main()
