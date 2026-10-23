"""Frozen two-criterion probe; explicit external-call acknowledgment is required."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import boundary_s30_draft as draft
from . import scoring_s26 as base
from . import transport_s29 as historical
from .config import load_json
from .local_settings import read_setting
from .provenance import sha256_json, sha256_text
from .providers.observed_http import DiagnosticRequestError, post_json_observed

POLICY = "config/s30_boundary_policy_v1.json"
PROMPT = "config/s30_boundary_judge.txt"
MANIFEST = "config/s30_boundary_frozen_v1.json"
SOURCES = sorted(set(historical.SOURCES + [historical.MANIFEST, POLICY, PROMPT,
    draft.ANCHORS, draft.FIXTURES, "benchmark/boundary_s30_draft.py", "benchmark/boundary_s30.py"]))
STATUSES = ("met", "partial", "missed", "unclear")
JUDGES = [{"provider": "gemini", "model": "gemini-3.8-flash"},
          {"provider": "grok", "model": "grok-4.7"}]
ROW_FIELDS = {"requirement_index", "status", "response_evidence", "rationale"}
SCHEMA = {"type": "object", "properties": {"criterion_assessments": {
    "type": "array", "minItems": 2, "maxItems": 2, "items": {
        "type": "object", "properties": {
            "requirement_index": {"type": "integer", "enum": [1, 3]},
            "status": {"type": "string", "enum": list(STATUSES)},
            "response_evidence": {"type": "string"}, "rationale": {"type": "string"}},
        "required": sorted(ROW_FIELDS), "additionalProperties": False}}},
    "required": ["criterion_assessments"], "additionalProperties": False}


def inputs(root):
    historical.check_manifest(root)
    policy = load_json(root / POLICY)
    packets, expected, repeats = draft.build_packets(*draft.inputs(root))
    if (policy["version"] != "s30-boundary-v1" or policy["judges"] != JUDGES
            or [policy[k] for k in ("first_calls", "repeat_calls", "maximum_calls",
                                   "automatic_retries", "candidate_calls", "request_timeout_seconds")]
            != [20, 4, 24, 0, 0, 240]
            or policy["sampling"] != "provider_defaults_unpinned"):
        raise ValueError("Unexpected S30 policy")
    return policy, packets, expected, repeats


def schedule(policy, packets, repeats):
    ordered = sorted(packets, key=lambda key: sha256_json(packets[key]))
    return [(phase, key, judge) for phase in ("first", "repeat")
            for key in ordered if phase == "first" or key in repeats for judge in policy["judges"]]


def manifest(root):
    policy, packets, _, repeats = inputs(root)
    return {"version": "s30-frozen-v1",
            "files": {p: sha256_text((root / p).read_text(encoding="utf-8")) for p in SOURCES},
            "packets": {k: sha256_json(v) for k, v in sorted(packets.items())},
            "schedule_sha256": sha256_json(schedule(policy, packets, repeats)),
            "output_schema_sha256": sha256_json(SCHEMA)}


def check_manifest(root):
    actual = manifest(root)
    if actual != load_json(root / MANIFEST):
        raise ValueError("S30 frozen input changed; create a new experiment version")
    return actual


def validate(judgment, packet):
    if not isinstance(judgment, dict) or set(judgment) != {"criterion_assessments"}:
        raise ValueError("Invalid S30 judgment fields")
    rows = judgment["criterion_assessments"]
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("S30 requires exactly two criteria")
    answer = packet["transcript"][3]["content"]
    for index, row in zip((1, 3), rows):
        if (not isinstance(row, dict) or set(row) != ROW_FIELDS
                or type(row["requirement_index"]) is not int or row["requirement_index"] != index
                or row["status"] not in STATUSES
                or not isinstance(row["rationale"], str) or not row["rationale"].strip()
                or not isinstance(row["response_evidence"], str)):
            raise ValueError("Invalid S30 criterion row or order")
        evidence = row["response_evidence"]
        if ((row["status"] in ("met", "partial") and not evidence.strip())
                or (evidence and evidence not in answer)):
            raise ValueError("S30 evidence must be literal update text")


def request(provider, model, key, packet, instruction, timeout):
    if provider == "gemini":
        endpoint, header, auth = base.GEMINI_ENDPOINT, "x-goog-api-key", key
        payload = {"model": model, "system_instruction": instruction,
                   "input": json.dumps(packet, ensure_ascii=False), "store": False,
                   "response_format": {"type": "text", "mime_type": "application/json", "schema": SCHEMA}}
    elif provider == "grok":
        endpoint, header, auth = base.GROK_ENDPOINT, "Authorization", f"Bearer {key}"
        payload = {"model": model, "input": [{"role": "system", "content": instruction},
                   {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}], "store": False,
                   "text": {"format": {"type": "json_schema", "name": "boundary_s30",
                                          "schema": SCHEMA, "strict": True}}}
    else:
        raise ValueError("Unsupported S30 provider")
    return post_json_observed(endpoint, payload, auth_header=header, auth_value=auth,
                              timeout=timeout, retries=0)


def attempt(phase, key, spec, packet):
    return {"phase": phase, "packet_key": key, "provider": spec["provider"],
            "model_requested": spec["model"], "packet_sha256": sha256_json(packet),
            "timeout_seconds": 240, "automatic_retries": 0}


def run(root, output, env_file, max_calls, approved_protocol_sha256=None):
    frozen = check_manifest(root)
    if (max_calls != 24 or approved_protocol_sha256 != sha256_json(frozen)
            or output.exists() or not output.resolve().is_relative_to((root / "work").resolve())):
        raise ValueError("S30 requires a fresh work/ output, max-calls 24 and the approved protocol SHA256")
    policy, packets, _, repeats = inputs(root)
    keys = {p: read_setting(env_file, name, secret=True)
            for p, name in (("gemini", "GEMINI_API_KEY"), ("grok", "GROK_API_KEY"))}
    output.mkdir(parents=True, mode=0o700)
    base.write_new(output / "manifest.json", frozen)
    # The CLI acknowledgment binds scope; it is not independent proof of owner consent.
    base.write_new(output / "external_call_acknowledgment.json",
                   {"protocol_sha256": approved_protocol_sha256, "maximum_calls": 24})
    instruction = (root / PROMPT).read_text(encoding="utf-8")
    for i, (phase, key, spec) in enumerate(schedule(policy, packets, repeats), 1):
        record = attempt(phase, key, spec, packets[key])
        base.write_new(output / f"{i:02d}.attempt.json", record)
        try:
            raw, latency = request(spec["provider"], spec["model"], keys[spec["provider"]],
                                   packets[key], instruction, policy["request_timeout_seconds"])
            base.write_new(output / f"{i:02d}.response.json", raw)
            judgment = base.parse_response(raw, spec["provider"])
            if raw["model"] != spec["model"] or type(latency) is not int or latency < 0:
                raise ValueError("Unexpected S30 model or latency")
            validate(judgment, packets[key])
            base.write_new(output / f"{i:02d}.judgment.json", {
                **record, "model_returned": raw["model"], "judgment": judgment, "latency_ms": latency})
            print(json.dumps({"completed": i, "maximum": 24, "phase": phase,
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
    base.write_new(output / "complete.json", {"judge_calls": 24, "candidate_calls": 0})
    return audit(root, output)


def validate_stop(marker, output, attempt_count, row_count):
    common = {"attempted", "saved", "kind"}
    if (not isinstance(marker, dict) or type(marker.get("attempted")) is not int
            or type(marker.get("saved")) is not int or marker["attempted"] != attempt_count
            or marker["saved"] != row_count or attempt_count != row_count + 1
            or (output / "complete.json").exists()):
        raise ValueError("Invalid S30 stop marker")
    if marker["kind"] == "transport_failure":
        if set(marker) != common | {"diagnostic"}:
            raise ValueError("Unsafe S30 stop fields")
        d = marker["diagnostic"]
        if (not isinstance(d, dict) or set(d) != {"version", "category", "http_status", "elapsed_ms",
                "delivery", "attempts", "automatic_retries"}
                or d["version"] != "transport-diagnostic-v1"
                or type(d["attempts"]) is not int or d["attempts"] != 1
                or type(d["automatic_retries"]) is not int or d["automatic_retries"] != 0
                or d["category"] not in {"http_error", "timeout", "tls_error", "dns_error", "network_error",
                                         "unreadable_json", "unclassified_error"}
                or d["delivery"] not in {"unknown", "response_received", "error_response_received_execution_unknown"}
                or type(d["elapsed_ms"]) is not int or d["elapsed_ms"] < 0
                or not (d["http_status"] is None or type(d["http_status"]) is int
                        and 100 <= d["http_status"] <= 599)):
            raise ValueError("Unsafe S30 diagnostic fields")
        if (output / f"{attempt_count:02d}.response.json").exists():
            raise ValueError("Transport failure cannot claim a saved JSON response")
    elif marker["kind"] == "response_validation_failure":
        if (set(marker) != common | {"error_type", "delivery"}
                or marker["error_type"] not in {"ValueError", "TypeError", "KeyError", "AttributeError", "JSONDecodeError"}
                or marker["delivery"] != "response_saved_validation_failed"
                or not (output / f"{attempt_count:02d}.response.json").exists()):
            raise ValueError("Invalid S30 validation stop")
    else:
        raise ValueError("Unknown S30 stop kind")


def audit(root, output):
    frozen = check_manifest(root)
    if (load_json(output / "manifest.json") != frozen
            or load_json(output / "external_call_acknowledgment.json") != {
                "protocol_sha256": sha256_json(frozen), "maximum_calls": 24}):
        raise ValueError("Saved S30 manifest or acknowledgment mismatch")
    policy, packets, expected, repeats = inputs(root)
    plan = schedule(policy, packets, repeats)
    attempts = sorted(output.glob("*.attempt.json"))
    paths = sorted(output.glob("*.judgment.json"))
    responses = sorted(output.glob("*.response.json"))
    if not 0 <= len(paths) <= len(responses) <= len(attempts) <= 24 or len(attempts) > len(paths) + 1:
        raise ValueError("Invalid S30 artifact counts")
    for paths_to_check, suffix in ((attempts, "attempt"), (paths, "judgment"), (responses, "response")):
        if [p.name for p in paths_to_check] != [f"{i:02d}.{suffix}.json" for i in range(1, len(paths_to_check) + 1)]:
            raise ValueError("S30 artifacts must be a contiguous prefix")
    for i, path in enumerate(attempts):
        phase, key, spec = plan[i]
        if load_json(path) != attempt(phase, key, spec, packets[key]):
            raise ValueError("S30 saved attempt differs from schedule")
    rows, cells = {}, []
    for i, path in enumerate(paths):
        phase, key, spec = plan[i]
        raw = load_json(output / f"{i + 1:02d}.response.json")
        row = load_json(path)
        record = attempt(phase, key, spec, packets[key])
        if (set(row) != set(record) | {"model_returned", "judgment", "latency_ms"}
                or any(row[k] != v for k, v in record.items())
                or not isinstance(raw, dict) or raw.get("model") != spec["model"]
                or row["model_returned"] != raw["model"]
                or row["judgment"] != base.parse_response(raw, spec["provider"])
                or type(row["latency_ms"]) is not int or row["latency_ms"] < 0):
            raise ValueError("S30 saved response or judgment mismatch")
        validate(row["judgment"], packets[key])
        statuses = [r["status"] for r in row["judgment"]["criterion_assessments"]]
        rows[(phase, key, spec["provider"])] = statuses
        cells.append({"phase": phase, "fixture": key, "provider": spec["provider"],
                      "model": raw["model"], "statuses": statuses, "author_expected_statuses": expected[key],
                      "latency_ms": row["latency_ms"],
                      "response_sha256": sha256_text((output / f"{i + 1:02d}.response.json").read_text(encoding="utf-8"))})
    stopped = load_json(output / "stopped.json") if (output / "stopped.json").exists() else None
    if stopped is not None:
        validate_stop(stopped, output, len(attempts), len(rows))
    complete = len(rows) == len(attempts) == 24 and stopped is None and (output / "complete.json").exists()
    if (output / "complete.json").exists() and (not complete or load_json(output / "complete.json") != {
            "judge_calls": 24, "candidate_calls": 0}):
        raise ValueError("Invalid S30 completion marker")
    known = [actual == want for (phase, key, _), statuses in rows.items()
             if phase == "first" and expected[key] is not None
             for actual, want in zip(statuses, expected[key])]
    repeated = [actual == previous for (phase, key, provider), statuses in rows.items() if phase == "repeat"
                for actual, previous in zip(statuses, rows[("first", key, provider)])]
    gate = complete and len(known) == 32 and all(known) and len(repeated) == 8 and all(repeated)
    return {"status": "complete_focused_development_probe" if complete else "incomplete_saved_prefix",
            "attempted_calls": len(attempts), "valid_judgments": len(rows), "stopped": stopped,
            "known_first_criterion_matches": sum(known), "known_first_criterion_count": len(known),
            "repeat_criterion_matches": sum(repeated), "repeat_criterion_count": len(repeated),
            "exploratory_first_judgments": sum(phase == "first" and expected[key] is None for phase, key, _ in rows),
            "ready_to_design_full_scoring_repeat": gate, "calibration_complete": False,
            "candidate_pilot_authorized": False, "candidate_calls": 0, "automatic_retries": 0,
            "cells": cells, "limits": "Author-hypothesis agreement and repeatability only; no numerical scoring, clinical adjudication, default adoption, pooling or further-call permission."}


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
        result = {"status": "frozen_requires_separate_owner_approval_before_calls",
                  "protocol_sha256": sha256_json(frozen), "maximum_calls": 24,
                  "first_calls": 20, "repeat_calls": 4, "judges": JUDGES, "candidate_calls": 0}
    elif args.output is None:
        parser.error("--output required")
    elif args.command == "run":
        result = run(root, args.output, args.env_file, args.max_calls, args.approved_protocol_sha256)
    else:
        result = audit(root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
