#!/usr/bin/env python3
"""A1 experiment generator: paired counterfactual configs for ABxLab.

Reads a product-pairs CSV and emits one Hydra task YAML per
(pair x factor-level x focal-side x arm), where the two arms of a
counterfactual pair share everything except the treatment:

  - treatment arm: focal product gets the data-quality intervention
  - control arm:   focal product gets the same function as a passthrough
                   (keep=-1 / no-op args), so both arms traverse identical
                   code paths and the logged nudge_metadata stays comparable

Focal side is counterbalanced (each pair generated twice, focal=A and
focal=B). Seeds are handled at run time by ABxLab (k runs per config);
the pairing key for analysis is (pair_id, factor, level, focal, seed).

Input CSV columns: pair_id, category, url_a, url_b
Usage: generate_counterfactual_experiments.py pairs.csv out_dir/

Drop the resulting directory next to ABxLab's conf/experiment-*/ and select
it via study.experiment_path.
"""

import csv
import sys
import pathlib

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

# factor -> level -> (function name, treatment args, control args)
# Control args are explicit passthroughs so both arms log metadata.
FACTORS = {
    "attributes": {
        "sparse": ("attributes", {"keep": 3}, {"keep": -1}),
        "absent": ("attributes", {"keep": 0}, {"keep": -1}),
    },
    "structured_data": {
        # Store pages ship with microdata; treatment strips it from the
        # focal product. (H2's inject mode is for catalogs built bare.)
        "stripped": ("structured_data", {"mode": "strip"}, None),
    },
    "description": {
        # Text variants are filled in per product from catalog/variants/
        # by a post-processing step; placeholders here.
        "thin": ("description", {"mode": "replace",
                                 "value": "__THIN_VARIANT__"}, None),
        "padded": ("description", {"mode": "replace",
                                   "value": "__PADDED_VARIANT__"}, None),
        "removed": ("description", {"mode": "remove"}, None),
    },
    "images": {
        "single": ("images", {"keep": 1}, {"keep": -1}),
    },
}


def make_config(task_id, name, urls, focal_url, factor, level, arm):
    func, treat_args, control_args = FACTORS[factor][level]
    choices = []
    args = treat_args if arm == "treatment" else control_args
    if args is not None:
        choices.append({
            "url": focal_url,
            "nudge": f"dq:{factor}:{level}:{arm}",
            "functions": [{"module": MODULE, "name": func, "args": args}],
        })
    return {
        "task": {
            "name": name,
            "config": {
                "task_id": task_id,
                "start_urls": list(urls),
                "intent_template": INTENT,
                "instantiation_dict": {},
                "intent": INTENT,
                "choices": choices,
                "intent_template_id": 0,
            },
        }
    }


def main(pairs_csv, out_dir):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    task_id = 0

    with open(pairs_csv, newline="") as f:
        pairs = list(csv.DictReader(f))

    for pair in pairs:
        urls = (pair["url_a"], pair["url_b"])
        for factor, levels in FACTORS.items():
            for level in levels:
                for focal in ("a", "b"):
                    focal_url = pair[f"url_{focal}"]
                    for arm in ("treatment", "control"):
                        name = (f"dq-{pair['pair_id']}-{factor}-{level}"
                                f"-{focal}-{arm}")
                        cfg = make_config(task_id, name, urls, focal_url,
                                          factor, level, arm)
                        path = out / f"{name}.yaml"
                        with open(path, "w") as fh:
                            fh.write("# @package _global_\n\n")
                            yaml.safe_dump(cfg, fh, sort_keys=False,
                                           default_flow_style=False)
                        manifest.append({
                            "task_id": task_id, "name": name,
                            "pair_id": pair["pair_id"],
                            "category": pair["category"],
                            "factor": factor, "level": level,
                            "focal": focal, "arm": arm,
                        })
                        task_id += 1

    with open(out / "manifest.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=manifest[0].keys())
        writer.writeheader()
        writer.writerows(manifest)

    print(f"{task_id} configs -> {out} (manifest.csv for analysis joins)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
