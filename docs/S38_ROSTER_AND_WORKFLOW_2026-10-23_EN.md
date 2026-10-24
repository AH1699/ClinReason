# S38 reference roster and workflow rehearsal

The upcoming six-model roster now uses **MiniMax M3 and stable M3.1 Flash**, as the owner selected. The ordered workflow runs end to end with supplied mock replies. No provider request, account change, new case or measured model score was produced; spending controls and the live transport still need completion.

Verification: **515 tests pass, including 28 new S38 tests**. The frozen offline snapshot and public audit summary agree.

## The new model configuration

[The S38 roster](../config/reference_mix_s38_v1.json) contains Gemini 3.5 Flash-Lite / 3.8 Flash, Grok 4.6 / 4.7, and MiniMax M3.1 Flash / M3. Gemini 3.8 Flash and Grok 4.7 remain the two judges. It is an explicit experiment configuration: local environment model names do not override it.

MiniMax lists [M2.7 retirement on November 18](https://platform.minimax.io/docs/faq/models), with different transition rules for pay-as-you-go and subscription users. The owner approved replacement before any new results. This is **`MiniMax-M3.1-Flash`**, not the older preview alias. Its [published standard rates](https://platform.minimax.io/docs/pricing/overview) are $0.15 input / $0.60 output per million tokens; M3's short-context standard rates remain $0.30 / $1.20. M2.7 pricing is no longer a dependency for this roster. Account entitlement has not been tested.

Historical `model_matrix.json`, S36/S37 configurations and M2.7 results remain unchanged. S38 applies a hash-bound prospective roster override, rather than editing files that older experiments depend on. The original nine development families, six confirmation reservations, weights and scoring arithmetic are unchanged.

## What the rehearsal now exercises

| Segment | Requests in the design | What must happen |
|---|---:|---|
| Stress controls | 72 judge requests | Complete records, unsafe-error detection, ordering and repeat checks before any development candidate |
| Development first pass | 216 candidate + 432 judge requests | Two answer turns; each judge sees only the appropriate stage criteria |
| Development repeats | 96 judge requests | Rejudge the exact saved answers and payloads, without regenerating candidates |
| Confirmation | 144 candidate + 288 judge requests | Separate final-version run; no confirmation-driven tuning |
| Optional control recheck | 72 judge requests | At most once after the predeclared engineering revision, separately approved |

That is **816 first-phase steps**, then **432 confirmation steps**, or **504** if the separately approved recheck is needed. The [rehearsal engine](../benchmark/workflow_s38.py) integrates the private fixture journal, request construction, exact-model decoding, scoring and reporting. Tests execute the complete first and confirmation paths; they also check the optional recheck schedule and its position before confirmation.

Candidate requests contain no answer key, scoring anchors, reference answer or later user turn. The update uses that candidate's actual saved first answer. Reasoning fields are not inserted into the conversation. Judge inputs exclude candidate identity, control-profile names and expected statuses; initial-stage packets exclude future facts. Repeat payloads must match their originals exactly. Technical failures stop without retry or repair, retaining raw bytes before parsing.

The control gate implements the S36 design: 72 valid records, 12 configured unsafe errors, 12 strict ordering groups, at least 22/24 repeated stage vectors and 11/12 repeated partial scores within five points. Development diagnostics retain denominators of **96 repeated stages, 312 criterion comparisons and 108 cross-judge score pairs**. Missing or unclear point pairs cannot establish a complete stability gate. The 90th percentile uses the nearest-rank definition.

Two judge reports remain separate, with fixed model/family/language denominators and intervals for missing or unclear cells. Repeat rows do not enter the first-pass mean. Mock statuses deliberately test arithmetic and control flow; they are not clinical labels, difficulty evidence or model performance. Their one-micro-dollar reservation per fixture is an artificial test unit, not a provider cost estimate.

## Billing and parameter findings

[Gemini's Interactions-specific guide](https://ai.google.dev/gemini-api/docs/thinking) confirms that its output limit includes thought tokens. This closes the endpoint-documentation question from S37, not the remaining input-token accounting issue.

[Grok's guide](https://docs.x.ai/developers/model-capabilities/text/best-practices) still excludes reasoning from the visible-output cap. Its [reasoning documentation](https://docs.x.ai/developers/model-capabilities/text/reasoning) says reasoning cannot be disabled. The draft explicitly preserves its documented high default; that does not bound cost.

The [MiniMax request contract](https://platform.minimax.io/docs/api-reference/text-chat-openai) requires a model-specific adjustment: M3.1 Flash does not support `service_tier`, so S38 omits it. Adaptive thinking, separate reasoning output and its documented maximum-effort default are explicit. M3 keeps standard tier. Both use visible answer content only for scoring.

These provider settings are not equal compute budgets. The draft 8,192-token fields have different scopes, and an overly tight combined limit may truncate an answer. Truncation must remain a technical failure, not a low clinical score. Effective sampling, token bounds and cost/quality tradeoffs must be settled before a live protocol is frozen; no tuning toward an 80-point mean is permitted.

## Remaining work

The [readiness record](../config/workflow_s38_readiness_v1.json) keeps live allowance at zero. Next, settle an enforceable spending policy, implement actual HTTP raw-body capture and usage reconciliation, and test them with injected responses before loading credentials. Finish effective provider settings and freeze the complete approval-bound protocol. Only then request specific export, request-count and billing approval.

The owner has approved the **roster change**, not a paid run or billing-account changes. Earlier $55/$35 figures remain proposed limits, not guaranteed caps. Expert review remains later; H128 records interpretation questions without blocking engineering. The target remains roughly 80 averaged over the fixed roster, separately per judge, never a forced score for each model.

Reproduce this checkpoint with `python3 -m benchmark.workflow_s38` and `python3 -m unittest discover -s tests -q`. [Audit summary](../data/audit/s38_workflow_summary.json); [offline snapshot](../config/workflow_s38_offline_frozen_v1.json). Development remains 125 families / 250 variants, plus three separately reserved new families / six variants; approved calibration and hidden Gold remain zero. Xi'an and purchased assets stay local.
