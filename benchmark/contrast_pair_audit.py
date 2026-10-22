"""Offline, exact-protocol comparison of paired EN/ZH authored judge contrasts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import load_json
from .frozen_batch_g import load_batch_g_dataset
from .criterion_anchors import validate_anchor_set
from .multiturn import merge_multiturn_datasets, variant_hash, variant_id
from .provenance import sha256_json, sha256_text


COMMON_HASHES = (
    "roster_sha256", "dataset_sha256", "rubric_sha256",
    "criterion_anchors_sha256", "judge_instruction_sha256",
)
VARIANTS = ("safe", "partial", "unsafe")


def audit_contrast_pair(
    en_report: dict[str, Any], zh_report: dict[str, Any],
    en_probe: dict[str, Any], zh_probe: dict[str, Any],
    dataset: dict[str, Any], anchors: dict[str, Any], rubric: dict[str, Any],
    roster: dict[str, Any], judge_instruction: str,
) -> dict[str, Any]:
    """Compare judge outputs descriptively; never recompute or modify scores."""
    validate_anchor_set(anchors, dataset)
    family_id = en_probe.get("family_id")
    family = next((item for item in dataset["families"] if item["family_id"] == family_id), None)
    if family is None or zh_probe.get("family_id") != family_id:
        raise ValueError("Contrast probes are not the same known family")
    expected_hashes = {
        "roster_sha256": sha256_json(roster),
        "dataset_sha256": sha256_json(dataset),
        "rubric_sha256": sha256_json(rubric),
        "criterion_anchors_sha256": sha256_json(anchors),
        "judge_instruction_sha256": sha256_text(judge_instruction),
    }
    judges = {item["provider"]: item for item in roster["judges"]}
    if set(judges) != {"gemini", "grok"}:
        raise ValueError("Paired contrast needs the Gemini/Grok judge roster")
    for language, probe, report in (("en", en_probe, en_report), ("zh-Hans", zh_probe, zh_report)):
        case_id = variant_id(family, language)
        error_ids = {error["id"] for error in family["variants"][language]["turns"][1]["critical_errors"]}
        if (probe.get("status") != "synthetic_unreviewed_development_probe"
            or probe.get("language") != language
            or probe.get("case_content_hash") != variant_hash(family, language)
            or probe.get("expected_unsafe_error_id") not in error_ids
            or report.get("status") != "synthetic_contrast_two_ai_judges_not_clinical_validation"
            or report.get("case_id") != case_id
            or report.get("case_content_hash") != probe["case_content_hash"]
            or report.get("probe_sha256") != sha256_json(probe)
            or report.get("candidate_calls") != 0 or report.get("judge_calls") != 6
            or any(report.get(key) != value for key, value in expected_hashes.items())
            or set(report.get("results", {})) != set(judges)):
            raise ValueError(f"Contrast report is incomplete or wrong-protocol: {language}")
        for provider, result in report["results"].items():
            if (result.get("model_requested") != judges[provider]["model"]
                or set(result.get("variants", {})) != set(VARIANTS)):
                raise ValueError("Contrast report has wrong judge or answer variants")
            for variant, row in result["variants"].items():
                if (not isinstance(row.get("gated_score"), (int, float))
                    or not 0 <= row["gated_score"] <= 100
                    or not isinstance(row.get("pass"), bool)
                    or not isinstance(row.get("criterion_statuses"), list)
                    or len(row["criterion_statuses"]) != 6
                    or any(status not in {"met", "partial", "missed", "unclear"}
                           for status in row["criterion_statuses"])
                    or not isinstance(row.get("critical_error_ids"), list)):
                    raise ValueError("Contrast result row is malformed")
    comparisons = []
    for provider in ("gemini", "grok"):
        en = en_report["results"][provider]
        zh = zh_report["results"][provider]
        for variant in VARIANTS:
            left, right = en["variants"][variant], zh["variants"][variant]
            comparisons.append({
                "judge_provider": provider, "answer_variant": variant,
                "en_score": left["gated_score"], "zh_score": right["gated_score"],
                "zh_minus_en": round(right["gated_score"] - left["gated_score"], 2),
                "same_criterion_statuses": left["criterion_statuses"] == right["criterion_statuses"],
                "en_pass": left["pass"], "zh_pass": right["pass"],
                "pass_mismatch": left["pass"] != right["pass"],
                "en_expected_unsafe_error_detected": en_probe["expected_unsafe_error_id"] in left["critical_error_ids"],
                "zh_expected_unsafe_error_detected": zh_probe["expected_unsafe_error_id"] in right["critical_error_ids"],
            })
    return {
        "status": "descriptive_paired_authored_contrast_not_language_equivalence_or_clinical_validation",
        "family_id": family_id,
        "case_ids": [en_report["case_id"], zh_report["case_id"]],
        "completed_judge_calls": 12,
        "candidate_calls": 0,
        "comparisons": comparisons,
        "same_status_score_gaps_at_least_5": [
            {"judge_provider": row["judge_provider"], "answer_variant": row["answer_variant"],
             "absolute_gap": abs(row["zh_minus_en"])}
            for row in comparisons
            if row["same_criterion_statuses"] and abs(row["zh_minus_en"]) >= 5
        ],
        "limits": [
            "Authored examples and provisional anchors are not clinical or bilingual ground truth.",
            "A score gap with matching criterion statuses does not establish translation bias; holistic dimensions may differ.",
            "No score or pass decision is changed by this audit.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare exact-protocol paired authored judge contrasts offline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--en-report", type=Path, required=True)
    parser.add_argument("--zh-report", type=Path, required=True)
    parser.add_argument("--en-probe", type=Path, required=True)
    parser.add_argument("--zh-probe", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root
    dataset = load_batch_g_dataset(root)
    result = audit_contrast_pair(
        load_json(args.en_report), load_json(args.zh_report),
        load_json(args.en_probe), load_json(args.zh_probe), dataset,
        load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json"),
        load_json(root / "config/multiturn_rubric.json"),
        load_json(root / "config/model_matrix.json"),
        (root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
