#!/usr/bin/env bash
# Run only the seven cases after the separately logged TRIAGE-017-EN smoke test.
# Each case is a fresh, four-call attempt. Stop at the first failure; never retry.
set -euo pipefail

if [[ $# -ne 2 || "$2" != "--live" ]]; then
  echo "Usage: bash scripts/run_batch_f_remaining.sh {gemini-35-flash-lite|grok-46|minimax-m27} --live" >&2
  exit 2
fi

case "$1" in
  gemini-35-flash-lite|grok-46|minimax-m27) ;;
  *) echo "Candidate is not in the frozen batch-F pilot" >&2; exit 2 ;;
esac

candidate_id="$1"
case_ids=(
  HC-MT-TRIAGE-017-ZH-HANS
  HC-MT-MEDSAFE-013-EN
  HC-MT-MEDSAFE-013-ZH-HANS
  HC-MT-MEDSAFE-014-EN
  HC-MT-MEDSAFE-014-ZH-HANS
  HC-MT-REASON-014-EN
  HC-MT-REASON-014-ZH-HANS
)

for case_id in "${case_ids[@]}"; do
  output_dir="work/batch_f_pilot_${candidate_id}_${case_id}_2026-10-19"
  echo "Starting ${candidate_id} ${case_id} (at most four logical API calls)"
  python3 -m benchmark.cli model-matrix \
    --roster config/model_matrix_batch_f_v1.json \
    --anchors config/multiturn_criterion_anchors_batch_f_v1.json \
    --candidate-id "$candidate_id" \
    --case-id "$case_id" \
    --output-dir "$output_dir" \
    --max-api-calls 4 --live
done
