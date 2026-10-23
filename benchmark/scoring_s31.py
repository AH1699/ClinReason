"""Frozen full-score S30-anchor integration; live calls require separate consent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import boundary_s30 as boundary
from . import scoring_s26 as base
from . import scoring_s28 as previous
from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .local_settings import read_setting
from .provenance import sha256_json, sha256_text
from .providers.observed_http import DiagnosticRequestError, post_json_observed

POLICY = "config/scoring_s31_v1.json"
MANIFEST = "config/scoring_s31_frozen_v1.json"
PROMPT = base.PROMPT
SOURCES = sorted(set(boundary.SOURCES + [boundary.MANIFEST, base.MANIFEST,
    previous.MANIFEST, POLICY, "benchmark/scoring_s31.py", "tests/test_scoring_s31.py",
    "data/audit/s30_boundary_summary.json"]))


def inputs(root):
    boundary.check_manifest(root)
    previous.check_manifest(root)
    old_policy, old_packets, controls = previous.inputs(root)
    policy = load_json(root / POLICY)
    permitted = {"version", "timeout_seconds", "anchor_path", "comparison", "advance_gate"}
    for key, value in old_policy.items():
        if key not in permitted and policy.get(key) != value:
            raise ValueError("S31 must preserve S28 scope and scoring arithmetic")
    if (policy["version"] != "s31-v1-full-score-s30-anchor-integration"
            or policy["timeout_seconds"] != 240
            or policy["anchor_path"] != boundary.draft.ANCHORS
            or policy["sampling"] != "provider_defaults_unpinned"
            or policy["order"] != "preserve_s28_packet_key_order_first_then_partial_repeats"):
        raise ValueError("Unexpected S31 protocol")
    predecessor = load_json(root / "data/audit/s30_boundary_summary.json")
    if (predecessor["ready_to_design_full_scoring_repeat"] is not True
            or predecessor["valid_judgments"] != 24
            or predecessor["known_first_criterion_matches"] != 32
            or predecessor["repeat_criterion_matches"] != 8
            or predecessor["frozen_manifest_sha256"] != sha256_json(boundary.check_manifest(root))):
        raise ValueError("S31 requires the recorded S30 design-advance result")
    anchors = load_json(root / policy["anchor_path"])
    validate_anchor_set(anchors, load_json(root / "data/multiturn/batch_g_cases.json"))
    packets = {key: attach_anchors(packet, anchors) for key, packet in old_packets.items()}
    return policy, packets, controls


def schedule(policy, packets):
    return previous.schedule(policy, packets)


def manifest(root):
    policy, packets, _ = inputs(root)
    return {"version": "s31-frozen-v1",
            "files": {p: sha256_text((root / p).read_text(encoding="utf-8")) for p in SOURCES},
            "packets": {k: sha256_json(p) for k, p in sorted(packets.items())},
            "schedule_sha256": sha256_json(schedule(policy, packets)),
            "output_schema_sha256": {k: sha256_json(base.schema(p)) for k, p in sorted(packets.items())}}


def check_manifest(root):
    actual = manifest(root)
    if actual != load_json(root / MANIFEST):
        raise ValueError("S31 frozen input changed; create a new experiment version")
    return actual


def request(provider, model, key, packet, instruction, timeout):
    # Preserve S28's complete-judgment payload/schema and prompt. Only transport
    # observation and the prospectively configured timeout change here.
    return base.request_judgment(provider, model, key, packet, instruction, timeout,
                                 transport=post_json_observed)


def attempt(phase, key, spec, packet):
    return {"phase": phase, "packet_key": key, "provider": spec["provider"],
            "model_requested": spec["model"], "packet_sha256": sha256_json(packet),
            "timeout_seconds": 240, "automatic_retries": 0}


def run(root, output, env_file, max_calls, approved_protocol_sha256=None):
    frozen = check_manifest(root)
    if (type(max_calls) is not int or max_calls != 32
            or approved_protocol_sha256 != sha256_json(frozen)
            or output.exists() or not output.resolve().is_relative_to((root / "work").resolve())):
        raise ValueError("S31 requires fresh work/ output, max-calls 32 and the approved protocol SHA256")
    policy, packets, _ = inputs(root)
    keys = {p: read_setting(env_file, name, secret=True)
            for p, name in (("gemini", "GEMINI_API_KEY"), ("grok", "GROK_API_KEY"))}
    output.mkdir(parents=True, mode=0o700)
    base.write_new(output / "manifest.json", frozen)
    # A CLI acknowledgment binds scope; actual owner consent is external to it.
    base.write_new(output / "external_call_acknowledgment.json",
                   {"protocol_sha256": approved_protocol_sha256, "maximum_calls": 32})
    instruction = (root / PROMPT).read_text(encoding="utf-8")
    for i, (phase, key, spec) in enumerate(schedule(policy, packets), 1):
        record = attempt(phase, key, spec, packets[key])
        base.write_new(output / f"{i:02d}.attempt.json", record)
        try:
            raw, latency = request(spec["provider"], spec["model"], keys[spec["provider"]],
                                   packets[key], instruction, policy["timeout_seconds"])
            base.write_new(output / f"{i:02d}.response.json", raw)
            judgment = base.parse_response(raw, spec["provider"])
            if raw["model"] != spec["model"] or type(latency) is not int or latency < 0:
                raise ValueError("Unexpected S31 model or latency")
            result = base.score(judgment, packets[key], policy)
            base.write_new(output / f"{i:02d}.judgment.json", {
                **record, "model_returned": raw["model"], "judgment": judgment,
                "score": result, "latency_ms": latency})
            print(json.dumps({"completed": i, "maximum": 32, "phase": phase,
                              "provider": spec["provider"], "latency_ms": latency}), flush=True)
        except DiagnosticRequestError as exc:
            base.write_new(output / "stopped.json", {"attempted": i, "saved": i - 1,
                "kind": "transport_failure", "diagnostic": exc.diagnostic})
            return audit(root, output)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            base.write_new(output / "stopped.json", {"attempted": i, "saved": i - 1,
                "kind": "response_validation_failure", "error_type": type(exc).__name__,
                "delivery": "response_saved_validation_failed"})
            return audit(root, output)
    base.write_new(output / "complete.json", {"judge_calls": 32, "candidate_calls": 0})
    return audit(root, output)


def vector(row):
    return {"criteria": [[r["stage_id"], r["requirement_index"], r["status"]]
                         for r in row["judgment"]["criterion_assessments"]],
            "critical_errors": sorted([[r["stage_id"], r["error_id"], r["severity"]]
                                       for r in row["judgment"]["critical_errors"]])}


def audit(root, output):
    frozen = check_manifest(root)
    if (load_json(output / "manifest.json") != frozen
            or load_json(output / "external_call_acknowledgment.json") != {
                "protocol_sha256": sha256_json(frozen), "maximum_calls": 32}):
        raise ValueError("S31 saved manifest or acknowledgment mismatch")
    policy, packets, controls = inputs(root)
    plan = schedule(policy, packets)
    attempts = sorted(output.glob("*.attempt.json"))
    paths = sorted(output.glob("*.judgment.json"))
    responses = sorted(output.glob("*.response.json"))
    if not 0 <= len(paths) <= len(responses) <= len(attempts) <= 32 or len(attempts) > len(paths) + 1:
        raise ValueError("Invalid S31 artifact counts")
    for collection, suffix in ((attempts, "attempt"), (paths, "judgment"), (responses, "response")):
        if [p.name for p in collection] != [f"{i:02d}.{suffix}.json" for i in range(1, len(collection) + 1)]:
            raise ValueError("S31 artifacts must be a contiguous prefix")
    for i, path in enumerate(attempts):
        phase, key, spec = plan[i]
        if load_json(path) != attempt(phase, key, spec, packets[key]):
            raise ValueError("S31 attempt differs from frozen schedule")
    rows, cells = {}, []
    for i, path in enumerate(paths):
        phase, key, spec = plan[i]
        raw = load_json(output / f"{i + 1:02d}.response.json")
        row = load_json(path)
        record = attempt(phase, key, spec, packets[key])
        if (not isinstance(row, dict)
                or set(row) != set(record) | {"model_returned", "judgment", "score", "latency_ms"}
                or any(row[k] != v for k, v in record.items())
                or not isinstance(raw, dict) or raw.get("model") != spec["model"]
                or row["model_returned"] != raw["model"]
                or row["judgment"] != base.parse_response(raw, spec["provider"])
                or row["score"] != base.score(row["judgment"], packets[key], policy)
                or type(row["latency_ms"]) is not int or row["latency_ms"] < 0):
            raise ValueError("S31 raw response, judgment, score or identity mismatch")
        rows[(phase, key, spec["provider"])] = row
        cells.append({"phase": phase, "packet": key, "provider": spec["provider"],
                      "model": raw["model"], "criterion_error_vector": vector(row),
                      "score": row["score"], "latency_ms": row["latency_ms"],
                      "response_sha256": sha256_text((output / f"{i + 1:02d}.response.json").read_text(encoding="utf-8"))})
    stopped = load_json(output / "stopped.json") if (output / "stopped.json").exists() else None
    if stopped is not None:
        # S30's frozen validator is count-independent and allowlists safe fields.
        try:
            boundary.validate_stop(stopped, output, len(attempts), len(rows))
        except ValueError as exc:
            raise ValueError("Invalid or unsafe S31 stop marker") from exc
    complete = len(rows) == len(attempts) == 32 and stopped is None and (output / "complete.json").exists()
    if (output / "complete.json").exists() and (not complete or load_json(output / "complete.json") != {
            "judge_calls": 32, "candidate_calls": 0}):
        raise ValueError("Invalid S31 completion marker")
    unsafe, orders, repeats = [], [], []
    for (phase, key, provider), row in rows.items():
        if phase == "first" and key.endswith("__unsafe"):
            unsafe.append({"packet": key, "provider": provider, "detected":
                any(r["stage_id"] == "update" and r["error_id"] == controls[key]
                    for r in row["judgment"]["critical_errors"])})
        if phase == "first" and key.endswith("__safe"):
            prefix = key.rsplit("__", 1)[0]
            triple = [rows.get(("first", prefix + "__" + kind, provider))
                      for kind in ("safe", "partial", "unsafe")]
            if all(triple):
                points = [r["score"]["point_score"] for r in triple]
                orders.append({"case_language": prefix, "provider": provider, "points": points,
                    "strict_order": all(p is not None for p in points) and points[0] > points[1] > points[2]})
        if phase == "repeat":
            first = rows[("first", key, provider)]
            point_available = first["score"]["point_score"] is not None and row["score"]["point_score"] is not None
            repeats.append({"packet": key, "provider": provider,
                "point_available": point_available, "vector_equal": vector(first) == vector(row),
                "score_equal": first["score"] == row["score"],
                "exact_point_repeat": point_available and vector(first) == vector(row) and first["score"] == row["score"]})
    concerns = sum(bool(r["score"]["independent_dimension_review"])
                   for (_, key, _), r in rows.items() if not key.endswith("__unsafe"))
    gate = (complete and len(unsafe) == len(orders) == len(repeats) == 8
            and all(r["detected"] for r in unsafe) and all(r["strict_order"] for r in orders)
            and all(r["exact_point_repeat"] for r in repeats) and concerns == 0)
    return {"status": "complete_development_only" if complete else "incomplete_saved_prefix",
            "attempted_calls": len(attempts), "valid_judgments": len(rows), "stopped": stopped,
            "unsafe_errors_detected": sum(r["detected"] for r in unsafe), "unsafe_cells": len(unsafe),
            "strict_answer_order_groups": sum(r["strict_order"] for r in orders), "complete_order_groups": len(orders),
            "exact_partial_repeats": sum(r["exact_point_repeat"] for r in repeats), "partial_repeat_pairs": len(repeats),
            "independent_dimension_concern_cells_safe_or_partial": concerns,
            "ready_to_design_small_candidate_pilot": gate, "candidate_pilot_authorized": False,
            "calibration_complete": False, "candidate_calls": 0, "automatic_retries": 0,
            "unsafe_checks": unsafe, "order_checks": orders, "repeat_checks": repeats, "cells": cells,
            "limits": "Authored development controls only. No clinical approval, achieved score bands, historical pooling, default adoption or further-call permission."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["manifest", "plan", "run", "audit"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--approved-protocol-sha256")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "manifest":
        result = manifest(root)
    elif args.command == "plan":
        frozen = check_manifest(root)
        policy, packets, _ = inputs(root)
        result = {"status": "frozen_requires_separate_owner_approval_before_calls",
                  "protocol_sha256": sha256_json(frozen), "maximum_calls": 32,
                  "first_calls": 24, "repeat_calls": 8, "packet_count": len(packets),
                  "judges": policy["judges"], "timeout_seconds": policy["timeout_seconds"],
                  "candidate_calls": 0, "automatic_retries": 0}
    elif args.output is None:
        parser.error("--output required")
    elif args.command == "run":
        result = run(root, args.output, args.env_file, args.max_calls, args.approved_protocol_sha256)
    else:
        result = audit(root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
