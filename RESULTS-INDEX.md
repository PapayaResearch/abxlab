# results-index.csv — the durable record of every episode

One row per episode across all studies (A1-mini, A3-copy, A3b): model, task,
seed, manifest join (pair/category/factor/level/focal/arm), reward, steps,
error, the chosen product slug, whether the MITM intervention applied, and
token counts.

**Why it exists**: `results/` is ~1.9GB and gitignored, so it lives on one
machine. This 697KB CSV is committed, and it reproduces the published
effects exactly (verified 2026-08-06: A3b claim effect +0.291, style effect
+0.009 — identical to the figures in the research repo's
`a1-experiment/a3b-claims-vs-style-results.md`).

Regenerate after new runs with the snippet in the research repo's writeups,
or re-derive from `results/` with the same parsing the analyze_* scripts use
(summary_info.json for outcomes, the final step_*.pkl.gz for the chosen URL,
nudge_metadata.yaml for the manipulation check).

Full raw traces are archived outside git at
`~/veliu-backups/abxlab-results-core-2026-08-06.tar.gz` (768MB, integrity
verified) — upload to durable storage still pending.
