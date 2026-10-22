"""Frozen v3-instruction judge-only panel; development diagnostic, never clinical calibration."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .local_settings import read_setting
from .model_matrix import KEYS, JUDGES, run_anchored_contrast
from .multifamily_repeatability_s19 import _cell
from .multiturn import merge_multiturn_datasets, variant_hash, variant_id
from .multiturn_diagnostics import contrast_packet
from .multiturn_judging import score_judgment
from .provenance import sha256_json, sha256_text


POLICY_PATH = "config/judge_evidence_panel_s21_v1.json"
VARIANTS = ("safe", "partial", "unsafe")
FAMILIES = ("HC-MT-TRIAGE-020", "HC-MT-MEDSAFE-015")
LANGUAGES = ("en", "zh-Hans")


def _inputs(root: Path) -> dict[str, Any]:
    policy = load_json(root / POLICY_PATH)
    if (policy.get("version") != "s21-v1-preregistered-judge-instruction-panel"
        or policy.get("status") != "prospective_development_only_not_clinical_or_scoring_contract"
        or policy.get("family_ids") != list(FAMILIES)
        or policy.get("languages") != list(LANGUAGES)
        or policy.get("answer_types") != list(VARIANTS)
        or policy.get("first_judge_calls") != 24 or policy.get("partial_repeat_calls") != 8
        or policy.get("candidate_calls") != 0 or policy.get("automatic_retries") != 0):
        raise ValueError("Unknown S21 prospective protocol")
    for path, digest in policy["file_sha256"].items():
        if sha256_text((root / path).read_text(encoding="utf-8")) != digest:
            raise ValueError(f"S21 frozen source changed: {path}")
    g = load_json(root / "data/multiturn/batch_g_cases.json")
    i = load_json(root / "data/multiturn/batch_i_cases.json")
    dataset = merge_multiturn_datasets([g, i])
    g_anchors = load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json")
    i_anchors = load_json(root / "config/multiturn_criterion_anchors_batch_i_v1.json")
    anchors = deepcopy(g_anchors)
    anchors["families"] = [item for item in g_anchors["families"] if item["family_id"] == FAMILIES[0]] + i_anchors["families"]
    validate_anchor_set(anchors, dataset)
    roster = load_json(root / "config/s21_judge_panel_roster.json")
    if (roster.get("status") != "development_only_judge_only_no_candidate_models"
        or len(roster.get("judges", [])) != 2
        or {item["provider"] for item in roster["judges"]} != {"gemini", "grok"}):
        raise ValueError("S21 judge roster changed")
    sources = [load_json(root / "data/multiturn/batch_g_contrasts_v1.json"),
               load_json(root / "data/multiturn/s21_medsafe015_contrasts_v1.json")]
    probes = {}
    families = {item["family_id"]: item for item in dataset["families"]}
    for source in sources:
        if (source.get("schema_version") != "0.1.0"
            or source.get("status") != "synthetic_unreviewed_development_probes_not_clinical_truth"):
            raise ValueError("S21 contrast source is malformed")
        for row in source["probes"]:
            if row["family_id"] not in FAMILIES:
                continue
            key = row["family_id"], row["language"]
            if (key in probes or row["language"] not in LANGUAGES
                or row["case_content_hash"] != variant_hash(families[row["family_id"]], row["language"])):
                raise ValueError("S21 contrast duplicate or stale case revision")
            if row["expected_unsafe_error_id"] not in {
                item["id"] for item in families[row["family_id"]]["variants"][row["language"]]["turns"][1]["critical_errors"]
            }:
                raise ValueError("S21 unsafe control is not configured")
            for name in ("initial_response", "safe_update_response", "partial_update_response", "unsafe_update_response"):
                if not isinstance(row.get(name), str) or not row[name].strip():
                    raise ValueError("S21 contrast lacks an authored answer")
            probes[key] = {"schema_version": "0.1.0", "status": "synthetic_unreviewed_development_probe", **row}
    if set(probes) != {(family, language) for family in FAMILIES for language in LANGUAGES}:
        raise ValueError("S21 panel must contain two EN/ZH families")
    result = {
        "policy": policy, "dataset": dataset, "anchors": anchors, "roster": roster,
        "rubric": load_json(root / "config/multiturn_rubric.json"),
        "instruction": (root / "config/multiturn_judge_prompt_v3_evidence.txt").read_text(encoding="utf-8").strip(),
        "families": families, "probes": probes,
    }
    actual = protocol_hashes(result)
    if actual != policy["protocol_hashes"]:
        raise ValueError("S21 assembled protocol differs from preregistration")
    return result


def protocol_hashes(inputs: dict[str, Any]) -> dict[str, str]:
    return {"dataset_sha256": sha256_json(inputs["dataset"]),
            "anchors_sha256": sha256_json(inputs["anchors"]),
            "roster_sha256": sha256_json(inputs["roster"]),
            "rubric_sha256": sha256_json(inputs["rubric"]),
            "instruction_sha256": sha256_text(inputs["instruction"]),
            "probes_sha256": sha256_json([inputs["probes"][key] for key in sorted(inputs["probes"])])}


def plan(root: Path) -> dict[str, Any]:
    inputs = _inputs(root)
    packets = []
    for key in sorted(inputs["probes"]):
        family, probe = inputs["families"][key[0]], inputs["probes"][key]
        for variant in VARIANTS:
            packet = attach_anchors(contrast_packet(family, probe, variant), inputs["anchors"])
            packets.append({"case_id": variant_id(family, key[1]), "answer_type": variant,
                            "packet_sha256": sha256_json(packet)})
    if len(packets) != 12 or packets != inputs["policy"]["packet_hashes"]:
        raise ValueError("S21 exact answer packets differ from preregistration")
    return {"status": "s21_preflight_no_api_calls", "policy_sha256": sha256_json(inputs["policy"]),
            "protocol_hashes": protocol_hashes(inputs), "packet_hashes": packets,
            "first_judge_calls": 24, "partial_repeat_calls": 8, "candidate_calls": 0,
            "limits": inputs["policy"]["limits"]}


def _target(root: Path, path: Path) -> Path:
    target = path.resolve()
    if not target.is_relative_to((root / "work").resolve()) or target.exists():
        raise ValueError("S21 output must be a fresh ignored work/ directory")
    return target


def _write(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _stem(family_id: str, language: str) -> str:
    return f"{family_id.lower()}_{'en' if language == 'en' else 'zh'}"


def run_first(root: Path, target: Path, *, env_file: Path, max_api_calls: int,
              timeout: float) -> dict[str, Any]:
    if max_api_calls != 24 or timeout <= 0:
        raise ValueError("S21 first run requires --max-api-calls 24 and positive timeout")
    target = _target(root, target)
    frozen = plan(root)
    inputs = _inputs(root)
    target.mkdir(parents=True)
    _write(target / "plan.json", frozen)
    for key in sorted(inputs["probes"]):
        run_anchored_contrast(inputs["probes"][key], inputs["roster"], inputs["dataset"],
                              inputs["rubric"], inputs["anchors"],
                              output_dir=target / _stem(*key), env_file=env_file,
                              judge_instruction=inputs["instruction"], max_api_calls=6,
                              timeout=timeout)
    complete = {"status": "s21_first_24_judge_calls_complete", "policy_sha256": frozen["policy_sha256"],
                "protocol_hashes": frozen["protocol_hashes"], "candidate_calls": 0, "judge_calls": 24}
    _write(target / "complete.json", complete)
    return complete


def _first_cells(root: Path, target: Path, inputs: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    frozen = plan(root)
    complete = load_json(target / "complete.json")
    if (complete.get("status") != "s21_first_24_judge_calls_complete"
        or complete.get("policy_sha256") != frozen["policy_sha256"]
        or complete.get("protocol_hashes") != frozen["protocol_hashes"]
        or complete.get("candidate_calls") != 0 or complete.get("judge_calls") != 24
        or load_json(target / "plan.json") != frozen):
        raise ValueError("S21 first run is incomplete or changed")
    cells = {}
    for key in sorted(inputs["probes"]):
        family, probe = inputs["families"][key[0]], inputs["probes"][key]
        directory = target / _stem(*key)
        report = load_json(directory / "report.json")
        if (report.get("roster_sha256") != frozen["protocol_hashes"]["roster_sha256"]
            or report.get("dataset_sha256") != frozen["protocol_hashes"]["dataset_sha256"]
            or report.get("criterion_anchors_sha256") != frozen["protocol_hashes"]["anchors_sha256"]
            or report.get("judge_instruction_sha256") != frozen["protocol_hashes"]["instruction_sha256"]
            or report.get("rubric_sha256") != frozen["protocol_hashes"]["rubric_sha256"]
            or report.get("candidate_calls") != 0 or report.get("judge_calls") != 6):
            raise ValueError("S21 first-run report has a protocol mismatch")
        for variant in VARIANTS:
            for provider in ("gemini", "grok"):
                record = _cell(directory, report, probe, family, inputs, provider, variant)
                raw = load_json(directory / f"{provider}-judge__{variant}.judgment.json")
                cells[(report["case_id"], variant, provider)] = {**record, "judgment": raw["judgment"]}
    if len(cells) != 24:
        raise ValueError("S21 first run lacks cells")
    if any(len({item["returned_model"] for key, item in cells.items() if key[2] == provider}) != 1
           for provider in ("gemini", "grok")):
        raise ValueError("S21 first run returned mixed model identities")
    return cells


def audit_first(root: Path, target: Path) -> dict[str, Any]:
    inputs = _inputs(root)
    cells = _first_cells(root, target, inputs)
    unsafe_detected = 0
    ordered = 0
    for key, probe in inputs["probes"].items():
        case_id = variant_id(inputs["families"][key[0]], key[1])
        for provider in ("gemini", "grok"):
            safe, partial, unsafe = (cells[(case_id, variant, provider)] for variant in VARIANTS)
            unsafe_detected += probe["expected_unsafe_error_id"] in {item[0] for item in unsafe["critical_errors"]}
            ordered += safe["score"] > partial["score"] > unsafe["score"]
    return {"status": "s21_first_saved_results_verified_not_calibration", "cells": len(cells),
            "format_flags": dict(Counter(flag for item in cells.values() for flag in evidence_format_flags(item["judgment"]))),
            "partial_scores": {f"{case_id}/{provider}": item["score"]
                               for (case_id, variant, provider), item in sorted(cells.items()) if variant == "partial"},
            "unsafe_named_error_detected": unsafe_detected, "unsafe_cells": 8,
            "safe_partial_unsafe_score_ordering": ordered, "ordered_panels": 8,
            "candidate_calls": 0, "judge_calls": 24,
            "limits": inputs["policy"]["limits"]}


def evidence_format_flags(judgment: dict[str, Any]) -> list[str]:
    flags = []
    for stage in judgment["stage_scores"]:
        rationale = stage["rationale"]
        if "REQ:" not in rationale or "SAFETY:" not in rationale:
            flags.append(f"{stage['stage_id']}_missing_evidence_markers")
        elif stage["safety"] < 4 and "none established" in rationale.split("SAFETY:", 1)[1].casefold():
            flags.append(f"{stage['stage_id']}_safety_deduction_without_stated_basis")
    if "REVISION:" not in judgment["overall_rationale"]:
        flags.append("missing_revision_marker")
    return flags


def run_repeat(root: Path, first: Path, target: Path, *, env_file: Path,
               max_api_calls: int, timeout: float) -> dict[str, Any]:
    if max_api_calls != 8 or timeout <= 0:
        raise ValueError("S21 partial repeat requires --max-api-calls 8 and positive timeout")
    target = _target(root, target)
    inputs = _inputs(root)
    first_cells = _first_cells(root, first, inputs)
    frozen = plan(root)
    keys = {provider: read_setting(env_file, KEYS[provider], secret=True)
            for provider in ("gemini", "grok")}
    target.mkdir(parents=True)
    _write(target / "plan.json", {**frozen, "first_complete_sha256": sha256_json(load_json(first / "complete.json")),
                                  "repeat_answer_type": "partial", "repeat_judge_calls": 8})
    for key in sorted(inputs["probes"]):
        family, probe = inputs["families"][key[0]], inputs["probes"][key]
        packet = attach_anchors(contrast_packet(family, probe, "partial"), inputs["anchors"])
        case_id = packet["case_id"]
        for spec in inputs["roster"]["judges"]:
            provider = spec["provider"]
            judge = JUDGES[provider](model=spec["model"], api_key=keys[provider],
                                     instruction=inputs["instruction"], timeout=timeout, retries=0)
            judge.rejected_output_path = target / f"{_stem(*key)}__{provider}.rejected.json"
            judgment = judge.evaluate(packet)
            score = score_judgment(judgment, packet, inputs["rubric"])
            if judge.model_version != first_cells[(case_id, "partial", provider)]["returned_model"]:
                raise ValueError("S21 repeated judge returned a different model identity")
            _write(target / f"{_stem(*key)}__{provider}.judgment.json", {
                "case_id": case_id, "answer_type": "partial", "provider": provider,
                "model_requested": spec["model"], "model_returned": judge.model_version,
                "packet_sha256": sha256_json(packet), "policy_sha256": frozen["policy_sha256"],
                "judgment": judgment, "score": score})
    complete = {"status": "s21_partial_repeat_8_judge_calls_complete", "policy_sha256": frozen["policy_sha256"],
                "first_complete_sha256": sha256_json(load_json(first / "complete.json")),
                "candidate_calls": 0, "judge_calls": 8}
    _write(target / "complete.json", complete)
    return complete


def audit(root: Path, first: Path, repeat: Path) -> dict[str, Any]:
    inputs = _inputs(root)
    left = _first_cells(root, first, inputs)
    frozen = plan(root)
    complete = load_json(repeat / "complete.json")
    if (complete.get("status") != "s21_partial_repeat_8_judge_calls_complete"
        or complete.get("policy_sha256") != frozen["policy_sha256"]
        or complete.get("first_complete_sha256") != sha256_json(load_json(first / "complete.json"))
        or complete.get("candidate_calls") != 0 or complete.get("judge_calls") != 8
        or load_json(repeat / "plan.json") != {**frozen, "first_complete_sha256": complete["first_complete_sha256"],
                                                 "repeat_answer_type": "partial", "repeat_judge_calls": 8}):
        raise ValueError("S21 repeated panel is incomplete or changed")
    rows = []
    for key in sorted(inputs["probes"]):
        family, probe = inputs["families"][key[0]], inputs["probes"][key]
        packet = attach_anchors(contrast_packet(family, probe, "partial"), inputs["anchors"])
        for spec in inputs["roster"]["judges"]:
            provider = spec["provider"]
            raw = load_json(repeat / f"{_stem(*key)}__{provider}.judgment.json")
            score = score_judgment(raw["judgment"], packet, inputs["rubric"])
            first_cell = left[(packet["case_id"], "partial", provider)]
            if (raw.get("case_id") != packet["case_id"] or raw.get("answer_type") != "partial"
                or raw.get("provider") != provider or raw.get("model_requested") != spec["model"]
                or raw.get("model_returned") != first_cell["returned_model"]
                or raw.get("packet_sha256") != sha256_json(packet)
                or raw.get("policy_sha256") != frozen["policy_sha256"]
                or raw.get("score") != score):
                raise ValueError("S21 repeated judgment lacks exact packet or score binding")
            second = raw["judgment"]
            statuses = [item["status"] for item in second["criterion_assessments"]]
            errors = [(item["error_id"], item["severity"]) for item in second["critical_errors"]]
            rows.append({"case_id": packet["case_id"], "judge": provider,
                         "score_first_repeat": [first_cell["score"], score["gated_score"]],
                         "score_same": first_cell["score"] == score["gated_score"],
                         "statuses_same": first_cell["criterion_statuses"] == statuses,
                         "critical_errors_same": first_cell["critical_errors"] == errors,
                         "dimensions_same": [first_cell["requirements"], first_cell["safety"], first_cell["revision"],
                                              first_cell["judgment"]["stage_scores"][0]["requirements"],
                                              first_cell["judgment"]["stage_scores"][0]["safety"]]
                             == [second["stage_scores"][1]["requirements"], second["stage_scores"][1]["safety"],
                                 second["revision_score"], second["stage_scores"][0]["requirements"],
                                 second["stage_scores"][0]["safety"]],
                         "pass_same": first_cell["pass"] == score["pass"],
                         "format_flags_first": evidence_format_flags(first_cell["judgment"]),
                         "format_flags_repeat": evidence_format_flags(second)})
    return {"status": "s21_exact_packet_v3_instruction_repeat_not_clinical_calibration",
            "first_cells": 24, "repeat_partial_cells": len(rows),
            "exact_score_repeats": sum(row["score_same"] for row in rows),
            "status_repeats": sum(row["statuses_same"] for row in rows),
            "critical_error_repeats": sum(row["critical_errors_same"] for row in rows),
            "pass_repeats": sum(row["pass_same"] for row in rows),
            "format_flags_all_first": dict(Counter(flag for item in left.values() for flag in evidence_format_flags(item["judgment"]))),
            "format_flags_partial_repeat": dict(Counter(flag for row in rows for flag in row["format_flags_repeat"])),
            "comparisons": rows, "candidate_calls": 0, "judge_calls": 32,
            "limits": inputs["policy"]["limits"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S21 frozen v3-instruction judge-only panel")
    parser.add_argument("command", choices=("plan", "run-first", "audit-first", "run-repeat", "audit"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--first-dir", type=Path)
    parser.add_argument("--repeat-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = plan(args.root)
    elif args.command == "run-first":
        if args.first_dir is None:
            parser.error("run-first requires --first-dir")
        result = run_first(args.root, args.first_dir, env_file=args.env_file,
                           max_api_calls=args.max_api_calls, timeout=args.timeout)
    elif args.command == "audit-first":
        if args.first_dir is None:
            parser.error("audit-first requires --first-dir")
        result = audit_first(args.root, args.first_dir)
    elif args.command == "run-repeat":
        if args.first_dir is None or args.repeat_dir is None:
            parser.error("run-repeat requires --first-dir and --repeat-dir")
        result = run_repeat(args.root, args.first_dir, args.repeat_dir, env_file=args.env_file,
                            max_api_calls=args.max_api_calls, timeout=args.timeout)
    else:
        if args.first_dir is None or args.repeat_dir is None:
            parser.error("audit requires --first-dir and --repeat-dir")
        result = audit(args.root, args.first_dir, args.repeat_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
