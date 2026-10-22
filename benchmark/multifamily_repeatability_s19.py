"""Bounded exact-packet repeat of saved S9/S11 authored contrasts; never rescoring history."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .batch_g_contrasts import select_contrast
from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .frozen_batch_g import load_batch_g_dataset
from .model_matrix import run_anchored_contrast
from .multiturn import variant_id
from .multiturn_diagnostics import contrast_packet
from .multiturn_judging import score_judgment
from .provenance import sha256_json, sha256_text


POLICY_PATH = "config/multifamily_repeatability_s19_v1.json"
VARIANTS = ("safe", "partial", "unsafe")


def _inputs(root: Path) -> dict[str, Any]:
    policy = load_json(root / POLICY_PATH)
    dataset = load_batch_g_dataset(root)
    anchors = load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json")
    validate_anchor_set(anchors, dataset)
    return {
        "policy": policy, "dataset": dataset, "anchors": anchors,
        "rubric": load_json(root / "config/multiturn_rubric.json"),
        "roster": load_json(root / "config/model_matrix.json"),
        "instruction": (root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip(),
    }


def _probe(root: Path, row: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    if row["family_id"] == "HC-MT-TRIAGE-018":
        source = load_json(root / row["probe_path"])
        suffix = "EN" if row["language"] == "en" else "ZH-HANS"
        return select_contrast(source, f"{row['family_id']}-{suffix}",
                               inputs["dataset"], inputs["anchors"])
    return load_json(root / row["probe_path"])


def _cell(directory: Path, report: dict[str, Any], probe: dict[str, Any],
          family: dict[str, Any], inputs: dict[str, Any], provider: str,
          variant: str) -> dict[str, Any]:
    spec = next(item for item in inputs["roster"]["judges"] if item["provider"] == provider)
    path = directory / f"{spec['id']}__{variant}.judgment.json"
    raw = load_json(path)
    packet = attach_anchors(contrast_packet(family, probe, variant), inputs["anchors"])
    score = score_judgment(raw["judgment"], packet, inputs["rubric"])
    summary = report["results"][provider]["variants"][variant]
    if (raw.get("case_id") != report["case_id"]
        or raw.get("case_content_hash") != probe["case_content_hash"]
        or raw.get("probe_sha256") != sha256_json(probe)
        or raw.get("judge_id") != spec["id"]
        or raw.get("judge_provider") != provider
        or raw.get("judge_model_requested") != spec["model"]
        or raw.get("judge_model_returned") != report["results"][provider]["model_returned"]
        or raw.get("variant") != variant
        or raw.get("judge_instruction_sha256") != report["judge_instruction_sha256"]
        or raw.get("criterion_anchors_sha256") != report["criterion_anchors_sha256"]
        or raw.get("rubric_sha256") != report["rubric_sha256"]
        or sha256_json(raw.get("score")) != sha256_json(score)
        or score["gated_score"] != summary["gated_score"]
        or score["pass"] != summary["pass"]
        or [item["status"] for item in raw["judgment"]["criterion_assessments"]] != summary["criterion_statuses"]
        or [item["error_id"] for item in raw["judgment"]["critical_errors"]] != summary["critical_error_ids"]):
        raise ValueError("Saved judgment does not match exact report, packet or rubric")
    judgment = raw["judgment"]
    return {
        "returned_model": raw["judge_model_returned"],
        "criterion_statuses": summary["criterion_statuses"],
        "requirements": judgment["stage_scores"][1]["requirements"],
        "safety": judgment["stage_scores"][1]["safety"],
        "revision": judgment["revision_score"],
        "critical_errors": [(item["error_id"], item["severity"])
                            for item in judgment["critical_errors"]],
        "score": score["gated_score"], "pass": score["pass"],
        "human_review": judgment["requires_human_review"],
    }


def prepare(root: Path) -> tuple[dict[str, Any], list[tuple[dict[str, Any], dict[str, Any]]]]:
    inputs = _inputs(root)
    policy = inputs["policy"]
    rows = policy.get("historical_first_observations", [])
    if (policy.get("version") != "s19-v1-preregistered-plan-no-calls"
        or policy.get("status") != "prospective_development_protocol_not_scoring_contract"
        or policy.get("planned_new_judge_calls_max") != 24
        or policy.get("planned_candidate_calls") != 0 or policy.get("automatic_retries") != 0
        or len(rows) != 4
        or {(row["family_id"], row["language"]) for row in rows} !=
           {(family, lang) for family in policy["family_ids"] for lang in policy["languages"]}
        or policy.get("answer_types") != list(VARIANTS)):
        raise ValueError("Unknown or incomplete S19 policy")
    if any(sha256_text((root / path).read_text(encoding="utf-8")) != digest
           for path, digest in policy["adapter_sha256_at_source_and_now"].items()):
        raise ValueError("Judge adapter changed from saved S9/S11 revisions")
    expected_hashes = {
        "roster_sha256": sha256_json(inputs["roster"]),
        "dataset_sha256": sha256_json(inputs["dataset"]),
        "rubric_sha256": sha256_json(inputs["rubric"]),
        "criterion_anchors_sha256": sha256_json(inputs["anchors"]),
        "judge_instruction_sha256": sha256_text(inputs["instruction"]),
    }
    selected = []
    packet_hashes = []
    for row in rows:
        family = next(item for item in inputs["dataset"]["families"]
                      if item["family_id"] == row["family_id"])
        probe = _probe(root, row, inputs)
        directory = root / row["source_dir"]
        report = load_json(directory / "report.json")
        if (sha256_json(report) != row["report_sha256"]
            or report.get("status") != "synthetic_contrast_two_ai_judges_not_clinical_validation"
            or report.get("case_id") != variant_id(family, row["language"])
            or report.get("case_content_hash") != probe["case_content_hash"]
            or report.get("probe_sha256") != sha256_json(probe)
            or report.get("candidate_calls") != 0 or report.get("judge_calls") != 6
            or any(report.get(key) != value for key, value in expected_hashes.items())
            or set(report.get("results", {})) != {"gemini", "grok"}):
            raise ValueError("Historical contrast report is incompatible")
        for variant in VARIANTS:
            packet = attach_anchors(contrast_packet(family, probe, variant), inputs["anchors"])
            packet_hashes.append({"case_id": report["case_id"], "variant": variant,
                                  "packet_sha256": sha256_json(packet)})
            for provider in ("gemini", "grok"):
                _cell(directory, report, probe, family, inputs, provider, variant)
        selected.append((row, probe))
    plan = {"status": "s19_source_packets_audited_no_api_calls",
            "policy_sha256": sha256_json(policy), "source_report_sha256": [row["report_sha256"] for row in rows],
            "protocol_hashes": expected_hashes, "packet_hashes": packet_hashes,
            "historical_judgments_verified": 24, "planned_new_judge_calls_max": 24,
            "candidate_calls": 0, "limits": policy["interpretation_limit"]}
    return plan, selected


def compare_cells(first: dict[tuple[str, str, str], dict[str, Any]],
                  second: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
    if len(first) != 24 or set(first) != set(second):
        raise ValueError("S19 repeat is incomplete or has unexpected cells")
    rows = []
    for key in sorted(first):
        left, right = first[key], second[key]
        rows.append({"case_id": key[0], "answer_type": key[1], "judge": key[2],
                     "score_delta": round(right["score"] - left["score"], 2),
                     "score_same": left["score"] == right["score"],
                     "statuses_same": left["criterion_statuses"] == right["criterion_statuses"],
                     "dimensions_same": all(left[name] == right[name] for name in ("requirements", "safety", "revision")),
                     "critical_errors_same": left["critical_errors"] == right["critical_errors"],
                     "pass_same": left["pass"] == right["pass"],
                     "review_same": left["human_review"] == right["human_review"],
                     "returned_model_same": left["returned_model"] == right["returned_model"]})
    return {"status": "descriptive_s19_repeatability_not_clinical_or_score_calibration",
            "cells": len(rows), "exact_score_repeats": sum(row["score_same"] for row in rows),
            "status_repeats": sum(row["statuses_same"] for row in rows),
            "dimension_repeats": sum(row["dimensions_same"] for row in rows),
            "critical_error_repeats": sum(row["critical_errors_same"] for row in rows),
            "pass_repeats": sum(row["pass_same"] for row in rows),
            "review_repeats": sum(row["review_same"] for row in rows),
            "model_identity_repeats": sum(row["returned_model_same"] for row in rows),
            "comparisons": rows}


def run(root: Path, target: Path, *, env_file: Path, max_api_calls: int, timeout: float) -> dict[str, Any]:
    if max_api_calls != 24 or timeout <= 0:
        raise ValueError("S19 run requires --max-api-calls 24 and positive timeout")
    if not target.resolve().is_relative_to((root / "work").resolve()) or target.exists():
        raise ValueError("S19 output must be a fresh ignored work/ directory")
    plan, selected = prepare(root)
    inputs = _inputs(root)
    target.mkdir(parents=True)
    (target / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row, probe in selected:
        name = f"{row['family_id'].lower()}_{'en' if row['language'] == 'en' else 'zh'}"
        run_anchored_contrast(probe, inputs["roster"], inputs["dataset"],
                              inputs["rubric"], inputs["anchors"], output_dir=target / name,
                              env_file=env_file, judge_instruction=inputs["instruction"],
                              max_api_calls=6, timeout=timeout)
    complete = {"status": "s19_complete_24_judge_calls_no_candidate_calls",
                "policy_sha256": plan["policy_sha256"], "protocol_hashes": plan["protocol_hashes"],
                "source_report_sha256": plan["source_report_sha256"]}
    (target / "complete.json").write_text(json.dumps(complete, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return complete


def audit(root: Path, target: Path) -> dict[str, Any]:
    plan, selected = prepare(root)
    complete = load_json(target / "complete.json")
    if (complete.get("status") != "s19_complete_24_judge_calls_no_candidate_calls"
        or any(complete.get(name) != plan[name] for name in
               ("policy_sha256", "protocol_hashes", "source_report_sha256"))):
        raise ValueError("S19 repeat completion record does not match frozen plan")
    inputs = _inputs(root)
    first, second = {}, {}
    for row, probe in selected:
        family = next(item for item in inputs["dataset"]["families"]
                      if item["family_id"] == row["family_id"])
        source_dir = root / row["source_dir"]
        repeat_dir = target / f"{row['family_id'].lower()}_{'en' if row['language'] == 'en' else 'zh'}"
        source_report = load_json(source_dir / "report.json")
        repeat_report = load_json(repeat_dir / "report.json")
        if any(repeat_report.get(name) != source_report.get(name) for name in
               ("case_id", "case_content_hash", "probe_sha256", "roster_sha256", "dataset_sha256",
                "rubric_sha256", "criterion_anchors_sha256", "judge_instruction_sha256", "judge_calls", "candidate_calls")):
            raise ValueError("S19 repeated report has a protocol mismatch")
        for variant in VARIANTS:
            for provider in ("gemini", "grok"):
                key = (source_report["case_id"], variant, provider)
                first[key] = _cell(source_dir, source_report, probe, family, inputs, provider, variant)
                second[key] = _cell(repeat_dir, repeat_report, probe, family, inputs, provider, variant)
    return {**compare_cells(first, second), "policy_sha256": plan["policy_sha256"],
            "limits": inputs["policy"]["interpretation_limit"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S19 bounded multi-family exact-packet judge repeat")
    parser.add_argument("command", choices=("plan", "run", "audit"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = prepare(args.root)[0]
    elif args.command == "run":
        if args.output_dir is None:
            parser.error("run requires --output-dir")
        result = run(args.root, args.output_dir, env_file=args.env_file,
                     max_api_calls=args.max_api_calls, timeout=args.timeout)
    else:
        if args.output_dir is None:
            parser.error("audit requires --output-dir")
        result = audit(args.root, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
