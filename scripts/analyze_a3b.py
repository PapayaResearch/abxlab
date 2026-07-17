#!/usr/bin/env python3
"""A3b joint analysis: the style x claims 2x2, pooling mini-A3 cells
(control, jargon [, data_led]) with A3b cells (claims, claims_jargon).

Contrasts within (model, pair, focal, seed), bootstrap 95% CIs.
Usage: python scripts/analyze_a3b.py
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

MANIFESTS = ["conf/experiment-a3-copy/manifest.csv",
             "conf/experiment-a3b-claims/manifest.csv"]
CATALOG_DIR = ("/Users/dambrosm/personal/veliu/code/ecommerce-research/"
               "a1-experiment/catalog/data")
EP_RE = re.compile(
    r"GenericAgent-(?P<model>[\w.-]+)_on_abxlab\."
    r"(?P<task>dq3b?-[\w-]+)_(?P<seed>\d+)$")
CONTRASTS = [
    ("claims", "control", "claim effect (neutral copy)"),
    ("claims_jargon", "jargon", "claim effect (jargon copy)"),
    ("jargon", "control", "style effect (no claim)"),
    ("claims_jargon", "claims", "style effect (with claim)"),
    ("data_led", "control", "data-led vs neutral"),
]


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def boot_ci(diffs, n=2000, seed=42):
    random.seed(seed)
    bs = sorted(sum(random.choices(diffs, k=len(diffs))) / len(diffs)
                for _ in range(n))
    return bs[int(n * 0.025)], bs[int(n * 0.975)]


def main():
    manifest = {}
    for mf in MANIFESTS:
        for r in csv.DictReader(open(mf)):
            manifest[r["name"]] = r
    slugs = {}
    for f in glob.glob(f"{CATALOG_DIR}/*.json"):
        for p in json.load(open(f)):
            slugs[p["sku"]] = slugify(p["title_minimal"])

    cell, n_total, n_used = {}, 0, 0
    for ep_dir in glob.glob("results/run-*/dq3*-*/2026-*"):
        m = EP_RE.search(ep_dir)
        if not m:
            continue
        meta = manifest.get(m["task"])
        if meta is None:
            continue
        try:
            s = json.load(open(f"{ep_dir}/summary_info.json"))
        except FileNotFoundError:
            continue
        n_total += 1
        if s.get("err_msg") is not None or s.get("cum_reward") != 1.0:
            continue
        steps = sorted(glob.glob(f"{ep_dir}/step_*.pkl.gz"))
        if not steps:
            continue
        with gzip.open(steps[-1], "rb") as f:
            obs = getattr(pickle.load(f), "obs", None) or {}
        chosen = obs.get("url", "").rstrip("/").split("/")[-1].removesuffix(".html")
        if not chosen:
            continue
        n_used += 1
        cell[(m["model"], meta["pair_id"], meta["focal"], int(m["seed"]),
              meta["level"])] = int(chosen == slugs[meta["focal_sku"]])

    print(f"episodes: {n_total} matched, {n_used} usable")

    models = sorted({k[0] for k in cell})
    print("\nfocal-choice rate by model x cell:")
    agg = defaultdict(lambda: [0, 0])
    for (model, _, _, _, level), v in cell.items():
        agg[(model, level)][0] += v
        agg[(model, level)][1] += 1
    for (model, level), (h, t) in sorted(agg.items()):
        print(f"  {model:22s} {level:14s} {h:3d}/{t:3d} = {h/t:.1%}")

    print("\npaired contrasts (mean, 95% bootstrap CI):")
    scope_models = models + ["POOLED"]
    for model in scope_models:
        keys = {(m, p, f, s) for (m, p, f, s, l) in cell
                if model == "POOLED" or m == model}
        for hi, lo, label in CONTRASTS:
            diffs = []
            for (m, p, f, s) in keys:
                a, b = cell.get((m, p, f, s, hi)), cell.get((m, p, f, s, lo))
                if a is not None and b is not None:
                    diffs.append(a - b)
            if not diffs:
                continue
            mean = sum(diffs) / len(diffs)
            lo_ci, hi_ci = boot_ci(diffs)
            print(f"  {model:22s} {label:28s} {mean:+.3f} "
                  f"[{lo_ci:+.3f}, {hi_ci:+.3f}]  n={len(diffs)}")


if __name__ == "__main__":
    main()
