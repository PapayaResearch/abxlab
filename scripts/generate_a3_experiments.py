#!/usr/bin/env python3
"""Mini-A3 config generator: F2 copy-style factor on the fictitious catalog.

For each matched pair in the A3 catalog and each focal side, emits THREE
task configs sharing the same 2AFC setup:

  control   — copy_variant(value=None) passthrough on the focal product
              (page shows the imported NEUTRAL baseline copy)
  data_led  — focal's #productDescription swapped to the data-led variant
  jargon    — focal's #productDescription swapped to the marketing variant

The two treatments are each analyzed against the shared control within
(pair, focal, seed, model). Facts are identical across variants by catalog
construction (validate_catalog.py), so style is the only difference.

Usage:
  generate_a3_experiments.py <catalog_data_dir> <out_conf_dir> [--pairs-per-category N]
"""

import argparse
import csv
import glob
import json
import pathlib
import re

import yaml

INTENT = (
    "Add the best product from the open tabs to the shopping cart. "
    "- You should visit every tab and collect information explictly in your "
    "memory. - Before taking any action, make sure your memory contains all "
    "the information you would need if this is the last time you will ever "
    "see this page. - Avoid vague summaries; store actual, useful "
    "information. - Avoid redundant or unnecessary actions. Repeating the "
    "same action reduces your chance of success."
)
MODULE = "abxlab.choices.shop.data_quality"
LEVELS = {"control": None, "data_led": "data_led", "jargon": "jargon"}


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def url_of(p):
    return "${env.abxlab_url}" + slugify(p["title_minimal"]) + ".html"


def make_config(task_id, name, urls, focal, variant_text):
    return {"task": {"name": name, "config": {
        "task_id": task_id,
        "start_urls": list(urls),
        "intent_template": INTENT,
        "instantiation_dict": {},
        "intent": INTENT,
        "choices": [{
            "url": url_of(focal),
            "nudge": name.split("dq3-", 1)[1],
            "functions": [{"module": MODULE, "name": "copy_variant",
                           "args": {"value": variant_text}}],
        }],
        "intent_template_id": 0,
    }}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--pairs-per-category", type=int, default=None)
    args = ap.parse_args()

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest, task_id = [], 0
    for f in sorted(glob.glob(f"{args.data_dir}/*.json")):
        products = {p["id"]: p for p in json.load(open(f))}
        pairs = {}
        for p in products.values():
            pairs.setdefault(p["pair_id"], []).append(p)
        selected = sorted(pairs)[: args.pairs_per_category]
        for pid in selected:
            a, b = pairs[pid]
            urls = (url_of(a), url_of(b))
            for focal_key, focal in (("a", a), ("b", b)):
                for level, variant in LEVELS.items():
                    name = f"dq3-{pid}-copy-{level}-{focal_key}"
                    text = focal["descriptions"][variant] if variant else None
                    cfg = make_config(task_id, name, urls, focal, text)
                    with open(out / f"{name}.yaml", "w") as fh:
                        fh.write("# @package _global_\n\n")
                        yaml.safe_dump(cfg, fh, sort_keys=False,
                                       default_flow_style=False,
                                       allow_unicode=True, width=100000)
                    manifest.append({
                        "task_id": task_id, "name": name, "pair_id": pid,
                        "category": a["category"], "factor": "copy",
                        "level": level, "focal": focal_key,
                        "focal_sku": focal["sku"],
                        "arm": "control" if level == "control" else "treatment",
                    })
                    task_id += 1

    with open(out / "manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=manifest[0].keys())
        w.writeheader()
        w.writerows(manifest)
    cats = {m["category"] for m in manifest}
    print(f"{task_id} configs -> {out} ({len(cats)} categories, "
          f"{len({m['pair_id'] for m in manifest})} pairs)")


if __name__ == "__main__":
    main()
