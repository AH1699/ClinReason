"""Provisional contrast-response checks for an AI judge, never Gold calibration."""

from __future__ import annotations

from typing import Any

from .providers.base import JudgeProvider
from .reviews import case_content_hash
from .scoring import aggregate_judgments


def assess_contrasts(
    cases: list[dict[str, Any]], pairs: list[dict[str, Any]],
    judge: JudgeProvider, rubric: dict[str, Any], scoring: dict[str, Any],
) -> dict[str, Any]:
    by_id = {case["id"]: case for case in cases}
    if len(by_id) != len(cases):
        raise ValueError("Duplicate case IDs in contrast dataset")
    if not pairs or len({pair["case_id"] for pair in pairs}) != len(pairs):
        raise ValueError("Contrast pairs must be nonempty with unique case IDs")
    results = []
    for pair in pairs:
        case_id = pair["case_id"]
        if case_id not in by_id:
            raise ValueError(f"Unknown contrast case: {case_id}")
        case = by_id[case_id]
        error_id = pair["expected_unsafe_error_id"]
        if not any(error["id"] == error_id and error["severity"] == 3
                   for error in case["critical_errors"]):
            raise ValueError(f"Contrast error is not a configured severity-3 error: {case_id}")
        if not all(isinstance(pair.get(key), str) and pair[key].strip()
                   for key in ("good_response", "unsafe_response", "source_url")):
            raise ValueError(f"Contrast is missing response text or source: {case_id}")
        outcomes = {}
        for variant in ("good", "unsafe"):
            judgment = judge.evaluate(case, {"text": pair[f"{variant}_response"]}, rubric)
            aggregate = aggregate_judgments([judgment], rubric, scoring)
            outcomes[variant] = {
                "gated_score": aggregate["gated_score"],
                "reported_critical_error_ids": sorted(
                    error["error_id"] for error in judgment["critical_errors"]
                ),
                "review_status": aggregate["review_status"],
            }
        error_detected = error_id in outcomes["unsafe"]["reported_critical_error_ids"]
        correctly_ranked = outcomes["good"]["gated_score"] > outcomes["unsafe"]["gated_score"]
        results.append({
            "case_id": case_id,
            "case_content_hash": case_content_hash(case),
            "expected_unsafe_error_id": error_id,
            "error_detected": error_detected,
            "correctly_ranked": correctly_ranked,
            "good": outcomes["good"],
            "unsafe": outcomes["unsafe"],
        })
    return {
        "status": "provisional_synthetic_judge_diagnostic_not_gold_calibration",
        "pair_count": len(results),
        "error_detection_count": sum(row["error_detected"] for row in results),
        "correct_ranking_count": sum(row["correctly_ranked"] for row in results),
        "judge_provider": judge.provider_name,
        "judge_model_id": judge.model_id,
        "judge_model_returned": judge.model_version,
        "results": results,
    }
