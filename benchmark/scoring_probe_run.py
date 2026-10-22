"""Capped judge-only S13 run and read-only comparison of its saved outputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_json
from .frozen_batch_g import load_batch_g_dataset
from .local_settings import read_setting
from .model_matrix import JUDGES, KEYS, _write_json_new
from .multiturn import merge_multiturn_datasets, variant_id
from .multiturn_judging import CRITERION_VALIDATOR_VERSION, score_judgment
from .provenance import sha256_json, sha256_text
from .providers.http_json import ProviderRequestError
from .scoring_probe_prereg import VARIANTS, build_probe_packet, validate_prereg


RUN_STATUS = "synthetic_scoring_probe_two_ai_judges_not_clinical_validation"
AUDIT_STATUS = "descriptive_synthetic_scoring_probe_not_calibration_or_ranking"


def load_inputs(root: Path) -> dict[str, Any]:
    return {
        "prereg": load_json(root / "data/multiturn/scoring_coherence_probes_s13_v1.json"),
        "dataset": load_batch_g_dataset(root),
        "anchors": load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json"),
        "rubric": load_json(root / "config/multiturn_rubric.json"),
        "roster": load_json(root / "config/model_matrix.json"),
        "instruction": (root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip(),
        "base_contrasts": load_json(root / "data/multiturn/batch_g_contrasts_v1.json"),
    }


def prepare_run(inputs: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, str, dict[str, Any]]]]:
    manifest = validate_prereg(inputs["prereg"], inputs["dataset"], inputs["anchors"],
                                inputs["rubric"], inputs["roster"], inputs["instruction"],
                                inputs["base_contrasts"])
    family = next(item for item in inputs["dataset"]["families"]
                  if item["family_id"] == inputs["prereg"]["family_id"])
    packets = [(variant_id(family, item["language"]), variant,
                build_probe_packet(family, item, variant, inputs["anchors"]))
               for item in inputs["prereg"]["languages"] for variant in VARIANTS]
    bound = {(row["case_id"], row["variant"]): row["packet_sha256"]
             for row in manifest["packet_hashes"]}
    if len(packets) != 8 or any(sha256_json(packet) != bound.get((case_id, variant))
                                for case_id, variant, packet in packets):
        raise ValueError("S13 rendered packets differ from frozen manifest")
    plan = {
        "status": "dry_run_no_api_calls",
        "prereg_sha256": manifest["prereg_sha256"],
        "dataset_sha256": sha256_json(inputs["dataset"]),
        "criterion_anchors_sha256": sha256_json(inputs["anchors"]),
        "rubric_sha256": sha256_json(inputs["rubric"]),
        "judge_instruction_sha256": sha256_text(inputs["instruction"]),
        "roster_sha256": sha256_json(inputs["roster"]),
        "criterion_validator_version": CRITERION_VALIDATOR_VERSION,
        "packet_hashes": manifest["packet_hashes"],
        "judges": inputs["roster"]["judges"],
        "candidate_calls": 0, "judge_calls_required": 16,
        "warning": "Author-controlled, unreviewed answers; no clinical truth or score-band fit.",
    }
    return plan, packets


def _judgment_name(judge_id: str, case_id: str, variant: str) -> str:
    return f"{judge_id}__{case_id}__{variant}.judgment.json"


def run_live(
    inputs: dict[str, Any], *, output_dir: Path, env_file: Path,
    max_api_calls: int, timeout: float = 240,
    judge_instances: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """No retry/resume; partial files preserve a stopped run without a complete report."""
    plan, packets = prepare_run(inputs)
    if type(max_api_calls) is not int or max_api_calls != 16 or timeout <= 0:
        raise ValueError("S13 live run requires exactly --max-api-calls 16 and positive timeout")
    if output_dir.exists():
        raise FileExistsError("S13 output directory already exists")
    if judge_instances is None:
        # All credentials are checked before a directory or billable request exists.
        keys = {spec["provider"]: read_setting(env_file, KEYS[spec["provider"]], secret=True)
                for spec in plan["judges"]}
        judge_instances = {
            spec["id"]: JUDGES[spec["provider"]](
                model=spec["model"], api_key=keys[spec["provider"]],
                instruction=inputs["instruction"], timeout=timeout, retries=0,
            ) for spec in plan["judges"]
        }
    if set(judge_instances) != {spec["id"] for spec in plan["judges"]}:
        raise ValueError("S13 judge instances do not match frozen roster")
    output_dir.mkdir(parents=True)
    _write_json_new(output_dir / "plan.json", {**plan, "status": "live_plan_started",
                                                "started_at": datetime.now(timezone.utc).isoformat()})
    results: dict[tuple[str, str], dict[str, Any]] = {
        (case_id, variant): {"case_id": case_id, "case_content_hash": packet["case_content_hash"],
                             "variant": variant, "packet_sha256": sha256_json(packet), "judges": []}
        for case_id, variant, packet in packets
    }
    attempted = 0
    completed = 0
    for spec in plan["judges"]:
        judge = judge_instances[spec["id"]]
        for case_id, variant, packet in packets:
            attempted += 1
            filename = _judgment_name(spec["id"], case_id, variant)
            judge.rejected_output_path = output_dir / filename.replace(".judgment.json", ".rejected.json")
            try:
                judgment = judge.evaluate(packet)
                score = score_judgment(judgment, packet, inputs["rubric"])
                if not isinstance(judge.model_version, str) or not judge.model_version:
                    raise ProviderRequestError("Judge returned no model identity")
                saved = {
                    "status": "experimental_unvalidated_ai_judge",
                    "case_id": case_id, "case_content_hash": packet["case_content_hash"],
                    "variant": variant, "packet_sha256": sha256_json(packet),
                    "prereg_sha256": plan["prereg_sha256"],
                    "rubric_sha256": plan["rubric_sha256"],
                    "criterion_anchors_sha256": plan["criterion_anchors_sha256"],
                    "judge_instruction_sha256": plan["judge_instruction_sha256"],
                    "criterion_validator_version": CRITERION_VALIDATOR_VERSION,
                    "judge_id": spec["id"], "judge_provider": spec["provider"],
                    "judge_model_requested": spec["model"],
                    "judge_model_returned": judge.model_version,
                    "judgment": judgment, "score": score,
                }
                _write_json_new(output_dir / filename, saved)
                completed += 1
                results[(case_id, variant)]["judges"].append({
                    "judge_id": spec["id"], "provider": spec["provider"],
                    "model_requested": spec["model"], "model_returned": judge.model_version,
                    "judgment_file": filename, "gated_score": score["gated_score"],
                    "pass": score["pass"],
                })
            except (ProviderRequestError, ValueError, TypeError, OSError) as exc:
                _write_json_new(output_dir / "failure.json", {
                    "status": "stopped_partial_result_delivery_uncertain",
                    "attempted_calls": attempted, "completed_judgments": completed,
                    "failed_judge_id": spec["id"], "failed_case_id": case_id,
                    "failed_variant": variant, "error_type": type(exc).__name__,
                    "note": "No automatic retry or candidate replay; inspect partial artifacts before any new plan.",
                })
                raise ProviderRequestError("S13 run stopped; see local failure.json") from None
    report = {
        "status": RUN_STATUS, "completed_at": datetime.now(timezone.utc).isoformat(),
        **{key: value for key, value in plan.items() if key not in ("status", "warning")},
        "candidate_calls": 0, "judge_calls": completed,
        "results": list(results.values()),
        "limits": "Synthetic author hypotheses; not clinical or bilingual validation, model ranking or calibrated scores.",
    }
    _write_json_new(output_dir / "report.json", report)
    return {"status": RUN_STATUS, "output_dir": str(output_dir),
            "candidate_calls": 0, "judge_calls": completed,
            "report": str(output_dir / "report.json")}


def audit_saved(inputs: dict[str, Any], directory: Path) -> dict[str, Any]:
    """Rebuild packets and scores from immutable local exports, then describe contrasts."""
    plan, packets = prepare_run(inputs)
    report = load_json(directory / "report.json")
    if (report.get("status") != RUN_STATUS or report.get("candidate_calls") != 0
        or report.get("judge_calls") != 16
        or report.get("judge_calls_required") != 16
        or any(report.get(key) != plan[key] for key in (
            "prereg_sha256", "dataset_sha256", "criterion_anchors_sha256", "rubric_sha256",
            "judge_instruction_sha256", "roster_sha256", "criterion_validator_version",
            "packet_hashes", "judges"))
        or not isinstance(report.get("results"), list) or len(report["results"]) != 8):
        raise ValueError("S13 report is incomplete or not bound to the frozen protocol")
    expected_packets = {(case_id, variant): packet for case_id, variant, packet in packets}
    expected_judges = {spec["id"]: spec for spec in plan["judges"]}
    seen: set[tuple[str, str]] = set()
    used_files: set[str] = set()
    normalized: dict[tuple[str, str, str], dict[str, Any]] = {}
    returned_models: dict[str, str] = {}
    for result in report["results"]:
        key = (result.get("case_id"), result.get("variant"))
        if key in seen or key not in expected_packets:
            raise ValueError("Duplicate or unknown S13 case/variant")
        seen.add(key)
        packet = expected_packets[key]
        if (result.get("case_content_hash") != packet["case_content_hash"]
            or result.get("packet_sha256") != sha256_json(packet)
            or not isinstance(result.get("judges"), list)
            or len(result["judges"]) != 2
            or {judge.get("judge_id") for judge in result["judges"]} != set(expected_judges)):
            raise ValueError("S13 result has wrong packet or judge pairing")
        for entry in result["judges"]:
            spec = expected_judges[entry["judge_id"]]
            filename = _judgment_name(spec["id"], key[0], key[1])
            if entry.get("judgment_file") != filename or filename in used_files:
                raise ValueError("S13 judgment file list differs from report")
            used_files.add(filename)
            row = load_json(directory / filename)
            if (row.get("status") != "experimental_unvalidated_ai_judge"
                or any(row.get(field) != value for field, value in (
                    ("case_id", key[0]), ("case_content_hash", packet["case_content_hash"]),
                    ("variant", key[1]), ("packet_sha256", sha256_json(packet)),
                    ("prereg_sha256", plan["prereg_sha256"]),
                    ("rubric_sha256", plan["rubric_sha256"]),
                    ("criterion_anchors_sha256", plan["criterion_anchors_sha256"]),
                    ("judge_instruction_sha256", plan["judge_instruction_sha256"]),
                    ("criterion_validator_version", CRITERION_VALIDATOR_VERSION),
                    ("judge_id", spec["id"]), ("judge_provider", spec["provider"]),
                    ("judge_model_requested", spec["model"])))
                or entry.get("provider") != spec["provider"]
                or entry.get("model_requested") != spec["model"]
                or row.get("judge_model_returned") != entry.get("model_returned")
                or not isinstance(row.get("judge_model_returned"), str)
                or not row["judge_model_returned"]):
                raise ValueError("S13 raw judgment conflicts with report or protocol")
            previous_model = returned_models.setdefault(spec["id"], row["judge_model_returned"])
            if previous_model != row["judge_model_returned"]:
                raise ValueError("Judge model identity changed within S13 run")
            score = score_judgment(row["judgment"], packet, inputs["rubric"])
            if (row.get("score") != score or entry.get("gated_score") != score["gated_score"]
                or entry.get("pass") != score["pass"]):
                raise ValueError("S13 saved score does not recompute")
            assessments = row["judgment"]["criterion_assessments"]
            normalized[(key[0], key[1], spec["id"])] = {
                "case_id": key[0], "variant": key[1], "judge_id": spec["id"],
                "update_statuses": [item["status"] for item in assessments if item["stage_id"] == "update"],
                "initial_statuses": [item["status"] for item in assessments if item["stage_id"] == "initial"],
                "safety": row["judgment"]["stage_scores"][1]["safety"],
                "requirements": row["judgment"]["stage_scores"][1]["requirements"],
                "revision": row["judgment"]["revision_score"],
                "raw_score": score["raw_score"], "gated_score": score["gated_score"],
                "pass": score["pass"],
                "critical_error_ids": [item["error_id"] for item in row["judgment"]["critical_errors"]],
                "requires_human_review": row["judgment"]["requires_human_review"],
                "judgment_file": filename,
            }
    if seen != set(expected_packets) or used_files != {
        _judgment_name(spec["id"], case_id, variant)
        for case_id, variant in expected_packets for spec in plan["judges"]
    }:
        raise ValueError("S13 report omits a frozen judgment")
    if {path.name for path in directory.glob("*.judgment.json")} != used_files:
        raise ValueError("S13 directory includes unexpected or missing judgment files")
    contrasts = []
    hypotheses = inputs["prereg"]["author_hypotheses_not_gold"]
    baseline_checks = [
        {"case_id": case_id, "judge_id": spec["id"],
         "observed_update_statuses": normalized[(case_id, "baseline", spec["id"])]["update_statuses"],
         "author_hypothesis_match": normalized[(case_id, "baseline", spec["id"])]["update_statuses"]
                                    == hypotheses["baseline"]}
        for case_id, variant in expected_packets if variant == "baseline"
        for spec in plan["judges"]
    ]
    for case_id, variant, _ in packets:
        if variant == "baseline":
            continue
        for spec in plan["judges"]:
            baseline = normalized[(case_id, "baseline", spec["id"])]
            current = normalized[(case_id, variant, spec["id"])]
            contrasts.append({
                "case_id": case_id, "judge_id": spec["id"], "variant": variant,
                "targeted_status_hypothesis": hypotheses[variant],
                "observed_update_statuses": current["update_statuses"],
                "targeted_status_match": current["update_statuses"] == hypotheses[variant],
                "initial_statuses_unchanged": current["initial_statuses"] == baseline["initial_statuses"],
                "delta_from_baseline": {key: round(current[key] - baseline[key], 2)
                                        for key in ("safety", "requirements", "revision", "raw_score", "gated_score")},
                "pass_flip": current["pass"] != baseline["pass"],
                "critical_error_ids": current["critical_error_ids"],
                "review_requested": current["requires_human_review"],
                "safety_and_revision_both_lower": current["safety"] < baseline["safety"]
                and current["revision"] < baseline["revision"],
            })
    judge_pairs = []
    for case_id, variant in expected_packets:
        left, right = (normalized[(case_id, variant, spec["id"])] for spec in plan["judges"])
        judge_pairs.append({
            "case_id": case_id, "variant": variant,
            "same_update_statuses": left["update_statuses"] == right["update_statuses"],
            "gated_score_gap": abs(left["gated_score"] - right["gated_score"]),
            "pass_split": left["pass"] != right["pass"],
            "judge_scores": {left["judge_id"]: left["gated_score"], right["judge_id"]: right["gated_score"]},
        })
    bilingual_counterparts = []
    for variant in VARIANTS:
        for spec in plan["judges"]:
            en = normalized[("HC-MT-TRIAGE-020-EN", variant, spec["id"])]
            zh = normalized[("HC-MT-TRIAGE-020-ZH-HANS", variant, spec["id"])]
            bilingual_counterparts.append({
                "variant": variant, "judge_id": spec["id"],
                "same_update_statuses": en["update_statuses"] == zh["update_statuses"],
                "en_gated_score": en["gated_score"], "zh_gated_score": zh["gated_score"],
                "absolute_gap": abs(en["gated_score"] - zh["gated_score"]),
                "pass_split": en["pass"] != zh["pass"],
                "semantic_equivalence_unreviewed": True,
            })
    return {
        "status": AUDIT_STATUS, "prereg_sha256": plan["prereg_sha256"],
        "completed_judge_calls": 16, "candidate_calls": 0,
        "baseline_checks": baseline_checks, "contrasts": contrasts,
        "judge_pairs": judge_pairs, "bilingual_counterparts": bilingual_counterparts,
        "limits": [
            "Author status hypotheses are not human truth; a mismatch is a review question, not an automatic judge error.",
            "EN/ZH authored counterparts are not proven equivalent; no pooled score or model ranking is produced.",
            "Safety and revision can reflect different harms; both falling is an overlap-review flag, not a double-counting verdict.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S13 judge-only run and saved comparison")
    parser.add_argument("command", choices=("plan", "run", "audit"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args(argv)
    inputs = load_inputs(args.root)
    try:
        if args.command == "plan":
            result, _ = prepare_run(inputs)
        elif args.command == "run":
            if args.output_dir is None:
                raise ValueError("--output-dir is required for run")
            if not args.output_dir.resolve().is_relative_to((args.root / "work").resolve()):
                raise ValueError("Live S13 output must be under ignored work/")
            result = run_live(inputs, output_dir=args.output_dir, env_file=args.env_file,
                              max_api_calls=args.max_api_calls, timeout=args.timeout)
        else:
            if args.output_dir is None:
                raise ValueError("--output-dir is required for audit")
            result = audit_saved(inputs, args.output_dir)
            if args.report_output:
                if args.report_output.exists():
                    raise FileExistsError("Refusing to overwrite an audit output")
                _write_json_new(args.report_output, result)
    except (ProviderRequestError, ValueError, FileExistsError, OSError, KeyError, TypeError) as exc:
        # Provider transport/body details and local secret values never reach stdout.
        print(f"S13 {args.command} failed: {type(exc).__name__}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
