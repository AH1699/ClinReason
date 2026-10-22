"""S17 read-only dimension-evidence flags and clean-probe preregistration."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .config import load_json
from .provenance import sha256_json, sha256_text
from .scoring_dimension_fresh_run import audit_saved as audit_s16, load_inputs as load_s16, prepare_run
from .scoring_dimension_fresh_run import run_live as run_judges
from .scoring_probe_run import audit_saved as audit_s14, load_inputs as load_s14


POLICY_PATH = "config/scoring_dimension_evidence_s17_v1.json"
PARENT_PATH = "data/multiturn/scoring_dimension_probe_reason015_s15_v1.json"
S17_RUN_STATUS = "s17_punctuation_clean_judge_only_not_clinical_validation"
S17_AUDIT_STATUS = "s17_saved_clean_probe_description_not_calibration"


def preregister_plan(root: Path) -> dict[str, Any]:
    policy = load_json(root / POLICY_PATH)
    parent = load_json(root / PARENT_PATH)
    probe = load_json(root / policy["next_probe_path"])
    old_plan, old_packets = prepare_run(load_s16(root))
    if (policy.get("version") != "s17-v1-review-only"
        or policy.get("status") != "offline_evidence_questions_not_a_scoring_rule"
        or policy.get("planned_judge_calls_max") != 8
        or policy.get("planned_candidate_calls") != 0
        or probe.get("status") != "preregistered_author_probe_unjudged_not_clinical_truth"
        or probe.get("parent_s15_probe_sha256") != sha256_json(parent)
        or probe.get("family_id") != parent["family_id"]
        or probe.get("target_requirement_index") != parent["target_requirement_index"]
        or probe.get("planned_judges") != [item["id"] for item in old_plan["judges"]]
        or probe.get("planned_judge_calls_max") != 8
        or probe.get("planned_candidate_calls") != 0):
        raise ValueError("S17 scoring or clean-probe protocol changed")
    old_languages = {item["language"]: item for item in parent["languages"]}
    new_languages = {item["language"]: item for item in probe["languages"]}
    if set(new_languages) != {"en", "zh-Hans"} or new_languages["en"] != old_languages["en"]:
        raise ValueError("S17 English answer or language set changed")
    expected_zh = copy.deepcopy(old_languages["zh-Hans"])
    old_part = expected_zh["base_update_segments"][1]
    if not old_part.endswith("；"):
        raise ValueError("S15 punctuation premise changed")
    expected_zh["base_update_segments"][1] = old_part[:-1] + "。"
    if new_languages["zh-Hans"] != expected_zh:
        raise ValueError("S17 Chinese edit exceeds trailing punctuation")
    packets = []
    for case_id, variant, old_packet in old_packets:
        packet = copy.deepcopy(old_packet)
        language = packet["language"]
        item = new_languages[language]
        segments = item["base_update_segments"]
        answer = item["separator"].join(segments if variant == "baseline" else segments[:2])
        packet["transcript"][-1]["content"] = answer
        if (packet["case_content_hash"] != item["case_content_hash"]
            or packet["transcript"][1]["content"] != item["initial_response"]):
            raise ValueError("S17 case or initial answer changed")
        packets.append({"case_id": case_id, "variant": variant,
                        "answer_sha256": sha256_text(answer), "packet_sha256": sha256_json(packet)})
    if len(packets) != 4:
        raise ValueError("S17 requires four fixed answer packets")
    return {
        "status": "preregistered_no_api_calls_not_clinical_truth",
        "policy_sha256": sha256_json(policy), "probe_sha256": sha256_json(probe),
        "parent_probe_sha256": sha256_json(parent),
        **{key: old_plan[key] for key in ("dataset_sha256", "criterion_anchors_sha256",
                                            "rubric_sha256", "judge_instruction_sha256",
                                            "roster_sha256", "criterion_validator_version")},
        "packets": packets, "judges": old_plan["judges"],
        "judge_calls_max": 8, "candidate_calls": 0,
        "limits": policy["limits"],
    }


def prepare_live_run(root: Path) -> tuple[dict[str, Any], list[tuple[str, str, dict[str, Any]]]]:
    prereg = preregister_plan(root)
    old_plan, old_packets = prepare_run(load_s16(root))
    policy = load_json(root / POLICY_PATH)
    probe = load_json(root / policy["next_probe_path"])
    by_language = {item["language"]: item for item in probe["languages"]}
    packets = []
    for case_id, variant, old_packet in old_packets:
        packet = copy.deepcopy(old_packet)
        item = by_language[packet["language"]]
        segments = item["base_update_segments"]
        packet["transcript"][-1]["content"] = item["separator"].join(
            segments if variant == "baseline" else segments[:2]
        )
        packets.append((case_id, variant, packet))
    actual = [{"case_id": case_id, "variant": variant,
               "answer_sha256": sha256_text(packet["transcript"][-1]["content"]),
               "packet_sha256": sha256_json(packet)} for case_id, variant, packet in packets]
    if actual != prereg["packets"]:
        raise ValueError("S17 live packets differ from the frozen preregistration")
    plan = {**old_plan, "policy_sha256": prereg["policy_sha256"],
            "probe_sha256": prereg["probe_sha256"],
            "parent_probe_sha256": prereg["parent_probe_sha256"],
            "packet_hashes": [{"case_id": case_id, "variant": variant,
                               "case_content_hash": packet["case_content_hash"],
                               "packet_sha256": sha256_json(packet)}
                              for case_id, variant, packet in packets]}
    return plan, packets


def audit_clean_live(root: Path, directory: Path) -> dict[str, Any]:
    prepared = prepare_live_run(root)
    policy = load_json(root / POLICY_PATH)
    probe = load_json(root / policy["next_probe_path"])
    report = load_json(directory / "report.json")
    if report.get("parent_probe_sha256") != prepared[0]["parent_probe_sha256"]:
        raise ValueError("S17 report lost its S15 parent-probe binding")
    return audit_s16(load_s16(root), directory, prepared=prepared,
                     hypotheses=probe["author_hypotheses_not_gold"],
                     run_status=S17_RUN_STATUS, audit_status=S17_AUDIT_STATUS)


def describe_pairs(s14: dict[str, Any], s16: dict[str, Any], pass_threshold: float) -> dict[str, Any]:
    if (s14.get("completed_judge_calls") != 16 or s16.get("completed_judge_calls") != 8
        or s14.get("candidate_calls") != 0 or s16.get("candidate_calls") != 0):
        raise ValueError("Incomplete saved S14/S16 inputs")
    rows = []
    s14_scores = {item["case_id"]: item["judge_scores"] for item in s14["judge_pairs"]
                  if item["variant"] == "safety_net_omission"}
    for item in s14["contrasts"]:
        if item["variant"] == "safety_net_omission":
            rows.append(("s14_triage_020_safety_net_omission", item["case_id"], item["judge_id"],
                         item["observed_update_statuses"], item["delta_from_baseline"],
                         s14_scores[item["case_id"]][item["judge_id"]] >= pass_threshold))
    for item in s16["pairs"]:
        rows.append(("s16_reason_015_safety_net_omission", item["case_id"], item["judge_id"],
                     item["omission_update_statuses"], item["delta_from_baseline"], item["omission_pass"]))
    if len(rows) != 8 or len({row[:3] for row in rows}) != 8:
        raise ValueError("S17 requires eight distinct saved omission comparisons")
    result, counts = [], Counter()
    for cohort, case_id, judge_id, statuses, delta, passed in rows:
        if len(statuses) != 3 or statuses[2] == "met":
            raise ValueError("S17 targeted omission was not detected")
        flags = []
        if delta["requirements"] >= 0:
            flags.append("requirement_numeric_coherence_review")
        if delta["safety"] < 0:
            flags.append("independent_direct_safety_evidence_review")
        if delta["revision"] < 0:
            flags.append("independent_revision_evidence_review")
        if delta["safety"] < 0 and delta["revision"] < 0:
            flags.append("multi_dimension_overlap_review")
        if passed:
            flags.append("provisional_pass_with_omission_review")
        counts.update(flags)
        result.append({"cohort": cohort, "case_id": case_id, "judge_id": judge_id,
                       "target_status": statuses[2], "dimension_delta": {
                           key: delta[key] for key in ("requirements", "safety", "revision", "gated_score")},
                       "provisional_pass": passed, "review_flags": flags})
    return {"status": "offline_evidence_flags_not_rescoring_or_clinical_adjudication",
            "saved_omission_pairs": len(rows), "flag_counts": dict(sorted(counts.items())),
            "pairs": result, "candidate_calls": 0, "judge_calls": 0,
            "limits": "A flag asks for independent justification; it neither proves double counting nor changes any historical score or pass flag."}


def audit(root: Path, work_root: Path) -> dict[str, Any]:
    prereg = preregister_plan(root)
    s14 = audit_s14(load_s14(root), work_root / "s13_scoring_probe_2026-10-21")
    s16 = audit_s16(load_s16(root), work_root / "s15_reason015_probe_network_2026-10-21")
    threshold = load_json(root / "config/multiturn_rubric.json")["pass_threshold"]
    return {"preregistration": prereg,
            "saved_diagnostic": describe_pairs(s14, s16, threshold)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S17 clean probe and read-only saved-dimension flags")
    parser.add_argument("command", choices=("plan", "audit", "run", "audit-live"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        if args.output_dir is None:
            parser.error("run requires --output-dir")
        result = run_judges(load_s16(args.root), output_dir=args.output_dir,
                            env_file=args.env_file, max_api_calls=args.max_api_calls,
                            timeout=args.timeout, prepared=prepare_live_run(args.root),
                            run_status=S17_RUN_STATUS)
    elif args.command == "audit-live":
        if args.output_dir is None:
            parser.error("audit-live requires --output-dir")
        result = audit_clean_live(args.root, args.output_dir)
    elif args.command == "plan":
        result = preregister_plan(args.root)
    else:
        result = audit(args.root, args.work_root or args.root / "work")
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError("Refusing to overwrite S17 output")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
