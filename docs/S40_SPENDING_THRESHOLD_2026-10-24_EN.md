# S40 first phase spending threshold

The owner selected a **$55 stopping threshold with possible final-request overrun**, not a guaranteed ceiling. This choice applies only to the first phase and does not authorize data export or paid calls. The [versioned policy](../config/spending_s40_v1.json) records that decision without changing historical experiment files.

## What the monitor does

The [new monitor](../benchmark/spending_s40.py) permits one outstanding request. It checks the exact next scheduled row, writes the attempt and payload before dispatch, and settles the charge record before permitting another request. The monitoring amount combines Grok's reported billing ticks with Gemini/MiniMax undiscounted token estimates converted to the same integer unit. Reports retain these subtotals separately; their sum is a stopping signal, not a reconciled invoice.

At exactly $55 or above, the run keeps the last response and its full recorded amount, then stops. For example, $54 followed by a $3 request records $57, not $55, and sends no next request. There is no verified numerical bound on that last-request overrun. Missing or invalid accounting stops immediately with an unknown charge; it is never silently treated as zero. Any technical failure also stops, even when the known charge is below the threshold.

The ledger uses exact integer arithmetic and a hash chain binding each request to its settlement and predecessor. It keeps incomplete attempts visible. Concurrent admission, skipped/reordered rows, a second settlement, directory reuse, retries and resume are rejected. A local write failure leaves the run closed to further requests. These are software controls, not account-wide spending limits or proof that a provider stopped billing after a local timeout.

## Workflow and verification

The offline rehearsal now integrates the S38 schedule, S39 HTTP capture/accounting and selected threshold. It exercises the complete 816-request first-phase path using fake connections and preserves the existing control gate before candidate testing. Threshold-crossing, unknown-cost and interruption paths stop before another connection opens. The response that crosses the threshold is retained; repeats remain separate from first-pass scores.

**590 tests pass, including 33 new tests.** No model API calls, credentials, account changes, new cases or measured scores were involved. The production entry point remains disabled.

## What remains before a paid run

The [first-phase scope record](../config/first_phase_s40_scope_v1.json) prepares the exact six-model roster, two judges, nine development families, two languages and 816 maximum attempts: 216 candidate calls and 600 judge calls, including controls and repeats. It explicitly sets paid-call and export approval to false. Candidates receive case turns and their visible prior answer; judges also receive stage-specific labels and instructions. Confirmation-only cases, Xi'an records, purchased source files and local secrets are excluded from benchmark payloads.

Next, finish the real HTTPS connector and production scheduling/approval integration, confirm effective generation settings, and freeze the complete live protocol. Request explicit authorization for one first-phase run against that protocol. Stopping early must not trigger a fresh run, reset the budget or reuse an old authorization. The earlier $35 confirmation proposal has not been selected or approved by this first-phase decision; confirmation requires its own later policy and authorization.

If the threshold ends a run early, report an incomplete panel with its fixed-denominator intervals—not a mean recalculated over whichever cases/models finished. Budget-driven missingness can be uneven across the ordered roster. The roughly 80-point goal remains a fixed-roster mean objective and is not a reason to change scores or drop missing cells. H130 records this methods-review concern; clinical/language review remains later.

Development remains 125 families / 250 variants, plus three separately reserved new families / six variants; approved calibration and hidden Gold remain zero. MiniMax remains M3 plus stable M3.1 Flash. S26–S39 freezes are unchanged. Run `python3 -m benchmark.spending_s40` for the [snapshot audit](../data/audit/s40_threshold_summary.json), or `python3 -m unittest discover -s tests -q` for regression tests.
