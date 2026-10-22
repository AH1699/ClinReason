"""Exact-packet, capped S18 repeat of saved S17 judge judgments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import load_json
from .provenance import sha256_json, sha256_text
from .scoring_dimension_evidence_s17 import audit_clean_live, prepare_live_run
from .scoring_dimension_fresh_run import audit_saved as audit_judges
from .scoring_dimension_fresh_run import load_inputs, run_live


POLICY_PATH = "config/judge_repeatability_s18_v1.json"
RUN_STATUS = "s18_exact_packet_repeat_judge_only_not_clinical_validation"
AUDIT_STATUS = "s18_repeatability_description_not_score_calibration"


def prepare(root: Path) -> tuple[dict[str, Any], list[tuple[str, str, dict[str, Any]]], dict[str, Any]]:
    policy = load_json(root / POLICY_PATH)
    if (policy.get("version") != "s18-v1-one-exact-repeat"
        or policy.get("status") != "preregistered_development_repeatability_not_clinical_validation"
        or policy.get("planned_new_judge_calls_max") != 8
        or policy.get("planned_candidate_calls") != 0
        or policy.get("automatic_retries") != 0
        or policy.get("source_probe_path") != "data/multiturn/scoring_dimension_probe_reason015_s17_v2.json"):
        raise ValueError("Unknown S18 repeatability protocol")
    source_dir = root / policy["source_run_path"]
    source_report = load_json(source_dir / "report.json")
    if sha256_json(source_report) != policy["source_report_sha256"]:
        raise ValueError("S17 source report differs from preregistration")
    audit_clean_live(root, source_dir)
    plan, packets = prepare_live_run(root)
    if (plan["judge_calls_required"] != 8 or plan["candidate_calls"] != 0
        or len(packets) != 4):
        raise ValueError("S17 packets exceed the S18 call cap")
    plan = {**plan, "repeat_policy_sha256": sha256_json(policy),
            "repeat_source_report_sha256": policy["source_report_sha256"],
            "gemini_judge_adapter_sha256": sha256_text(
                (root / "benchmark/multiturn_judging.py").read_text(encoding="utf-8")),
            "grok_judge_adapter_sha256": sha256_text(
                (root / "benchmark/providers/grok_multiturn_judge.py").read_text(encoding="utf-8")),
            "warning": policy["interpretation_limit"]}
    return plan, packets, policy


def plan(root: Path) -> dict[str, Any]:
    prepared, packets, policy = prepare(root)
    return {"status": "s18_preregistered_no_api_calls",
            "repeat_policy_sha256": prepared["repeat_policy_sha256"],
            "source_report_sha256": prepared["repeat_source_report_sha256"],
            "probe_sha256": prepared["probe_sha256"],
            "protocol_hashes": {key: prepared[key] for key in (
                "dataset_sha256", "criterion_anchors_sha256", "rubric_sha256",
                "judge_instruction_sha256", "roster_sha256",
                "gemini_judge_adapter_sha256", "grok_judge_adapter_sha256")},
            "packets": prepared["packet_hashes"], "judges": prepared["judges"],
            "new_judge_calls_max": 8, "candidate_calls": 0,
            "sampling": policy["sampling"], "cost_limit": policy["cost_limit"],
            "limits": policy["interpretation_limit"]}


def _cells(directory: Path, report: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    cells = {}
    for item in report["results"]:
        for judge in item["judges"]:
            raw = load_json(directory / judge["judgment_file"])
            judgment = raw["judgment"]
            key = (item["case_id"], item["variant"], judge["judge_id"])
            if key in cells:
                raise ValueError("Duplicate repeated judgment cell")
            cells[key] = {
                "returned_model": raw["judge_model_returned"],
                "update_statuses": [entry["status"] for entry in judgment["criterion_assessments"]
                                    if entry["stage_id"] == "update"],
                "requirements": judgment["stage_scores"][1]["requirements"],
                "safety": judgment["stage_scores"][1]["safety"],
                "revision": judgment["revision_score"],
                "gated_score": raw["score"]["gated_score"],
                "pass": raw["score"]["pass"],
                "judge_requested_human_review": judgment["requires_human_review"],
            }
    return cells


def compare_cells(source: dict[tuple[str, str, str], dict[str, Any]],
                  repeated: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
    if len(source) != 8 or set(source) != set(repeated):
        raise ValueError("S18 exact repeat has missing or unexpected judgment cells")
    comparisons = []
    for key in sorted(source):
        first, second = source[key], repeated[key]
        comparisons.append({
            "case_id": key[0], "variant": key[1], "judge_id": key[2],
            "returned_model_same": first["returned_model"] == second["returned_model"],
            "source": first, "repeat": second,
            "score_delta": round(second["gated_score"] - first["gated_score"], 2),
            "criterion_statuses_same": first["update_statuses"] == second["update_statuses"],
            "dimensions_same": all(first[field] == second[field]
                                   for field in ("requirements", "safety", "revision")),
            "pass_same": first["pass"] == second["pass"],
            "judge_review_request_same": (first["judge_requested_human_review"]
                                          == second["judge_requested_human_review"]),
        })
    return {
        "cells_compared": len(comparisons),
        "exact_score_repeats": sum(row["score_delta"] == 0 for row in comparisons),
        "criterion_status_repeats": sum(row["criterion_statuses_same"] for row in comparisons),
        "dimension_repeats": sum(row["dimensions_same"] for row in comparisons),
        "pass_flag_repeats": sum(row["pass_same"] for row in comparisons),
        "judge_review_request_repeats": sum(row["judge_review_request_same"]
                                            for row in comparisons),
        "returned_model_identity_repeats": sum(row["returned_model_same"] for row in comparisons),
        "max_absolute_score_delta": max(abs(row["score_delta"]) for row in comparisons),
        "comparisons": comparisons,
    }


def audit(root: Path, repeat_dir: Path) -> dict[str, Any]:
    prepared, _packets, policy = prepare(root)
    report = load_json(repeat_dir / "report.json")
    if (report.get("repeat_policy_sha256") != prepared["repeat_policy_sha256"]
        or report.get("repeat_source_report_sha256") != prepared["repeat_source_report_sha256"]
        or any(report.get(key) != prepared[key] for key in (
            "gemini_judge_adapter_sha256", "grok_judge_adapter_sha256"))):
        raise ValueError("S18 repeat report lost source or request-adapter binding")
    inputs = load_inputs(root)
    probe = load_json(root / policy["source_probe_path"])
    verified = audit_judges(inputs, repeat_dir, prepared=(prepared, _packets),
                            hypotheses=probe["author_hypotheses_not_gold"],
                            run_status=RUN_STATUS, audit_status=AUDIT_STATUS)
    source_dir = root / policy["source_run_path"]
    source = _cells(source_dir, load_json(source_dir / "report.json"))
    repeated = _cells(repeat_dir, report)
    return {"status": AUDIT_STATUS, "source_report_sha256": policy["source_report_sha256"],
            "repeat_policy_sha256": prepared["repeat_policy_sha256"],
            "verified_judge_calls": verified["completed_judge_calls"], "candidate_calls": 0,
            **compare_cells(source, repeated), "limits": policy["interpretation_limit"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S18 bounded exact-packet judge repeatability study")
    parser.add_argument("command", choices=("plan", "run", "audit"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = plan(args.root)
    elif args.command == "run":
        if args.output_dir is None:
            parser.error("run requires --output-dir")
        prepared, packets, _policy = prepare(args.root)
        result = run_live(load_inputs(args.root), output_dir=args.output_dir,
                          env_file=args.env_file, max_api_calls=args.max_api_calls,
                          timeout=args.timeout, prepared=(prepared, packets), run_status=RUN_STATUS)
    else:
        if args.output_dir is None:
            parser.error("audit requires --output-dir")
        result = audit(args.root, args.output_dir)
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError("Refusing to overwrite S18 output")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
