# Separate multi-turn development pilot

`pilot_cases.json` contains four synthetic two-turn families, each with English and unreviewed Simplified Chinese variants (eight conversations). The scripted second user message is withheld until the candidate answers the first. This file is **not** part of the 30-family/60-prompt single-turn Alpha, and its scores must not be pooled into that Alpha average.

Each family names a transition failure mode and public sources. Each turn has candidate-visible `user` text and private draft `critical_requirements`/`critical_errors`. The two languages share error IDs and severities, but semantic equivalence has not been human reviewed. `contrast_transcripts.json` holds four English-only, deliberately stark safe/unsafe update pairs for judge smoke tests, not Gold labels.

Validate the contract with `python3 -m benchmark.cli validate-multiturn`. The [pilot report](../../docs/MULTITURN_PILOT_2026-10-11_EN.md) documents the local Grok/Gemini workflow, provisional scoring, observed smoke results, and next batch gate. Do not add real patient information, use these draft labels as clinical advice, or call a passing infrastructure test clinical validation.
