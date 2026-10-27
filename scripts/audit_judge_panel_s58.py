"""Read-only case-level readout of one terminal S57 run.

Replay frozen validation before deriving completion, ceiling and repeat counts.
No new calls, recovered scores, pooled means, rankings or clinical adjudication.
"""

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from scripts import judge_live_s57 as live

VERSION = "s58-saved-panel-readout-v1"
FILES = ("scripts/audit_judge_panel_s58.py", "tests/test_audit_judge_panel_s58.py")


def pass_counts(cells, label):
    present = [c[label]["scoring"] for c in cells if c[label] is not None]
    points = [s["point_score"] for s in present if s["point_score"] is not None]
    return {
        "complete_pairs": len(present), "missing_pairs": len(cells) - len(present),
        "point_scores": len(points), "interval_only_pairs": len(present) - len(points),
        "point_range": [min(points), max(points)] if points else None,
        "exactly_100": sum(p == 100 for p in points),
        "provisional_pass_true": sum(s["provisional_pass"] is True for s in present),
        "provisional_pass_false": sum(s["provisional_pass"] is False for s in present),
        "provisional_pass_unresolved": sum(s["provisional_pass"] is None for s in present),
        "hard_fail_pairs": sum(s["hard_fail"] is True for s in present),
    }


def repeat_comparison(cell):
    if cell["first"] is None or cell["repeat"] is None:
        return None
    first, repeat = (cell[k]["scoring"] for k in ("first", "repeat"))
    points = first["point_score"], repeat["point_score"]
    delta = (float(Decimal(str(points[1])) - Decimal(str(points[0])))
             if all(p is not None for p in points) else None)
    return {
        **{k: cell[k] for k in ("family_id", "language", "candidate_model", "comparative_review_hold")},
        "first_point": points[0], "repeat_point": points[1], "point_delta_repeat_minus_first": delta,
        "point_comparable": delta is not None,
        "stage_vector_matches": cell["repeat_stage_vector_matches"],
        "score_interval_changed": first["criterion_score_interval"] != repeat["criterion_score_interval"],
        "provisional_pass_changed": first["provisional_pass"] != repeat["provisional_pass"],
        "hard_fail_changed": first["hard_fail"] != repeat["hard_fail"],
        "independent_dimension_review_changed": first["independent_dimension_review"] != repeat["independent_dimension_review"],
    }


def family_readout(cells):
    result = []
    for family in dict.fromkeys(c["family_id"] for c in cells):
        group = [c for c in cells if c["family_id"] == family]
        paired = [repeat_comparison(c) for c in group if c["first"] is not None and c["repeat"] is not None]
        deltas = [p["point_delta_repeat_minus_first"] for p in paired if p["point_comparable"]]
        result.append({
            "family_id": family, "expected_cells": len(group),
            "review_held_cells": sum(c["comparative_review_hold"] for c in group),
            "score_use": group[0]["score_use"],
            "first": pass_counts(group, "first"), "repeat": pass_counts(group, "repeat"),
            "paired_first_repeat": len(paired), "point_comparable_repeats": len(deltas),
            "exact_point_repeats": sum(d == 0 for d in deltas),
            "maximum_absolute_repeat_gap": max(map(abs, deltas)) if deltas else None,
            "repeat_stage_vectors_matched": sum(sum(p["stage_vector_matches"].values()) for p in paired),
            "repeat_stage_vectors_compared": 2 * len(paired),
            "provisional_pass_changes": sum(p["provisional_pass_changed"] for p in paired),
            "hard_fail_changes": sum(p["hard_fail_changed"] for p in paired),
        })
    return result


def audit(root, directory, freeze):
    root, directory = Path(root), Path(directory)
    if freeze != live.snapshot(root):
        raise ValueError("Frozen S57 inputs differ")
    protocol = live.panel.sha256_json(freeze)
    before = live.saved.tree_hash(directory)
    checked, core = live.restore(root, directory, protocol)
    if checked["interrupted"] or checked["terminal"] is None:
        raise ValueError("Active or interrupted prefix is not a terminal readout; use S57 replay")
    after = live.saved.tree_hash(directory)
    if before != after:
        raise ValueError("Journal changed during readout")
    cells = checked["case_diagnostics"]
    rows = {r["sequence"]: r for r in core.rows}
    failures = []
    for sequence, outcome in core.outcomes.items():
        if outcome["status"] == "rejected":
            failures.append({"sequence": sequence, "category": outcome["category"],
                **{k: rows[sequence][k] for k in ("block", "family_id", "language", "candidate_model", "stage", "repeat")}})
    return {
        "version": VERSION, "protocol_sha256": protocol, "source_journal_sha256": before,
        "reporter_files": {p: live.journal.digest((root / p).read_bytes()) for p in FILES},
        "new_provider_calls_by_audit": 0, "cost_is_invoice_or_hard_ceiling": False,
        "replay": checked, "family_readout": family_readout(cells),
        "repeat_comparisons": [value for c in cells if (value := repeat_comparison(c)) is not None],
        "rejected_judgments": failures,
        "schedule_disposition_counts": dict(Counter(d["status"] for d in checked["dispositions"])),
        "interpretation": {
            "incomplete_pairs_remain_missing": True, "unclear_is_interval_not_zero": True,
            "repeat_scores_averaged": False, "pooled_model_means": False, "model_rankings": False,
            "held_cells_retained": True, "clinical_validation": False,
            "raw_text_exported": False, "score_band_fitting": False,
            "next_paid_diagnostic_automatically_authorized": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, default=Path(live.FREEZE))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(audit(root, args.directory, live.journal.read(args.freeze)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
