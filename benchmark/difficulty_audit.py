"""Descriptive, non-clinical difficulty diagnostics for paired two-turn runs."""

from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Any

from .multiturn import LANGUAGES, judge_packets_from_answers, validate_multiturn_dataset
from .multiturn_judging import score_judgment
from .provenance import sha256_json


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values), "median": round(median(values), 2),
        "mean": round(mean(values), 2), "max": max(values),
    }


def _unique_by_case(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    if not rows or any(not isinstance(row, dict) or not isinstance(row.get("case_id"), str) for row in rows):
        raise ValueError(f"{name} must contain case-ID objects")
    by_id = {row["case_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError(f"{name} contains duplicate case IDs")
    return by_id


def _check_manifest(
    manifest: dict[str, Any], rows: list[dict[str, Any]], name: str,
) -> None:
    if not isinstance(manifest, dict) or manifest.get("case_count") != len(rows):
        raise ValueError(f"{name} manifest case count does not match rows")
    expected = {(row["case_id"], row["case_content_hash"]) for row in rows}
    revisions = manifest.get("case_revisions")
    if not isinstance(revisions, list) or len(revisions) != len(expected) or {
        (item.get("case_id"), item.get("case_content_hash"))
        for item in revisions if isinstance(item, dict)
    } != expected:
        raise ValueError(f"{name} manifest case revisions do not match rows")


def audit_multiturn_difficulty(
    dataset: dict[str, Any], answers: list[dict[str, Any]],
    judgments: list[dict[str, Any]], candidate_manifest: dict[str, Any],
    judge_manifest: dict[str, Any], rubric: dict[str, Any],
) -> dict[str, Any]:
    """Describe one paired run; never infer clinical correctness from AI scores."""
    validate_multiturn_dataset(dataset)
    by_answer = _unique_by_case(answers, "Candidate answers")
    by_judgment = _unique_by_case(judgments, "Judgments")
    if set(by_answer) != set(by_judgment):
        raise ValueError("Candidate and judge case sets differ; partial runs cannot be audited")
    _check_manifest(candidate_manifest, answers, "Candidate")
    _check_manifest(judge_manifest, judgments, "Judge")
    if candidate_manifest.get("dataset_sha256") != sha256_json(dataset):
        raise ValueError("Candidate manifest is bound to a different dataset revision")
    if judge_manifest.get("rubric_sha256") != sha256_json(rubric):
        raise ValueError("Judge manifest is bound to a different rubric revision")
    if candidate_manifest.get("status") != "draft_multiturn_candidate_run_no_clinical_score":
        raise ValueError("Candidate manifest is not a draft multi-turn run")
    if judge_manifest.get("status") != "experimental_unvalidated_single_ai_judge":
        raise ValueError("Judge manifest is not a provisional multi-turn run")
    if not all(
        answer.get("provider") == candidate_manifest.get("provider")
        and answer.get("model_id") == candidate_manifest.get("requested_model")
        and answer.get("model_version") == candidate_manifest.get("returned_model")
        for answer in answers
    ):
        raise ValueError("Candidate model identity differs from its manifest")
    if not candidate_manifest.get("returned_model") or not judge_manifest.get("returned_model"):
        raise ValueError("Both manifests need returned model identities")

    packets = {packet["case_id"]: packet for packet in judge_packets_from_answers(dataset, answers)}
    families = {family["family_id"]: family for family in dataset["families"]}
    family_languages: dict[str, set[str]] = {}
    cases = []
    for case_id in sorted(by_answer):
        packet = packets[case_id]
        family_id = case_id.rsplit("-", 1)[0] if case_id.endswith("-EN") else case_id.removesuffix("-ZH-HANS")
        if family_id not in families:
            raise ValueError(f"Unknown family in audit: {case_id}")
        language = packet["language"]
        family_languages.setdefault(family_id, set()).add(language)
        row = by_judgment[case_id]
        if row.get("case_content_hash") != packet["case_content_hash"]:
            raise ValueError(f"Judgment case hash mismatch: {case_id}")
        computed = score_judgment(row.get("judgment"), packet, rubric)
        if row.get("score") != computed:
            raise ValueError(f"Stored score disagrees with recomputed score: {case_id}")
        errors = computed["critical_errors"]
        cases.append({
            "family_id": family_id, "case_id": case_id,
            "category": packet["category"], "language": language,
            "case_content_hash": packet["case_content_hash"],
            "gated_score": computed["gated_score"],
            "stage_scores": computed["stage_scores"],
            "revision_score": computed["revision_score"],
            "critical_error_ids": [error["error_id"] for error in errors],
            "critical_error_stages": [error["stage_id"] for error in errors],
            "hard_fail": computed["hard_fail"],
            "judge_requested_review": row["judgment"]["requires_human_review"],
        })
    if any(languages != set(LANGUAGES) for languages in family_languages.values()):
        raise ValueError("Difficulty audit requires both language variants of every family")

    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for case in cases:
        by_family.setdefault(case["family_id"], {})[case["language"]] = case
    pairs = [
        {
            "family_id": family_id,
            "category": families[family_id]["category"],
            "en_score": variants["en"]["gated_score"],
            "zh_hans_score": variants["zh-Hans"]["gated_score"],
            "absolute_gap": round(abs(variants["en"]["gated_score"] - variants["zh-Hans"]["gated_score"]), 2),
        }
        for family_id, variants in sorted(by_family.items())
    ]
    scores = [case["gated_score"] for case in cases]
    error_counts = Counter(stage for case in cases for stage in case["critical_error_stages"])
    return {
        "status": "provisional_patient_facing_difficulty_diagnostic_not_clinical_validation",
        "unit_of_analysis": "family_with_paired_english_and_chinese_variants",
        "dataset_sha256": sha256_json(dataset), "rubric_sha256": sha256_json(rubric),
        "candidate": {
            "provider": candidate_manifest["provider"],
            "requested_model": candidate_manifest["requested_model"],
            "returned_model": candidate_manifest["returned_model"],
        },
        "judge": {
            "provider": judge_manifest.get("provider"),
            "requested_model": judge_manifest.get("requested_model"),
            "returned_model": judge_manifest["returned_model"],
        },
        "family_count": len(pairs), "conversation_count": len(cases),
        "category_family_counts": dict(sorted(Counter(pair["category"] for pair in pairs).items())),
        "gated_score_distribution": _summary(scores),
        "at_least_90_count": sum(score >= 90 for score in scores),
        "perfect_100_count": sum(score == 100 for score in scores),
        "by_language": {
            language: _summary([case["gated_score"] for case in cases if case["language"] == language])
            for language in LANGUAGES
        },
        "by_category": {
            category: {
                "family_count": sum(pair["category"] == category for pair in pairs),
                "gated_score_distribution": _summary([
                    case["gated_score"] for case in cases if case["category"] == category
                ]),
                "at_least_90_count": sum(
                    case["category"] == category and case["gated_score"] >= 90 for case in cases
                ),
            }
            for category in sorted({case["category"] for case in cases})
        },
        "stage_score_distribution": {
            stage: _summary([case["stage_scores"][stage] for case in cases])
            for stage in ("initial", "update")
        },
        "revision_score_distribution": _summary([case["revision_score"] for case in cases]),
        "update_minus_initial_distribution": _summary([
            round(case["stage_scores"]["update"] - case["stage_scores"]["initial"], 2)
            for case in cases
        ]),
        "critical_error_counts_by_stage": {
            stage: error_counts[stage] for stage in ("initial", "update")
        },
        "hard_fail_count": sum(case["hard_fail"] for case in cases),
        "judge_requested_review_count": sum(case["judge_requested_review"] for case in cases),
        "absolute_language_gap_distribution": _summary([pair["absolute_gap"] for pair in pairs]),
        "paired_families": pairs, "cases": cases,
        "limitations": [
            "Synthetic draft cases and translations have not received clinical or bilingual review.",
            "A single uncalibrated AI judge cannot establish clinical correctness or model ranking.",
            "A single candidate run cannot establish cross-model discrimination or repeatability.",
            "Language score gaps may reflect judge bias, translation differences, or candidate behavior.",
        ],
    }


def compare_multiturn_judge_passes(
    dataset: dict[str, Any], answers: list[dict[str, Any]],
    candidate_manifest: dict[str, Any],
    first_judgments: list[dict[str, Any]], first_manifest: dict[str, Any],
    second_judgments: list[dict[str, Any]], second_manifest: dict[str, Any],
    rubric: dict[str, Any],
) -> dict[str, Any]:
    """Compare two independent judge calls on identical candidate responses."""
    if any(not isinstance(manifest.get("generated_at"), str) or not manifest["generated_at"].strip()
           for manifest in (first_manifest, second_manifest)):
        raise ValueError("Judge passes need recorded generation timestamps")
    if first_manifest["generated_at"] == second_manifest["generated_at"]:
        raise ValueError("Judge passes need distinct generation timestamps")
    identity = ("provider", "requested_model", "returned_model", "judge_instruction_sha256", "rubric_sha256")
    if any(first_manifest.get(key) != second_manifest.get(key) for key in identity):
        raise ValueError("Judge passes use different model, instruction, or rubric configurations")
    if not first_manifest.get("judge_instruction_sha256"):
        raise ValueError("Judge passes need a recorded instruction hash")
    first = audit_multiturn_difficulty(
        dataset, answers, first_judgments, candidate_manifest, first_manifest, rubric
    )
    second = audit_multiturn_difficulty(
        dataset, answers, second_judgments, candidate_manifest, second_manifest, rubric
    )
    first_cases = {case["case_id"]: case for case in first["cases"]}
    second_cases = {case["case_id"]: case for case in second["cases"]}
    if first_cases.keys() != second_cases.keys():
        raise ValueError("Judge passes have different case sets")
    changes = []
    for case_id in sorted(first_cases):
        old, new = first_cases[case_id], second_cases[case_id]
        changes.append({
            "case_id": case_id, "family_id": old["family_id"], "language": old["language"],
            "first_score": old["gated_score"], "second_score": new["gated_score"],
            "absolute_score_delta": round(abs(old["gated_score"] - new["gated_score"]), 2),
            "initial_changed": old["stage_scores"]["initial"] != new["stage_scores"]["initial"],
            "update_changed": old["stage_scores"]["update"] != new["stage_scores"]["update"],
            "revision_changed": old["revision_score"] != new["revision_score"],
            "critical_error_ids_changed": set(old["critical_error_ids"]) != set(new["critical_error_ids"]),
            "hard_fail_changed": old["hard_fail"] != new["hard_fail"],
            "review_request_changed": old["judge_requested_review"] != new["judge_requested_review"],
        })
    deltas = [row["absolute_score_delta"] for row in changes]
    return {
        "status": "provisional_judge_repeatability_diagnostic_not_human_calibration",
        "unit_of_analysis": "same_candidate_response_judged_twice",
        "family_count": first["family_count"], "conversation_count": len(changes),
        "candidate": first["candidate"], "judge": first["judge"],
        "first_generated_at": first_manifest["generated_at"],
        "second_generated_at": second_manifest["generated_at"],
        "absolute_score_delta_distribution": _summary(deltas),
        "changed_gated_score_count": sum(row["absolute_score_delta"] > 0 for row in changes),
        "changed_initial_count": sum(row["initial_changed"] for row in changes),
        "changed_update_count": sum(row["update_changed"] for row in changes),
        "changed_revision_count": sum(row["revision_changed"] for row in changes),
        "critical_error_label_flip_count": sum(row["critical_error_ids_changed"] for row in changes),
        "hard_fail_flip_count": sum(row["hard_fail_changed"] for row in changes),
        "review_request_flip_count": sum(row["review_request_changed"] for row in changes),
        "cases": changes,
        "limitations": [
            "Two passes on one candidate answer per case do not measure candidate nondeterminism.",
            "Agreement between uncalibrated AI passes does not establish clinical validity.",
            "Provider-default sampling and mutable aliases limit exact replay.",
        ],
    }
