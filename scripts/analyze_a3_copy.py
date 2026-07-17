#!/usr/bin/env python3
"""Mini-A3 analysis: copy-style (F2) paired contrasts.

Three arms per (pair, focal): control (neutral baseline), data_led, jargon.
Within (model, pair, focal, seed) we compute two paired contrasts against
the shared control, plus the head-to-head:

    data_led - control   (industry's prescription vs the baseline)
    jargon   - control   (the style industry forbids vs the baseline)
    jargon   - data_led  (the H2 showdown)

focal_chosen = the agent carted the focal product (whose copy was varied).

Usage: python scripts/analyze_a3_copy.py [results_glob]
"""

import csv
import glob
import gzip
import json
import os
import pickle
import random
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MANIFEST = "conf/experiment-a3-copy/manifest.csv"
CATALOG_DIR = ("/Users/dambrosm/personal/veliu/code/ecommerce-research/"
               "a1-experiment/catalog/data")


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def focal_slugs():
    """sku -> product-page slug, from the catalog source."""
    m = {}
    for f in glob.glob(f"{CATALOG_DIR}/*.json"):
        for p in json.load(open(f)):
            m[p["sku"]] = slugify(p["title_minimal"])
    return m


def episodes(results_glob):
    for ep_dir in glob.glob(results_glob):
        m = re.search(
            r"GenericAgent-(?P<model>[\w.-]+)_on_abxlab\.(?P<task>dq3-[\w-]+)_(?P<seed>\d+)$",
            ep_dir)
        if not m:
            continue
        try:
            summary = json.load(open(f"{ep_dir}/summary_info.json"))
        except FileNotFoundError:
            continue
        chosen = None
        if summary.get("err_msg") is None and summary.get("cum_reward") == 1.0:
            steps = sorted(glob.glob(f"{ep_dir}/step_*.pkl.gz"))
            if steps:
                with gzip.open(steps[-1], "rb") as f:
                    obs = getattr(pickle.load(f), "obs", None) or {}
                url = obs.get("url", "")
                chosen = url.rstrip("/").split("/")[-1].removesuffix(".html")
        yield {"model": m["model"], "task": m["task"],
               "seed": int(m["seed"]), "chosen_slug": chosen}


def boot_ci(diffs, n=2000, seed=42):
    random.seed(seed)
    bs = sorted(sum(random.choices(diffs, k=len(diffs))) / len(diffs)
                for _ in range(n))
    return bs[int(n * 0.025)], bs[int(n * 0.975)]


def main(results_glob):
    manifest = {r["name"]: r for r in csv.DictReader(open(MANIFEST))}
    slugs = focal_slugs()

    # cell[(model, pair, focal, seed, level)] = focal_chosen
    cell = {}
    n_total = n_choice = 0
    for ep in episodes(results_glob):
        meta = manifest.get(ep["task"])
        if meta is None:
            continue
        n_total += 1
        if not ep["chosen_slug"]:
            continue
        n_choice += 1
        focal_chosen = ep["chosen_slug"] == slugs[meta["focal_sku"]]
        cell[(ep["model"], meta["pair_id"], meta["focal"], ep["seed"],
              meta["level"])] = int(focal_chosen)

    print(f"episodes matched: {n_total}; with definite choice: {n_choice}")

    models = sorted({k[0] for k in cell})
    print("\nfocal-choice rate by model x level:")
    agg = defaultdict(lambda: [0, 0])
    for (model, *_ , level), v in ((k, v) for k, v in cell.items()):
        agg[(model, level)][0] += v
        agg[(model, level)][1] += 1
    for (model, level), (hits, tot) in sorted(agg.items()):
        print(f"  {model:22s} {level:9s} {hits:3d}/{tot:3d} = {hits/tot:.1%}")

    contrasts = [("data_led", "control"), ("jargon", "control"),
                 ("jargon", "data_led")]
    print("\npaired contrasts (mean diff, 95% bootstrap CI):")
    for model in models:
        keys = {(p, f, s) for (m, p, f, s, l) in cell if m == model}
        for hi, lo in contrasts:
            diffs = []
            for (p, f, s) in keys:
                a = cell.get((model, p, f, s, hi))
                b = cell.get((model, p, f, s, lo))
                if a is not None and b is not None:
                    diffs.append(a - b)
            if not diffs:
                continue
            mean = sum(diffs) / len(diffs)
            lo_ci, hi_ci = boot_ci(diffs)
            print(f"  {model:22s} {hi:9s} - {lo:9s}: {mean:+.3f} "
                  f"[{lo_ci:+.3f}, {hi_ci:+.3f}]  n={len(diffs)}")
    print("\nReading: positive 'jargon - data_led' = marketing copy BEATS "
          "data-led copy (industry advice backwards for agents).")


if __name__ == "__main__":
    g = sys.argv[1] if len(sys.argv) > 1 else "results/run-*/dq3-*/2026-*"
    main(g)
