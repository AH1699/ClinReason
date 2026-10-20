"""Offline flags from saved, protocol-matched development judge panels.

No candidate or judge API is called. Counts are diagnostics on unreviewed public
drafts, not a model ranking, clinical validity estimate, or calibration result.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .config import load_json


PANEL_STATUS = "experimental_unvalidated_two_ai_judges_not_clinical_ranking"
CONTRAST_STATUS = "synthetic_contrast_two_ai_judges_not_clinical_validation"
PROTOCOL_FIELDS = (
    "dataset_sha256", "rubric_sha256", "criterion_anchors_sha256",
    "judge_instruction_sha256", "criterion_validator_version",
)


def _case_language(case_id: str) -> tuple[str, str]:
    for suffix, language in (("-ZH-HANS", "zh-Hans"), ("-EN", "en")):
        if case_id.endswith(suffix):
            return case_id[:-len(suffix)], language
    raise ValueError(f"Case ID lacks a supported language suffix: {case_id}")


def _score(value: Any) -> float:
    if type(value) not in (int, float) or not 0 <= value <= 100:
        raise ValueError("Saved judge score must be a number in 0–100")
    return float(value)


def summarize_saved_panels(
    reports: list[dict[str, Any]], *, contrast: dict[str, Any] | None = None,
    flag_gap_at: float = 5.0,
) -> dict[str, Any]:
    """Validate exact protocol/case pairing and describe ceiling and judge gaps."""
    if not reports or not math.isfinite(flag_gap_at) or flag_gap_at < 0:
        raise ValueError("Provide saved panel reports and a finite nonnegative gap threshold")
    first = reports[0]
    if first.get("status") != PANEL_STATUS:
        raise ValueError("Not an unvalidated two-judge development panel")
    protocol = {field: first.get(field) for field in PROTOCOL_FIELDS}
    if any(not value for value in protocol.values()):
        raise ValueError("Saved panel is missing a protocol binding")
    candidate_ids: set[str] = set()
    reference_cases: dict[str, str] | None = None
    reference_judges: set[str] | None = None
    normalized: list[dict[str, Any]] = []
    for report in reports:
        if report.get("status") != PANEL_STATUS or any(
            report.get(field) != value for field, value in protocol.items()
        ):
            raise ValueError("Saved panels have different status or protocol bindings")
        rows = report.get("results")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Saved panel has no results")
        candidate = rows[0].get("candidate_id")
        if not isinstance(candidate, str) or not candidate or candidate in candidate_ids:
            raise ValueError("Candidate panel IDs must be distinct and nonempty")
        candidate_ids.add(candidate)
        cases: dict[str, str] = {}
        judge_ids: set[str] | None = None
        for row in rows:
            case_id = row.get("case_id")
            case_hash = row.get("case_content_hash")
            if (row.get("candidate_id") != candidate or not isinstance(case_id, str)
                or not isinstance(case_hash, str) or not case_hash or case_id in cases):
                raise ValueError("Duplicate or unbound case in saved panel")
            family_id, language = _case_language(case_id)
            cases[case_id] = case_hash
            judges = row.get("judges")
            if not isinstance(judges, list) or len(judges) != 2:
                raise ValueError("Expected two independent saved judge entries")
            this_judges = {judge.get("judge_id") for judge in judges}
            if len(this_judges) != 2 or not all(isinstance(item, str) and item for item in this_judges):
                raise ValueError("Duplicate or missing judge ID")
            if judge_ids is None:
                judge_ids = this_judges
            elif this_judges != judge_ids:
                raise ValueError("Judge set changes within a candidate panel")
            scores = {judge["judge_id"]: _score(judge.get("gated_score")) for judge in judges}
            normalized.append({
                "candidate_id": candidate, "case_id": case_id,
                "family_id": family_id, "language": language,
                "scores": scores,
                "judges": judges,
                "judge_gap": abs(scores[judges[0]["judge_id"]] - scores[judges[1]["judge_id"]]),
            })
        if reference_cases is None:
            reference_cases = cases
            reference_judges = judge_ids
        elif cases != reference_cases or judge_ids != reference_judges:
            raise ValueError("Saved panels do not cover identical case revisions and judges")

    assert reference_cases is not None and reference_judges is not None
    families: dict[str, set[str]] = defaultdict(set)
    for case_id in reference_cases:
        family_id, language = _case_language(case_id)
        families[family_id].add(language)
    if any(languages != {"en", "zh-Hans"} for languages in families.values()):
        raise ValueError("Saved panel must contain complete EN/ZH family pairs")
    by_candidate_judge: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    bilingual: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for row in normalized:
        for judge in row["judges"]:
            judge_id = judge["judge_id"]
            by_candidate_judge[(row["candidate_id"], judge_id)].append(judge)
            bilingual[(row["candidate_id"], judge_id, row["family_id"])][row["language"]] = row["scores"][judge_id]
    judge_summaries = [
        {
            "candidate_id": candidate, "judge_id": judge_id, "case_count": len(judgments),
            "score_100_count": sum(_score(j["gated_score"]) == 100 for j in judgments),
            "score_ge_95_count": sum(_score(j["gated_score"]) >= 95 for j in judgments),
            "hard_fail_count": sum(j["hard_fail"] is True for j in judgments),
            "review_required_count": sum(j["review_required"] is True for j in judgments),
            "same_vendor_as_candidate": all(j["same_vendor_as_candidate"] is True for j in judgments),
        }
        for (candidate, judge_id), judgments in sorted(by_candidate_judge.items())
    ]
    gap_flags = [
        {"candidate_id": row["candidate_id"], "case_id": row["case_id"],
         "language": row["language"], "judge_scores": row["scores"],
         "absolute_gap": row["judge_gap"]}
        for row in normalized if row["judge_gap"] >= flag_gap_at
    ]
    bilingual_flags = [
        {"candidate_id": candidate, "judge_id": judge_id, "family_id": family_id,
         "en_score": scores["en"], "zh_score": scores["zh-Hans"],
         "absolute_gap": abs(scores["en"] - scores["zh-Hans"])}
        for (candidate, judge_id, family_id), scores in sorted(bilingual.items())
        if set(scores) == {"en", "zh-Hans"}
        and abs(scores["en"] - scores["zh-Hans"]) >= flag_gap_at
    ]
    result = {
        "status": "saved_public_development_diagnostic_not_ranking_or_calibration",
        "protocol": protocol,
        "candidate_panel_count": len(reports),
        "paired_case_revision_count": len(reference_cases),
        "judge_ids": sorted(reference_judges),
        "flag_gap_at_points": flag_gap_at,
        "candidate_judge_summaries": judge_summaries,
        "judge_gap_flags": sorted(gap_flags, key=lambda item: (item["candidate_id"], item["case_id"])),
        "bilingual_gap_flags": bilingual_flags,
        "natural_answer_unsafe_false_pass_status": "not_measurable_without_independent_answer_labels",
        "interpretation_limits": [
            "Saved reports cover a small selected public development panel, not the current full case portfolio.",
            "A 100 score or judge agreement is not proof of clinical correctness; an EN/ZH gap is a review flag, not evidence of translation bias.",
            "The output contains no model ranking or target-band fit; no candidate or judge API was called.",
        ],
    }
    if contrast is not None:
        if contrast.get("status") != CONTRAST_STATUS or any(
            contrast.get(field) != protocol[field] for field in
            ("dataset_sha256", "rubric_sha256", "criterion_anchors_sha256", "judge_instruction_sha256")
        ) or contrast.get("case_id") not in reference_cases or {
            judge_id.removesuffix("-judge") for judge_id in contrast.get("results", {})
        } != {judge_id.removesuffix("-judge") for judge_id in reference_judges}:
            raise ValueError("Synthetic contrast does not match saved panel protocol")
        result["synthetic_author_contrast_not_human_truth"] = {
            "case_id": contrast.get("case_id"),
            "judge_flags": {
                judge_id: {
                    "ordered_scores": outcome["ordered_scores"],
                    "unsafe_error_detected": outcome["unsafe_error_detected"],
                    "unsafe_false_pass": outcome["unsafe_false_pass"],
                }
                for judge_id, outcome in sorted(contrast["results"].items())
            },
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect saved public-development judge panels offline")
    parser.add_argument("--report", type=Path, action="append", required=True)
    parser.add_argument("--contrast", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--flag-gap-at", type=float, default=5.0)
    args = parser.parse_args(argv)
    result = summarize_saved_panels(
        [load_json(path) for path in args.report],
        contrast=load_json(args.contrast) if args.contrast else None,
        flag_gap_at=args.flag_gap_at,
    )
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError("Refusing to overwrite an existing diagnostic output")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(json.dumps({"status": result["status"], "output": str(args.output)}))
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
