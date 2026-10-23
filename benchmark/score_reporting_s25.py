"""Offline score-reportability diagnostic over frozen S19/S22/S23/S24 evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import judge_evidence_panel_s22_abort_audit as s22
from . import multifamily_repeatability_s19 as s19
from . import scoring_boundary_s23 as s23
from .config import load_json
from .scoring_evidence_s24 import validate_contract


POLICY_PATH = "config/score_reporting_s25_v1.json"


def reportability(*, panel_complete: bool, exact_packet_pass_stable: bool | None,
                  clinical_and_language_approved: bool,
                  methods_released: bool) -> dict[str, Any]:
    """Return reasons, not a revised numeric score or an adjudicated pass."""
    holds = []
    if not panel_complete:
        holds.append("incomplete_frozen_panel")
    if exact_packet_pass_stable is None:
        holds.append("exact_packet_repeat_not_performed")
    elif not exact_packet_pass_stable:
        holds.append("identical_packet_pass_flip")
    if not clinical_and_language_approved:
        holds.append("unapproved_clinical_or_language_labels")
    if not methods_released:
        holds.append("methodology_release_pending")
    return {"comparison_ready": not holds, "hold_reasons": holds}


def audit(root: Path, s19_dir: Path, s22_dir: Path) -> dict[str, Any]:
    policy = load_json(root / POLICY_PATH)
    if (policy.get("version") != "s25-v1-offline-reportability"
            or policy.get("status") != "non_enforced_development_diagnostic_not_calibration"):
        raise ValueError("Unknown or enforced S25 reportability policy")
    evidence = validate_contract(root / "config/scoring_evidence_s24_v1.json")
    repeated = s19.audit(root, s19_dir)
    stopped = s22.audit(root, s22_dir)
    boundary = s23.audit(root, s22_dir, s19_dir)
    held = boundary["s20_identical_packet_pass_holds"]
    if (repeated["cells"] != 24 or len(held) != 2 or stopped["saved_cells"] != 23
            or stopped["full_first_stage_passed"] or evidence["proposed_deductions"] != 0):
        raise ValueError("S25 frozen evidence differs from expected audited inputs")
    unstable = {(row["case_id"], "partial", row["judge"]) for row in held}
    repeated_rows = []
    for row in repeated["comparisons"]:
        flags = reportability(
            panel_complete=True,
            exact_packet_pass_stable=row["pass_same"],
            clinical_and_language_approved=False,
            methods_released=False,
        )
        if ((row["case_id"], row["answer_type"], row["judge"]) in unstable) != ("identical_packet_pass_flip" in flags["hold_reasons"]):
            raise ValueError("S25 pass-flip hold differs from S23 verified boundary")
        repeated_rows.append({"case_id": row["case_id"], "answer_type": row["answer_type"],
                              "judge": row["judge"], "exact_score_repeated": row["score_same"],
                              "provisional_pass_repeated": row["pass_same"], **flags})
    return {
        "status": "s25_offline_reportability_not_scoring_contract",
        "policy_version": policy["version"],
        "s19_exact_packet_cells": repeated["cells"],
        "s19_exact_score_repeats": repeated["exact_score_repeats"],
        "s19_provisional_pass_repeats": repeated["pass_repeats"],
        "s19_identical_packet_pass_flip_holds": len(unstable),
        "s19_comparison_ready_cells": sum(row["comparison_ready"] for row in repeated_rows),
        "s19_cell_reportability": repeated_rows,
        "s22_saved_first_stage_cells": stopped["saved_cells"],
        "s22_planned_first_stage_cells": 24,
        "s22_missing_cell": stopped["missing_cell"],
        "s22_comparison_ready": reportability(panel_complete=False,
                                                exact_packet_pass_stable=None,
                                                clinical_and_language_approved=False,
                                                methods_released=False),
        "s24_evidence_fixtures": evidence["fixtures"],
        "candidate_calls": 0, "judge_calls": 0, "historical_scores_changed": 0,
        "limits": policy["limits"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline S25 score-reportability diagnostic")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--s19-dir", type=Path)
    parser.add_argument("--s22-dir", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    result = audit(args.root,
                   args.s19_dir or args.root / "work/s19_multifamily_repeat_2026-10-21",
                   args.s22_dir or args.root / "work/s22_v1_first_2026-10-22")
    if args.summary:
        result.pop("s19_cell_reportability")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
