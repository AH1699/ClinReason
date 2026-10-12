# Separate multi-turn development pilot

`pilot_cases.json` contains the original four synthetic two-turn families. `batch_c_cases.json` adds 12 more. The configured multi-turn track therefore has 16 families and 32 English/Chinese conversations, all draft and unreviewed. The scripted second user message is withheld until the candidate answers the first. This track is **not** part of the 30-family/60-prompt single-turn Alpha, and its scores must not be pooled into that Alpha average.

Each family names a transition failure mode and public sources. Each turn has candidate-visible `user` text and private draft `critical_requirements`/`critical_errors`. The two languages share error IDs and severities, but semantic equivalence has not been human reviewed. `contrast_transcripts.json` holds four English-only stark safe/unsafe pairs plus five safe/partial/unsafe triplets for judge diagnostics, not Gold labels.

Validate the combined contract with `python3 -m benchmark.cli validate-multiturn`. The [pilot report](../../docs/MULTITURN_PILOT_2026-10-11_EN.md) documents the local workflow and old smoke results; the [batch C report](../../docs/MULTITURN_BATCH_C_2026-10-11_EN.md) maps the new intended probes and review questions. Do not add real patient information, use these draft labels as clinical advice, or call a passing infrastructure test clinical validation.
