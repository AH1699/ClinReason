"""Read-only S20 adjudication queue for exact S19 judge repeats."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .config import load_json
from .multifamily_repeatability_s19 import audit as audit_s19, prepare as prepare_s19
from .provenance import sha256_json


POLICY_PATH = "config/paired_judge_evidence_s20_v1.json"


def classify_pair(comparison: dict[str, Any], source: dict[str, Any],
                  repeat: dict[str, Any]) -> dict[str, Any]:
    """Flag evidence to adjudicate; never select or alter a rating."""
    left, right = source["judgment"], repeat["judgment"]
    stages = (left["stage_scores"], right["stage_scores"])
    if any([item["stage_id"] for item in stage] != ["initial", "update"] for stage in stages):
        raise ValueError("Unexpected S19 stage order")
    dimensions = {
        f"{stage}_{dimension}": [stages[0][index][dimension], stages[1][index][dimension]]
        for index, stage in enumerate(("initial", "update"))
        for dimension in ("requirements", "safety")
    }
    dimensions["revision"] = [left["revision_score"], right["revision_score"]]
    changed = [name for name, values in dimensions.items() if values[0] != values[1]]
    if bool(changed) == comparison["dimensions_same"]:
        raise ValueError("S19 dimension comparison and raw ratings disagree")
    flags = []
    if changed and comparison["statuses_same"] and comparison["critical_errors_same"]:
        flags.append("same_finding_dimension_variance_review")
    if any(name.endswith("_safety") for name in changed):
        flags.append("distinct_direct_safety_evidence_review")
    if "revision" in changed:
        flags.append("new_turn_revision_evidence_review")
    if any(name.endswith("_requirements") for name in changed):
        flags.append("requirement_rating_evidence_review")
    if not comparison["pass_same"]:
        flags.append("identical_packet_provisional_pass_hold")
    if not comparison["review_same"]:
        flags.append("human_review_flag_variance_review")
    return {
        "case_id": comparison["case_id"], "answer_type": comparison["answer_type"],
        "judge": comparison["judge"], "changed_dimensions": changed,
        "ratings_first_repeat": dimensions, "score_delta": comparison["score_delta"],
        "criterion_statuses_same": comparison["statuses_same"],
        "critical_errors_same": comparison["critical_errors_same"],
        "pass_same": comparison["pass_same"], "flags": flags,
        "judge_rationales_not_independent_evidence": {
            "first_update": stages[0][1]["rationale"],
            "repeat_update": stages[1][1]["rationale"],
            "first_overall": left["overall_rationale"],
            "repeat_overall": right["overall_rationale"],
        },
    }


def audit(root: Path, repeat_dir: Path) -> dict[str, Any]:
    policy = load_json(root / POLICY_PATH)
    if (policy.get("version") != "s20-v1-offline-review-only"
        or policy.get("status") != "paired_evidence_adjudication_not_a_scoring_contract"
        or policy.get("source_protocol") != "config/multifamily_repeatability_s19_v1.json"
        or policy.get("expected_s19_cells") != 24):
        raise ValueError("Unknown S20 evidence policy")
    verified = audit_s19(root, repeat_dir)
    _, selected = prepare_s19(root)
    source_by_case = {}
    repeat_by_case = {}
    for row, _ in selected:
        lang = "en" if row["language"] == "en" else "zh"
        case_id = f"{row['family_id']}-{'EN' if lang == 'en' else 'ZH-HANS'}"
        source_by_case[case_id] = root / row["source_dir"]
        repeat_by_case[case_id] = repeat_dir / f"{row['family_id'].lower()}_{lang}"
    rows = []
    for comparison in verified["comparisons"]:
        case_id = comparison["case_id"]
        filename = f"{comparison['judge']}-judge__{comparison['answer_type']}.judgment.json"
        source = load_json(source_by_case[case_id] / filename)
        repeat = load_json(repeat_by_case[case_id] / filename)
        rows.append(classify_pair(comparison, source, repeat))
    counts = Counter(flag for row in rows for flag in row["flags"])
    held = [row for row in rows if "identical_packet_provisional_pass_hold" in row["flags"]]
    expected = {(case_id, policy["expected_boundary_answer_type"], policy["expected_boundary_judge"])
                for case_id in policy["expected_boundary_case_ids"]}
    if len(rows) != 24 or {(row["case_id"], row["answer_type"], row["judge"]) for row in held} != expected:
        raise ValueError("S20 observed pass boundary differs from frozen S19 result")
    return {
        "status": "s20_verified_saved_pair_adjudication_queue_not_rescoring",
        "policy_sha256": sha256_json(policy), "s19_policy_sha256": verified["policy_sha256"],
        "verified_pairs": len(rows), "flag_counts": dict(sorted(counts.items())),
        "pass_boundary_holds": len(held), "adjudication_fields": policy["required_adjudication_fields"],
        "rows": rows, "candidate_calls": 0, "judge_calls": 0, "limits": policy["limits"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline S20 exact-packet evidence adjudication audit")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--repeat-dir", type=Path)
    parser.add_argument("--summary", action="store_true", help="Omit per-cell judge rationales")
    args = parser.parse_args(argv)
    directory = args.repeat_dir or args.root / "work/s19_multifamily_repeat_2026-10-21"
    result = audit(args.root, directory)
    if args.summary:
        result = {key: value for key, value in result.items() if key != "rows"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
