# Prospective calibration drafts

`multiturn_candidates_v1.json` and `multiturn_candidates_batch_b.json` contain **six bilingual, two-turn author drafts** prospectively reserved for calibration. Both are deliberately absent from `config/benchmark.json`'s default development case list. Their paired provenance files record published-case mechanisms, public clinical sources, adaptations, and limits. The cases are synthetic, not copied patient records; Chinese text and clinical labels are unreviewed.

This directory is **not** a scored or approved Gold set. Do not run these cases for a model leaderboard, tune a judge against its own answers, or merge them into the public development set. See the [current S5 batch record](../../docs/S5_CALIBRATION_BATCH_B_2026-10-19_EN.md) and `python3 -m benchmark.portfolio_audit` for split/integrity status. The hidden candidate is intentionally absent from Git; approved calibration and hidden Gold counts remain zero.

`criterion_anchors_v1.json` and `response_contrasts_v1.json` form a [provisional bilingual scoring packet](../../docs/S5_CALIBRATION_ANCHORS_2026-10-19_EN.md) for these six draft families. It is structurally validated and hash-bound, but its clinical content, translation and intended response ordering have **not** been independently adjudicated. Neither file is in the default runner, and no responses have been scored.
