"""Controlled two-turn contrast checks for provisional judge discrimination."""

from __future__ import annotations

from typing import Any

from .multiturn import build_judge_packet, validate_multiturn_dataset, variant_hash, variant_id
from .multiturn_judging import score_judgment


def contrast_packet(family: dict[str, Any], pair: dict[str, Any], variant: str) -> dict[str, Any]:
    if variant not in {"safe", "partial", "unsafe"}:
        raise ValueError("Contrast variant must be safe, partial, or unsafe")
    language = pair["language"]
    turns = family["variants"][language]["turns"]
    update_key = f"{variant}_update_response"
    responses = [pair["initial_response"], pair[update_key]]
    transcript = []
    outputs = []
    for turn, text in zip(turns, responses):
        transcript.extend([{"role": "user", "content": turn["user"]},
                           {"role": "assistant", "content": text}])
        outputs.append({"stage_id": turn["stage_id"], "text": text})
    response = {
        "case_id": variant_id(family, language),
        "case_version": family["version"],
        "case_content_hash": variant_hash(family, language),
        "transcript": transcript,
        "turn_outputs": outputs,
    }
    return build_judge_packet(family, language, response)


def assess_contrast_pairs(
    dataset: dict[str, Any], pairs: list[dict[str, Any]], judge: Any,
    rubric: dict[str, Any],
) -> dict[str, Any]:
    validate_multiturn_dataset(dataset)
    families = {family["family_id"]: family for family in dataset["families"]}
    if not pairs or len({pair["family_id"] for pair in pairs}) != len(pairs):
        raise ValueError("Contrast pairs must be nonempty with unique family IDs")
    results = []
    for pair in pairs:
        family_id = pair["family_id"]
        if family_id not in families or pair.get("language") not in families[family_id]["variants"]:
            raise ValueError(f"Unknown contrast family or language: {family_id}")
        expected_error = pair["expected_unsafe_error_id"]
        update = families[family_id]["variants"][pair["language"]]["turns"][1]
        if expected_error not in {error["id"] for error in update["critical_errors"]}:
            raise ValueError(f"Expected error is not configured for the update: {family_id}")
        for field in ("initial_response", "safe_update_response", "unsafe_update_response"):
            if not isinstance(pair.get(field), str) or not pair[field].strip():
                raise ValueError(f"Missing contrast response: {family_id}/{field}")
        has_partial = "partial_update_response" in pair
        if has_partial and (not isinstance(pair["partial_update_response"], str)
                            or not pair["partial_update_response"].strip()):
            raise ValueError(f"Missing contrast response: {family_id}/partial_update_response")
        outcomes = {}
        for variant in (("safe", "partial", "unsafe") if has_partial else ("safe", "unsafe")):
            packet = contrast_packet(families[family_id], pair, variant)
            judgment = judge.evaluate(packet)
            score = score_judgment(judgment, packet, rubric)
            outcomes[variant] = {
                "gated_score": score["gated_score"],
                "critical_error_ids": sorted(error["error_id"] for error in judgment["critical_errors"]),
                "revision_score": score["revision_score"],
                "stage_scores": score["stage_scores"],
                "judge_rationale": {
                    "overall": judgment["overall_rationale"],
                    "stages": [
                        {"stage_id": stage["stage_id"], "rationale": stage["rationale"]}
                        for stage in judgment["stage_scores"]
                    ],
                    "critical_errors": judgment["critical_errors"],
                },
            }
        row = {
            "family_id": family_id,
            "case_id": variant_id(families[family_id], pair["language"]),
            "case_content_hash": variant_hash(families[family_id], pair["language"]),
            "expected_unsafe_error_id": expected_error,
            "error_detected": expected_error in outcomes["unsafe"]["critical_error_ids"],
            "correctly_ranked": outcomes["safe"]["gated_score"] > outcomes["unsafe"]["gated_score"],
            "safe": outcomes["safe"], "unsafe": outcomes["unsafe"],
        }
        if has_partial:
            row["partial"] = outcomes["partial"]
            row["correct_partial_ranking"] = (
                outcomes["safe"]["gated_score"] > outcomes["partial"]["gated_score"]
                > outcomes["unsafe"]["gated_score"]
            )
        results.append(row)
    return {
        "status": "provisional_synthetic_judge_diagnostic_not_gold_calibration",
        "pair_count": len(results),
        "error_detection_count": sum(row["error_detected"] for row in results),
        "correct_ranking_count": sum(row["correctly_ranked"] for row in results),
        "partial_pair_count": sum("partial" in row for row in results),
        "correct_partial_ranking_count": sum(row.get("correct_partial_ranking", False) for row in results),
        "judge_provider": judge.provider_name,
        "judge_model_id": judge.model_id,
        "judge_model_returned": judge.model_version,
        "results": results,
    }
