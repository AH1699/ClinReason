"""Offline, exact-file audit of the stopped S22 run; never repairs a missing cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import judge_evidence_panel_s21 as base
from . import judge_evidence_panel_s22 as s22
from .config import load_json
from .criterion_anchors import attach_anchors
from .multiturn import variant_id
from .multiturn_diagnostics import contrast_packet
from .multiturn_judging import score_judgment
from .provenance import sha256_json, sha256_text


MISSING = "hc-mt-triage-020_zh/grok-judge__unsafe.judgment.json"


def audit(root: Path, outer: Path) -> dict[str, Any]:
    frozen = s22.plan(root)
    if load_json(outer / "s22-plan.json") != frozen:
        raise ValueError("S22 abort audit plan differs from frozen policy")
    s22._check_connectivity_record(outer / "s22-connectivity-first.json", frozen)
    abort = load_json(outer / "s22-abort-first.json")
    if (abort.get("status") != "s22_first_aborted_do_not_resume_or_pool"
        or abort.get("error_type") != "ProviderRequestError"
        or abort.get("provider_receipt_or_billing") != "unknown"
        or (outer / "first/complete.json").exists()
        or (outer / "s22-first-complete.json").exists()
        or (outer / "repeat").exists()):
        raise ValueError("S22 first stage was not the documented stopped run")
    inputs = base._inputs(root)
    first = outer / "first"
    if load_json(first / "plan.json") != base.plan(root):
        raise ValueError("S22 inner first-stage plan differs from frozen packets")
    expected: dict[str, tuple[dict[str, Any], dict[str, Any], str, str]] = {}
    for key in sorted(inputs["probes"]):
        family, probe = inputs["families"][key[0]], inputs["probes"][key]
        for spec in inputs["roster"]["judges"]:
            for variant in base.VARIANTS:
                name = f"{base._stem(*key)}/{spec['id']}__{variant}.judgment.json"
                expected[name] = family, probe, spec["provider"], variant
    actual = {str(path.relative_to(first)) for path in first.rglob("*.judgment.json")}
    if set(expected) - actual != {MISSING} or actual - set(expected):
        raise ValueError("S22 saved cells are not the exact 23-cell stopped prefix")
    rows = []
    artifact_hashes = []
    for name in sorted(actual):
        family, probe, provider, variant = expected[name]
        spec = next(item for item in inputs["roster"]["judges"] if item["provider"] == provider)
        packet = attach_anchors(contrast_packet(family, probe, variant), inputs["anchors"])
        raw = load_json(first / name)
        score = score_judgment(raw["judgment"], packet, inputs["rubric"])
        if (raw.get("case_id") != variant_id(family, probe["language"])
            or raw.get("case_content_hash") != probe["case_content_hash"]
            or raw.get("probe_sha256") != sha256_json(probe)
            or raw.get("judge_instruction_sha256") != sha256_text(inputs["instruction"])
            or raw.get("criterion_anchors_sha256") != sha256_json(inputs["anchors"])
            or raw.get("rubric_sha256") != sha256_json(inputs["rubric"])
            or raw.get("judge_id") != spec["id"]
            or raw.get("judge_provider") != provider
            or raw.get("judge_model_requested") != spec["model"]
            or not isinstance(raw.get("judge_model_returned"), str)
            or not raw["judge_model_returned"]
            or raw.get("variant") != variant or raw.get("score") != score
            or next(item["packet_sha256"] for item in frozen["packets"]
                    if item["case_id"] == packet["case_id"] and item["answer_type"] == variant)
               != sha256_json(packet)):
            raise ValueError(f"S22 saved cell fails exact packet/protocol/score audit: {name}")
        artifact_hashes.append((name, sha256_json(raw)))
        rows.append({"case_id": packet["case_id"], "provider": provider,
                     "answer_type": variant, "score": score["gated_score"],
                     "pass": score["pass"],
                     "expected_unsafe_error_detected":
                         probe["expected_unsafe_error_id"] in {
                             item["error_id"] for item in raw["judgment"]["critical_errors"]}
                         if variant == "unsafe" else None,
                     "format_flags": base.evidence_format_flags(raw["judgment"]),
                     "returned_model": raw["judge_model_returned"]})
    for key in sorted(inputs["probes"]):
        directory = first / base._stem(*key)
        report_path = directory / "report.json"
        case_rows = [row for row in rows if row["case_id"] == variant_id(inputs["families"][key[0]], key[1])]
        if len(case_rows) == 6:
            report = load_json(report_path)
            if (report.get("roster_sha256") != sha256_json(inputs["roster"])
                or report.get("dataset_sha256") != sha256_json(inputs["dataset"])
                or report.get("criterion_anchors_sha256") != sha256_json(inputs["anchors"])
                or report.get("judge_instruction_sha256") != sha256_text(inputs["instruction"])
                or report.get("rubric_sha256") != sha256_json(inputs["rubric"])
                or report.get("candidate_calls") != 0 or report.get("judge_calls") != 6):
                raise ValueError("S22 complete-family report differs from frozen protocol")
            for variant in base.VARIANTS:
                for provider in ("gemini", "grok"):
                    base._cell(directory, report, inputs["probes"][key], inputs["families"][key[0]],
                               inputs, provider, variant)
        elif len(case_rows) != 5 or report_path.exists():
            raise ValueError("S22 incomplete family contains an unexpected report or cell count")
    if any(len({row["returned_model"] for row in rows if row["provider"] == provider}) != 1
           for provider in ("gemini", "grok")):
        raise ValueError("S22 saved cells have returned-model drift")
    return {"status": "s22_stopped_23_saved_cells_offline_audited_not_full_panel_or_calibration",
            "saved_cells": len(rows), "missing_cell": MISSING,
            "complete_case_language_panels": 3, "incomplete_case_language_panels": 1,
            "full_first_stage_passed": False, "repeat_permitted": False,
            "candidate_calls": 0, "attempted_new_judge_calls": 24,
            "verified_saved_judgments": 23, "last_request_receipt_or_billing": "unknown",
            "saved_artifacts_sha256": sha256_json(artifact_hashes), "rows": rows,
            "limits": "Saved-cell diagnostics only; the planned 24-cell first stage and 8-cell repeat are incomplete. No clinical truth, score calibration, model ranking or pooled S21/S22 result."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the stopped S22 local 23-cell prefix without API calls")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.root, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
