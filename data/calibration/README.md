# Prospective calibration drafts

`multiturn_candidates_v1.json` contains one **new, bilingual, two-turn author draft** prospectively reserved for calibration. It is deliberately absent from `config/benchmark.json`'s default development case list. `provenance_v1.json` records the published-case mechanism, current public prescribing source, adaptation, and limits. The case is synthetic, not a copied patient record, and its Chinese text and clinical labels are unreviewed.

This directory is **not** a scored or approved Gold set. Do not run these cases for a model leaderboard, tune a judge against its own answers, or merge them into the public development set. See the [S5 checkpoint](../../docs/S5_PROSPECTIVE_CASES_2026-10-18_EN.md) and `python3 -m benchmark.portfolio_audit` for split/integrity status. The hidden candidate is intentionally absent from Git; approved calibration and hidden Gold counts remain zero.
