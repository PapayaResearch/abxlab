#!/usr/bin/env python3
"""A1 mini-pilot analysis: paired treatment-vs-control contrast.

For each episode, the chosen product is the product page the agent was on
when it clicked add-to-cart (= final step URL; episodes end on add-to-cart).
We join episodes to the experiment manifest and compute, per
(pair, seed, model), the paired difference in focal-product choice between
the treatment arm (focal product's data degraded) and the control arm.

H1 direction: treatment focal-choice rate < control focal-choice rate.

Usage: python scripts/analyze_a1_mini.py [results_glob]
"""

import csv
import glob
import gzip
import json
import os
import pickle
import re
import sys
from collections import defaultdict

# repo root on sys.path: step pickles reference abxlab/agentlab classes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MANIFEST = "conf/experiment-a1-mini/manifest.csv"
PAIRS = "tasks/a1_pilot_pairs.csv"


def slug(url: str) -> str:
    url = url.replace("${env.abxlab_url}", "")  # hydra-interpolated pair URLs
    return url.rstrip("/").split("/")[-1].removesuffix(".html")


def episode_records(results_glob: str):
    for ep_dir in glob.glob(results_glob):
        m = re.search(
            r"GenericAgent-(?P<model>[\w.-]+)_on_abxlab\.(?P<task>dq-[\w-]+)_(?P<seed>\d+)$",
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
                if obs.get("url"):
                    chosen = slug(obs["url"])
        yield {
            "model": m["model"], "task": m["task"], "seed": int(m["seed"]),
            "ok": summary.get("err_msg") is None,
            "completed": summary.get("cum_reward") == 1.0,
            "chosen_slug": chosen,
        }


def main(results_glob: str):
    manifest = {r["name"]: r for r in csv.DictReader(open(MANIFEST))}
    pairs = {r["pair_id"]: r for r in csv.DictReader(open(PAIRS))}

    rows = []
    for ep in episode_records(results_glob):
        meta = manifest.get(ep["task"])
        if meta is None:
            continue
        pair = pairs[meta["pair_id"]]
        focal_slug = slug(pair[f"url_{meta['focal']}"])
        rows.append({**ep, **meta,
                     "focal_chosen": (ep["chosen_slug"] == focal_slug)
                     if ep["chosen_slug"] else None})

    n = len(rows)
    completed = [r for r in rows if r["completed"] and r["chosen_slug"]]
    print(f"episodes matched to manifest: {n}; completed with choice: {len(completed)}")
    if not completed:
        return

    # focal-choice rate by model x arm
    print("\nfocal-choice rate by model x arm "
          "(focal = the product whose data was degraded in the treatment arm):")
    agg = defaultdict(lambda: [0, 0])
    for r in completed:
        k = (r["model"], r["arm"])
        agg[k][0] += r["focal_chosen"]
        agg[k][1] += 1
    for (model, arm), (hits, tot) in sorted(agg.items()):
        print(f"  {model:28s} {arm:9s} {hits:3d}/{tot:3d} = {hits/tot:.1%}")

    # paired contrast per (model): mean over (pair, seed) of T - C
    print("\npaired contrast (treatment - control), per model:")
    cell = {}
    for r in completed:
        cell[(r["model"], r["pair_id"], r["focal"], r["seed"], r["arm"])] = r["focal_chosen"]
    for model in sorted({r["model"] for r in completed}):
        diffs = []
        keys = {(p, f, s) for (m, p, f, s, a) in cell if m == model}
        for (p, f, s) in keys:
            t = cell.get((model, p, f, s, "treatment"))
            c = cell.get((model, p, f, s, "control"))
            if t is not None and c is not None:
                diffs.append(int(t) - int(c))
        if not diffs:
            continue
        mean = sum(diffs) / len(diffs)
        # simple bootstrap CI
        import random
        random.seed(42)
        bs = sorted(
            sum(random.choices(diffs, k=len(diffs))) / len(diffs)
            for _ in range(2000))
        lo, hi = bs[50], bs[1949]
        print(f"  {model:28s} n_paired={len(diffs):3d}  "
              f"effect={mean:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")
    print("\n(negative effect = degrading the focal product's data reduced "
          "its selection, supporting H1)")


if __name__ == "__main__":
    g = sys.argv[1] if len(sys.argv) > 1 else "results/run-*/dq-*/2026-*"
    main(g)
