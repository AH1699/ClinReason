"""Bounded judge-only run of the frozen S15 cross-mechanism answer probe."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_json
from .frozen_batch_g import load_batch_g_dataset
from .criterion_anchors import attach_anchors, validate_anchor_set
from .local_settings import read_setting
from .model_matrix import JUDGES, KEYS, _write_json_new
from .multiturn import build_judge_packet, merge_multiturn_datasets, variant_id
from .multiturn_judging import CRITERION_VALIDATOR_VERSION, score_judgment
from .provenance import sha256_json, sha256_text
from .providers.http_json import ProviderRequestError
from .scoring_dimension_hypothesis import POLICY_PATH, validate_fresh_probe


RUN_STATUS = "s15_synthetic_judge_only_not_clinical_validation"
AUDIT_STATUS = "s15_saved_cross_mechanism_description_not_calibration"
VARIANTS = ("baseline", "omission")


def load_inputs(root: Path) -> dict[str, Any]:
    return {
        "root": root,
        "policy": load_json(root / POLICY_PATH),
        "dataset": load_batch_g_dataset(root),
        "anchors": load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json"),
        "rubric": load_json(root / "config/multiturn_rubric.json"),
        "roster": load_json(root / "config/model_matrix.json"),
        "instruction": (root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip(),
    }


def prepare_run(inputs: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, str, dict[str, Any]]]]:
    root, dataset, anchors = inputs["root"], inputs["dataset"], inputs["anchors"]
    manifest = validate_fresh_probe(root, dataset, inputs["policy"])
    validate_anchor_set(anchors, dataset)
    probe = load_json(root / inputs["policy"]["fresh_probe_path"])
    family = next(item for item in dataset["families"] if item["family_id"] == probe["family_id"])
    judges = inputs["roster"]["judges"]
    if (len(judges) != 2 or {item["id"] for item in judges} != {"gemini-judge", "grok-judge"}
        or {item["provider"] for item in judges} != {"gemini", "grok"}):
        raise ValueError("S15 requires the frozen two-judge roster")
    packets = []
    for item in probe["languages"]:
        language = item["language"]
        for variant in VARIANTS:
            response = item["separator"].join(item["base_update_segments"][:3 if variant == "baseline" else 2])
            transcript = []
            for turn, answer in zip(family["variants"][language]["turns"],
                                    (item["initial_response"], response)):
                transcript.extend([{"role": "user", "content": turn["user"]},
                                   {"role": "assistant", "content": answer}])
            candidate_response = {
                "case_id": variant_id(family, language), "case_version": family["version"],
                "case_content_hash": item["case_content_hash"], "transcript": transcript,
                "turn_outputs": [{"stage_id": "initial", "text": item["initial_response"]},
                                 {"stage_id": "update", "text": response}],
            }
            packet = attach_anchors(build_judge_packet(family, language, candidate_response), anchors)
            packets.append((packet["case_id"], variant, packet))
    if len(packets) != 4 or len({(case_id, variant) for case_id, variant, _ in packets}) != 4:
        raise ValueError("S15 requires four distinct case/answer packets")
    plan = {
        "status": "dry_run_no_api_calls", "policy_sha256": sha256_json(inputs["policy"]),
        "probe_sha256": manifest["probe_sha256"], "dataset_sha256": sha256_json(dataset),
        "criterion_anchors_sha256": sha256_json(anchors),
        "rubric_sha256": sha256_json(inputs["rubric"]),
        "judge_instruction_sha256": sha256_text(inputs["instruction"]),
        "roster_sha256": sha256_json(inputs["roster"]),
        "criterion_validator_version": CRITERION_VALIDATOR_VERSION,
        "packet_hashes": [{"case_id": case_id, "variant": variant,
                           "case_content_hash": packet["case_content_hash"],
                           "packet_sha256": sha256_json(packet)}
                          for case_id, variant, packet in packets],
        "judges": judges, "candidate_calls": 0, "judge_calls_required": 8,
        "warning": "Author-controlled answers; no clinical truth, score calibration or score-band fit.",
    }
    return plan, packets


def _filename(judge_id: str, case_id: str, variant: str) -> str:
    return f"{judge_id}__{case_id}__{variant}.judgment.json"


def run_live(inputs: dict[str, Any], *, output_dir: Path, env_file: Path,
             max_api_calls: int, timeout: float = 240,
             judge_instances: dict[str, Any] | None = None,
             prepared: tuple[dict[str, Any], list[tuple[str, str, dict[str, Any]]]] | None = None,
             run_status: str = RUN_STATUS) -> dict[str, Any]:
    plan, packets = prepared if prepared is not None else prepare_run(inputs)
    if type(max_api_calls) is not int or max_api_calls != 8 or timeout <= 0:
        raise ValueError("S15 live run requires exactly --max-api-calls 8 and positive timeout")
    if output_dir.exists():
        raise FileExistsError("S15 output directory already exists")
    if judge_instances is None:
        keys = {spec["provider"]: read_setting(env_file, KEYS[spec["provider"]], secret=True)
                for spec in plan["judges"]}
        judge_instances = {
            spec["id"]: JUDGES[spec["provider"]](
                model=spec["model"], api_key=keys[spec["provider"]],
                instruction=inputs["instruction"], timeout=timeout, retries=0,
            ) for spec in plan["judges"]
        }
    if set(judge_instances) != {spec["id"] for spec in plan["judges"]}:
        raise ValueError("S15 judge instances do not match roster")
    output_dir.mkdir(parents=True)
    _write_json_new(output_dir / "plan.json", {**plan, "status": "live_plan_started",
                                                "started_at": datetime.now(timezone.utc).isoformat()})
    results = {
        (case_id, variant): {"case_id": case_id, "case_content_hash": packet["case_content_hash"],
                             "variant": variant, "packet_sha256": sha256_json(packet), "judges": []}
        for case_id, variant, packet in packets
    }
    attempted = completed = 0
    for spec in plan["judges"]:
        judge = judge_instances[spec["id"]]
        for case_id, variant, packet in packets:
            attempted += 1
            filename = _filename(spec["id"], case_id, variant)
            judge.rejected_output_path = output_dir / filename.replace(".judgment.json", ".rejected.json")
            try:
                judgment = judge.evaluate(packet)
                score = score_judgment(judgment, packet, inputs["rubric"])
                if not isinstance(judge.model_version, str) or not judge.model_version:
                    raise ProviderRequestError("Judge returned no model identity")
                saved = {
                    "status": "experimental_unvalidated_ai_judge", "case_id": case_id,
                    "case_content_hash": packet["case_content_hash"], "variant": variant,
                    "packet_sha256": sha256_json(packet),
                    **{key: plan[key] for key in ("policy_sha256", "probe_sha256", "rubric_sha256",
                                                  "criterion_anchors_sha256", "judge_instruction_sha256",
                                                  "criterion_validator_version")},
                    "judge_id": spec["id"], "judge_provider": spec["provider"],
                    "judge_model_requested": spec["model"], "judge_model_returned": judge.model_version,
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
                    "status": "stopped_partial_result_delivery_uncertain", "attempted_calls": attempted,
                    "completed_judgments": completed, "failed_judge_id": spec["id"],
                    "failed_case_id": case_id, "failed_variant": variant,
                    "error_type": type(exc).__name__,
                    "note": "No automatic retry or candidate replay; inspect partial artifacts before a new plan.",
                })
                raise ProviderRequestError("S15 run stopped; see local failure.json") from None
    report = {
        "status": run_status, "completed_at": datetime.now(timezone.utc).isoformat(),
        **{key: value for key, value in plan.items() if key not in ("status", "warning")},
        "candidate_calls": 0, "judge_calls": completed, "results": list(results.values()),
        "limits": "Synthetic authored answers, not clinical/bilingual validation or model ranking.",
    }
    _write_json_new(output_dir / "report.json", report)
    return {"status": run_status, "output_dir": str(output_dir), "judge_calls": completed,
            "candidate_calls": 0, "report": str(output_dir / "report.json")}


def audit_saved(inputs: dict[str, Any], directory: Path, *,
                prepared: tuple[dict[str, Any], list[tuple[str, str, dict[str, Any]]]] | None = None,
                hypotheses: dict[str, Any] | None = None,
                run_status: str = RUN_STATUS, audit_status: str = AUDIT_STATUS) -> dict[str, Any]:
    plan, packets = prepared if prepared is not None else prepare_run(inputs)
    if hypotheses is None:
        hypotheses = load_json(inputs["root"] / inputs["policy"]["fresh_probe_path"])["author_hypotheses_not_gold"]
    report = load_json(directory / "report.json")
    fields = ("policy_sha256", "probe_sha256", "dataset_sha256", "criterion_anchors_sha256",
              "rubric_sha256", "judge_instruction_sha256", "roster_sha256",
              "criterion_validator_version", "packet_hashes", "judges", "judge_calls_required")
    if (report.get("status") != run_status or report.get("candidate_calls") != 0
        or report.get("judge_calls") != 8
        or any(report.get(key) != plan[key] for key in fields)
        or not isinstance(report.get("results"), list) or len(report["results"]) != 4):
        raise ValueError("S15 report is incomplete or has the wrong frozen protocol")
    expected_packets = {(case_id, variant): packet for case_id, variant, packet in packets}
    expected_judges = {spec["id"]: spec for spec in plan["judges"]}
    seen, used_files = set(), set()
    normalized = {}
    returned_models = {}
    for result in report["results"]:
        key = (result.get("case_id"), result.get("variant"))
        if key in seen or key not in expected_packets:
            raise ValueError("Duplicate or unknown S15 result")
        seen.add(key)
        packet = expected_packets[key]
        if (result.get("case_content_hash") != packet["case_content_hash"]
            or result.get("packet_sha256") != sha256_json(packet)
            or not isinstance(result.get("judges"), list) or len(result["judges"]) != 2
            or {item.get("judge_id") for item in result["judges"]} != set(expected_judges)):
            raise ValueError("S15 result has wrong packet or judge pairing")
        for entry in result["judges"]:
            spec = expected_judges[entry["judge_id"]]
            filename = _filename(spec["id"], *key)
            if entry.get("judgment_file") != filename or filename in used_files:
                raise ValueError("S15 judge file list differs from report")
            used_files.add(filename)
            row = load_json(directory / filename)
            bindings = {
                "status": "experimental_unvalidated_ai_judge", "case_id": key[0],
                "case_content_hash": packet["case_content_hash"], "variant": key[1],
                "packet_sha256": sha256_json(packet), "judge_id": spec["id"],
                "judge_provider": spec["provider"], "judge_model_requested": spec["model"],
                **{field: plan[field] for field in ("policy_sha256", "probe_sha256", "rubric_sha256",
                                                   "criterion_anchors_sha256", "judge_instruction_sha256",
                                                   "criterion_validator_version")},
            }
            if (any(row.get(field) != value for field, value in bindings.items())
                or entry.get("provider") != spec["provider"]
                or entry.get("model_requested") != spec["model"]
                or row.get("judge_model_returned") != entry.get("model_returned")
                or not isinstance(row.get("judge_model_returned"), str)
                or not row["judge_model_returned"]):
                raise ValueError("S15 raw judgment conflicts with report or protocol")
            previous = returned_models.setdefault(spec["id"], row["judge_model_returned"])
            if previous != row["judge_model_returned"]:
                raise ValueError("S15 judge model identity changed during run")
            score = score_judgment(row["judgment"], packet, inputs["rubric"])
            if (row.get("score") != score or entry.get("gated_score") != score["gated_score"]
                or entry.get("pass") != score["pass"]):
                raise ValueError("S15 saved score does not recompute")
            judgment = row["judgment"]
            normalized[(key[0], key[1], spec["id"])] = {
                "case_id": key[0], "variant": key[1], "judge_id": spec["id"],
                "update_statuses": [item["status"] for item in judgment["criterion_assessments"]
                                    if item["stage_id"] == "update"],
                "initial_statuses": [item["status"] for item in judgment["criterion_assessments"]
                                     if item["stage_id"] == "initial"],
                "requirements": judgment["stage_scores"][1]["requirements"],
                "safety": judgment["stage_scores"][1]["safety"],
                "revision": judgment["revision_score"], "gated_score": score["gated_score"],
                "pass": score["pass"], "critical_error_ids": [item["error_id"]
                                                            for item in judgment["critical_errors"]],
                "human_review_requested": judgment["requires_human_review"],
                "judgment_file": filename,
            }
    if seen != set(expected_packets) or used_files != {
        _filename(spec["id"], case_id, variant)
        for case_id, variant in expected_packets for spec in plan["judges"]
    } or {path.name for path in directory.glob("*.judgment.json")} != used_files:
        raise ValueError("S15 saved file set is incomplete or unexpected")
    pairs = []
    for case_id in sorted({key[0] for key in expected_packets}):
        for judge_id in sorted(expected_judges):
            baseline = normalized[(case_id, "baseline", judge_id)]
            omission = normalized[(case_id, "omission", judge_id)]
            pairs.append({
                "case_id": case_id, "judge_id": judge_id,
                "baseline_update_statuses": baseline["update_statuses"],
                "omission_update_statuses": omission["update_statuses"],
                "author_hypothesis_match":
                    baseline["update_statuses"] == hypotheses["baseline_update_statuses"]
                    and omission["update_statuses"] == hypotheses["omission_update_statuses"],
                "initial_statuses_unchanged": baseline["initial_statuses"] == omission["initial_statuses"],
                "delta_from_baseline": {name: round(omission[name] - baseline[name], 2)
                                        for name in ("requirements", "safety", "revision", "gated_score")},
                "baseline_gated_score": baseline["gated_score"],
                "omission_gated_score": omission["gated_score"],
                "baseline_pass": baseline["pass"], "omission_pass": omission["pass"],
                "omission_critical_error_ids": omission["critical_error_ids"],
                "omission_human_review_requested": omission["human_review_requested"],
            })
    return {"status": audit_status, "candidate_calls": 0, "completed_judge_calls": 8,
            "probe_sha256": plan["probe_sha256"], "pairs": pairs,
            "limits": "Author hypotheses and AI scores are not clinical truth; EN/ZH semantic equivalence unreviewed. No scores were changed."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S15 capped fresh-mechanism judge-only run and audit")
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
            if args.output_dir is None or not args.output_dir.resolve().is_relative_to((args.root / "work").resolve()):
                raise ValueError("S15 live output must be under ignored work/")
            result = run_live(inputs, output_dir=args.output_dir, env_file=args.env_file,
                              max_api_calls=args.max_api_calls, timeout=args.timeout)
        else:
            if args.output_dir is None:
                raise ValueError("--output-dir is required for audit")
            result = audit_saved(inputs, args.output_dir)
            if args.report_output:
                _write_json_new(args.report_output, result)
    except (ProviderRequestError, ValueError, FileExistsError, OSError, KeyError, TypeError) as exc:
        print(f"S15 {args.command} failed: {type(exc).__name__}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
