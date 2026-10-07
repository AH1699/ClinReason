from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any


def _median(values: list[float]) -> float:
    return float(statistics.median(values))


def _single_judge_pass(
    judgment: dict[str, Any], rubric: dict[str, Any], scoring_config: dict[str, Any]
) -> bool:
    weighted_sum = 0.0
    active_weight = 0.0
    for definition in rubric["dimensions"]:
        item = judgment["dimension_scores"].get(definition["id"], {})
        if item.get("applicable") and item.get("score") is not None:
            weighted_sum += (
                float(item["score"]) / rubric["scale_max"]
            ) * definition["weight"]
            active_weight += definition["weight"]
    if not active_weight:
        return False
    score = 100 * weighted_sum / active_weight
    hard_fail = False
    for error in judgment.get("critical_errors", []):
        rule = scoring_config["critical_error_rules"][str(int(error["severity"]))]
        score -= rule.get("deduction", 0)
        if "cap" in rule:
            score = min(score, rule["cap"])
        hard_fail = hard_fail or bool(rule.get("hard_fail", False))
    return (not hard_fail) and score >= scoring_config["pass_threshold"]


def aggregate_judgments(
    judgments: list[dict[str, Any]],
    rubric: dict[str, Any],
    scoring_config: dict[str, Any],
) -> dict[str, Any]:
    if not judgments:
        raise ValueError("At least one judgment is required")

    dimensions: dict[str, dict[str, Any]] = {}
    ranges: list[float] = []
    weighted_sum = 0.0
    active_weight = 0.0
    disagreement_threshold = scoring_config["judge_disagreement_threshold"]
    review_reasons: list[str] = []

    for definition in rubric["dimensions"]:
        dim_id = definition["id"]
        values = [
            float(j["dimension_scores"][dim_id]["score"])
            for j in judgments
            if j["dimension_scores"].get(dim_id, {}).get("applicable")
            and j["dimension_scores"][dim_id].get("score") is not None
        ]
        if not values:
            dimensions[dim_id] = {"score": None, "applicable": False, "range": None}
            continue
        score = _median(values)
        score_range = max(values) - min(values)
        ranges.append(score_range)
        dimensions[dim_id] = {
            "score": score,
            "applicable": True,
            "range": score_range,
            "judge_scores": values,
        }
        weighted_sum += (score / rubric["scale_max"]) * definition["weight"]
        active_weight += definition["weight"]
        if score_range >= disagreement_threshold:
            review_reasons.append(f"dimension_disagreement:{dim_id}")

    if active_weight == 0:
        raise ValueError("No applicable dimensions found")
    raw_score = 100 * weighted_sum / active_weight

    independent_passes = [
        _single_judge_pass(judgment, rubric, scoring_config) for judgment in judgments
    ]
    if len(set(independent_passes)) > 1:
        review_reasons.append("independent_pass_disagreement")

    error_votes: dict[tuple[str, int], int] = defaultdict(int)
    error_labels_by_id: dict[str, list[int | None]] = defaultdict(list)
    for judgment in judgments:
        seen_in_judgment: set[tuple[str, int]] = set()
        for error in judgment.get("critical_errors", []):
            key = (error["error_id"], int(error["severity"]))
            if key not in seen_in_judgment:
                error_votes[key] += 1
                seen_in_judgment.add(key)
        known_ids = {key[0] for key in error_votes}
        current = {key[0]: key[1] for key in seen_in_judgment}
        for error_id in known_ids | set(error_labels_by_id):
            error_labels_by_id[error_id].append(current.get(error_id))
    # Backfill earlier judges when an error ID first appears later.
    for labels in error_labels_by_id.values():
        if len(labels) < len(judgments):
            labels[:0] = [None] * (len(judgments) - len(labels))
    majority = len(judgments) // 2 + 1
    confirmed_errors = [
        {"error_id": key[0], "severity": key[1], "votes": votes}
        for key, votes in error_votes.items()
        if votes >= majority
    ]
    if any(len(set(labels)) > 1 for labels in error_labels_by_id.values()):
        review_reasons.append("critical_error_disagreement")

    gated_score = raw_score
    hard_fail = False
    for error in confirmed_errors:
        severity = error["severity"]
        rule = scoring_config["critical_error_rules"][str(severity)]
        if "deduction" in rule:
            gated_score -= rule["deduction"]
        if "cap" in rule:
            gated_score = min(gated_score, rule["cap"])
        hard_fail = hard_fail or bool(rule.get("hard_fail", False))

    gated_score = max(0.0, round(gated_score, 2))
    raw_score = round(raw_score, 2)
    pass_threshold = scoring_config["pass_threshold"]
    passed = (not hard_fail) and gated_score >= pass_threshold

    mean_judge_confidence = statistics.fmean(
        float(j.get("confidence", 0.5)) for j in judgments
    )
    mean_range = statistics.fmean(ranges) if ranges else rubric["scale_max"]
    agreement = max(0.0, 1.0 - mean_range / rubric["scale_max"])
    judge_factor = min(1.0, len(judgments) / scoring_config["target_judge_count"])
    confidence = round(
        mean_judge_confidence * (0.5 + 0.5 * agreement) * (0.7 + 0.3 * judge_factor),
        3,
    )
    if confidence < scoring_config["human_review_confidence_threshold"]:
        review_reasons.append("low_confidence")
    if any(j.get("requires_human_review") for j in judgments):
        review_reasons.append("judge_requested_review")
    if hard_fail:
        review_reasons.append("hard_fail")

    return {
        "dimension_scores": dimensions,
        "raw_score": raw_score,
        "gated_score": gated_score,
        "pass": passed,
        "hard_fail": hard_fail,
        "confirmed_critical_errors": confirmed_errors,
        "confidence": confidence,
        "review_status": "required" if review_reasons else "not_required",
        "review_reasons": sorted(set(review_reasons)),
        "judge_count": len(judgments),
    }
