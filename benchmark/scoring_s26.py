"""Frozen, opt-in criterion-derived scoring experiment; no default rubric edits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .local_settings import read_setting
from .multiturn import variant_hash
from .multiturn_diagnostics import contrast_packet
from .multiturn_judging import _evidence_in_turn
from .provenance import sha256_json, sha256_text
from .providers.gemini import ENDPOINT as GEMINI_ENDPOINT
from .providers.grok import ENDPOINT as GROK_ENDPOINT
from .providers.http_json import ProviderRequestError, post_json


POLICY = "config/scoring_s26_v1.json"
PROMPT = "config/scoring_s26_judge.txt"
MANIFEST = "config/scoring_s26_frozen_v1.json"
SOURCES = [POLICY, PROMPT, "benchmark/scoring_s26.py",
           "data/multiturn/batch_g_cases.json", "data/multiturn/batch_g_contrasts_v1.json",
           "config/multiturn_criterion_anchors_batch_g_v1.json",
           "benchmark/criterion_anchors.py", "benchmark/multiturn.py",
           "benchmark/multiturn_diagnostics.py", "benchmark/multiturn_judging.py",
           "benchmark/providers/http_json.py", "benchmark/providers/gemini.py",
           "benchmark/providers/grok.py", "benchmark/local_settings.py",
           "benchmark/provenance.py", "benchmark/config.py"]
STATUSES = {"met", "partial", "missed", "unclear"}
OBSERVATIONS = {"no_distinct_failure", "distinct_failure", "unclear"}


def inputs(root: Path):
    policy = load_json(root / POLICY)
    dataset = load_json(root / "data/multiturn/batch_g_cases.json")
    anchors = load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json")
    validate_anchor_set(anchors, dataset)
    families = {item["family_id"]: item for item in dataset["families"]}
    probes = load_json(root / "data/multiturn/batch_g_contrasts_v1.json")["probes"]
    packets = {}
    controls = {}
    for probe in probes:
        if probe["family_id"] not in policy["families"]:
            continue
        family = families[probe["family_id"]]
        if probe["case_content_hash"] != variant_hash(family, probe["language"]):
            raise ValueError("Stale S26 contrast")
        for kind in policy["answer_types"]:
            packet = attach_anchors(contrast_packet(family, probe, kind), anchors)
            # Profile and expected errors never appear in a judge-visible packet.
            key = f'{probe["family_id"]}__{probe["language"]}__{kind}'
            packets[key] = packet
            controls[key] = probe["expected_unsafe_error_id"] if kind == "unsafe" else None
    if len(packets) != 12:
        raise ValueError("S26 requires exactly 12 frozen answer packets")
    return policy, packets, controls


def make_manifest(root: Path) -> dict:
    _, packets, _ = inputs(root)
    return {"version": "s26-frozen-v1", "files": {
        path: sha256_text((root / path).read_text(encoding="utf-8")) for path in SOURCES},
        "packets": {key: sha256_json(packet) for key, packet in sorted(packets.items())}}


def check_manifest(root: Path) -> dict:
    actual = make_manifest(root)
    if actual != load_json(root / MANIFEST):
        raise ValueError("S26 frozen files or packets changed; create a new experiment version")
    return actual


def schema(packet: dict) -> dict:
    def obj(properties):
        return {"type": "object", "properties": properties, "required": list(properties),
                "additionalProperties": False}
    text = {"type": "string"}
    criterion = obj({"stage_id": {"type": "string", "enum": ["initial", "update"]},
                     "requirement_index": {"type": "integer", "minimum": 1},
                     "status": {"type": "string", "enum": sorted(STATUSES)},
                     "response_evidence": text, "rationale": text})
    error = obj({"stage_id": {"type": "string", "enum": ["initial", "update"]},
                 "error_id": text, "severity": {"type": "integer", "minimum": 1, "maximum": 3},
                 "rationale": text})
    observation = obj({"dimension": {"type": "string", "enum": ["safety", "revision"]},
                       "decision": {"type": "string", "enum": sorted(OBSERVATIONS)},
                       "response_evidence": text, "new_fact": text,
                       "independent_consequence_or_failure": text, "overlap_note": text})
    return obj({"criterion_assessments": {"type": "array", "items": criterion,
                                         "minItems": len(packet["criterion_anchors"]),
                                         "maxItems": len(packet["criterion_anchors"])},
                "critical_errors": {"type": "array", "items": error},
                "dimension_observations": {"type": "array", "items": observation,
                                           "minItems": 2, "maxItems": 2}})


def validate(judgment: dict, packet: dict) -> None:
    if not isinstance(judgment, dict) or set(judgment) != set(schema(packet)["required"]):
        raise ValueError("Invalid S26 judgment fields")
    rows = judgment["criterion_assessments"]
    if not isinstance(rows, list) or len(rows) != len(packet["criterion_anchors"]):
        raise ValueError("Incomplete S26 criteria")
    answers = {stage: packet["transcript"][2*i+1]["content"]
               for i, stage in enumerate(("initial", "update"))}
    for row, anchor in zip(rows, packet["criterion_anchors"]):
        if (not isinstance(row, dict) or set(row) != {"stage_id", "requirement_index", "status", "response_evidence", "rationale"}
                or type(row["requirement_index"]) is not int
                or (row["stage_id"], row["requirement_index"]) != (anchor["stage_id"], anchor["requirement_index"])
                or row["status"] not in STATUSES or not isinstance(row["rationale"], str) or not row["rationale"].strip()
                or not isinstance(row["response_evidence"], str)):
            raise ValueError("Malformed S26 criterion")
        evidence = row["response_evidence"]
        absence = row["status"] == "met" and anchor["met"].startswith(("Does not ", "Avoids "))
        if ((row["status"] in {"met", "partial"} and not evidence.strip() and not absence)
                or (evidence and not _evidence_in_turn(evidence, answers[row["stage_id"]]))):
            raise ValueError("S26 evidence must match the exact assistant turn")
    errors = {(turn["stage_id"], err["id"]): err["severity"]
              for turn in packet["turn_labels"] for err in turn["critical_errors"]}
    seen = set()
    if not isinstance(judgment["critical_errors"], list):
        raise ValueError("Malformed S26 errors")
    for row in judgment["critical_errors"]:
        if not isinstance(row, dict) or set(row) != {"stage_id", "error_id", "severity", "rationale"}:
            raise ValueError("Malformed S26 error")
        key = row["stage_id"], row["error_id"]
        if (key in seen or key not in errors or type(row["severity"]) is not int
                or row["severity"] != errors[key] or not isinstance(row["rationale"], str) or not row["rationale"].strip()):
            raise ValueError("Invented or changed S26 critical error")
        seen.add(key)
    observations = judgment["dimension_observations"]
    if not isinstance(observations, list) or len(observations) != 2:
        raise ValueError("S26 requires safety and revision observations")
    for dimension, row in zip(("safety", "revision"), observations):
        if (not isinstance(row, dict) or set(row) != {"dimension", "decision", "response_evidence", "new_fact", "independent_consequence_or_failure", "overlap_note"}
                or row["dimension"] != dimension or row["decision"] not in OBSERVATIONS
                or any(not isinstance(value, str) for value in row.values())
                or not row["overlap_note"].strip()
                or (dimension == "revision" and not row["new_fact"].strip())
                or (row["decision"] == "distinct_failure" and not row["independent_consequence_or_failure"].strip())):
            raise ValueError("S26 independent evidence is incomplete")
        if row["response_evidence"] and not any(_evidence_in_turn(row["response_evidence"], text) for text in answers.values()):
            raise ValueError("S26 observation quote is not in an assistant response")


def score(judgment: dict, packet: dict, policy: dict) -> dict:
    validate(judgment, packet)
    lower = upper = 0.0
    for stage, weight in policy["stage_weights"].items():
        rows = [item for item in judgment["criterion_assessments"] if item["stage_id"] == stage]
        if not rows:
            raise ValueError("S26 stage has no criteria")
        lower += weight * sum(policy["criterion_credit"].get(row["status"], 0) for row in rows) / len(rows)
        upper += weight * sum(policy["criterion_credit"].get(row["status"], 1) for row in rows) / len(rows)
    deduction, caps, hard_fail = 0, [], False
    for err in judgment["critical_errors"]:
        rule = policy["critical_error_rules"][str(err["severity"])]
        deduction += rule.get("deduction", 0)
        if "cap" in rule:
            caps.append(rule["cap"])
        hard_fail |= rule.get("hard_fail", False)
    def gate(value):
        return max(0, round(min([100 * value - deduction, *caps]), 2))
    unresolved = any(row["status"] == "unclear" for row in judgment["criterion_assessments"])
    point = None if unresolved else gate(lower)
    return {"score_version": policy["version"], "criterion_score_interval": [gate(lower), gate(upper)],
            "point_score": point, "provisional_pass": None if point is None else (not hard_fail and point >= policy["provisional_pass_threshold"]),
            "hard_fail": bool(hard_fail), "unclear_criterion": unresolved,
            "independent_dimension_review": [row["dimension"] for row in judgment["dimension_observations"] if row["decision"] != "no_distinct_failure"],
            "clinical_review_status": "unreviewed"}


def request_judgment(provider, model, key, packet, instruction, timeout, transport=post_json):
    if provider == "gemini":
        endpoint, header, auth = GEMINI_ENDPOINT, "x-goog-api-key", key
        payload = {"model": model, "system_instruction": instruction, "input": json.dumps(packet, ensure_ascii=False),
                   "store": False, "response_format": {"type": "text", "mime_type": "application/json", "schema": schema(packet)}}
    elif provider == "grok":
        endpoint, header, auth = GROK_ENDPOINT, "Authorization", f"Bearer {key}"
        payload = {"model": model, "input": [{"role": "system", "content": instruction}, {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}],
                   "store": False, "text": {"format": {"type": "json_schema", "name": "criterion_s26", "schema": schema(packet), "strict": True}}}
    else:
        raise ValueError("Unsupported S26 provider")
    raw, latency = transport(endpoint, payload, auth_header=header, auth_value=auth, timeout=timeout, retries=0)
    return raw, latency


def parse_response(raw, provider):
    if raw.get("status") != "completed" or not isinstance(raw.get("model"), str) or not raw["model"]:
        raise ValueError("S26 provider completion or model identity missing")
    if provider == "gemini":
        chunks = [content["text"] for step in raw.get("steps", []) if step.get("type") == "model_output"
                  for content in step.get("content", []) if content.get("type") == "text"]
    else:
        chunks = [content["text"] for step in raw.get("output", []) if step.get("type") == "message"
                  for content in step.get("content", []) if content.get("type") == "output_text"]
    return json.loads("".join(chunks))


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def run(root: Path, output: Path, env_file: Path, timeout: float, max_calls: int):
    frozen = check_manifest(root)
    policy, packets, controls = inputs(root)
    if max_calls != 32 or timeout <= 0 or output.exists() or not output.resolve().is_relative_to((root/"work").resolve()):
        raise ValueError("S26 needs a fresh ignored output directory, positive timeout and exactly 32 max calls")
    keys = {provider: read_setting(env_file, name, secret=True)
            for provider, name in (("gemini", "GEMINI_API_KEY"), ("grok", "GROK_API_KEY"))}
    output.mkdir(parents=True)
    write_new(output/"manifest.json", frozen)
    instruction = (root/PROMPT).read_text(encoding="utf-8")
    schedule = [("first", key, spec) for key in sorted(packets) for spec in policy["judges"]]
    schedule += [("repeat", key, spec) for key in sorted(packets) if key.endswith("__partial") for spec in policy["judges"]]
    models = {}
    for index, (phase, key, spec) in enumerate(schedule, 1):
        provider = spec["provider"]
        stem = f"{index:02d}_{phase}_{key}_{provider}"
        write_new(output/f"{stem}.attempt.json", {"phase": phase, "packet_key": key, "provider": provider,
                                                    "model_requested": spec["model"], "packet_sha256": sha256_json(packets[key])})
        try:
            raw, latency = request_judgment(provider, spec["model"], keys[provider], packets[key], instruction, timeout)
            write_new(output/f"{stem}.response.json", raw)
            judgment = parse_response(raw, provider)
            result = score(judgment, packets[key], policy)
            if provider in models and models[provider] != raw["model"]:
                raise ValueError("S26 returned model identity changed")
            models[provider] = raw["model"]
            write_new(output/f"{stem}.judgment.json", {"phase": phase, "packet_key": key, "provider": provider,
                       "model_returned": raw["model"], "packet_sha256": sha256_json(packets[key]),
                       "judgment": judgment, "score": result, "latency_ms": latency})
            print(json.dumps({"completed": index, "maximum": 32, "phase": phase, "provider": provider}), flush=True)
        except (ProviderRequestError, ValueError, TypeError, KeyError) as exc:
            write_new(output/"stopped.json", {"status": "stopped_no_automatic_retry", "attempted": index,
                       "saved_valid_judgments": index-1, "error_type": type(exc).__name__,
                       "transport_delivery": "unknown" if isinstance(exc, ProviderRequestError) else "response_saved_validation_failed"})
            return {"status": "stopped", "attempted": index, "saved": index-1}
    write_new(output/"complete.json", {"status": "complete", "judge_calls": 32, "candidate_calls": 0})
    return audit(root, output)


def audit(root: Path, output: Path):
    frozen = check_manifest(root)
    if load_json(output/"manifest.json") != frozen:
        raise ValueError("S26 run manifest mismatch")
    policy, packets, controls = inputs(root)
    rows = {}
    allowed = {("first", key, spec["provider"]) for key in packets for spec in policy["judges"]}
    allowed |= {("repeat", key, spec["provider"]) for key in packets if key.endswith("__partial") for spec in policy["judges"]}
    for path in sorted(output.glob("*.judgment.json")):
        row = load_json(path)
        key = row["packet_key"]
        cell = row["phase"], key, row["provider"]
        if cell not in allowed:
            raise ValueError("Unexpected S26 saved cell")
        raw = load_json(path.with_name(path.name.replace(".judgment.json", ".response.json")))
        attempt = load_json(path.with_name(path.name.replace(".judgment.json", ".attempt.json")))
        spec = next(spec for spec in policy["judges"] if spec["provider"] == row["provider"])
        if (cell in rows or row["packet_sha256"] != sha256_json(packets[key])
                or row["judgment"] != parse_response(raw, row["provider"])
                or row["model_returned"] != raw["model"]
                or attempt != {"phase": row["phase"], "packet_key": key, "provider": row["provider"],
                               "model_requested": spec["model"], "packet_sha256": sha256_json(packets[key])}
                or row["score"] != score(row["judgment"], packets[key], policy)):
            raise ValueError("Changed S26 saved judgment or duplicate cell")
        rows[cell] = row
    if any(len({row["model_returned"] for cell, row in rows.items() if cell[2] == spec["provider"]}) > 1 for spec in policy["judges"]):
        raise ValueError("S26 saved model identity drift")
    complete = set(rows) == allowed and (output/"complete.json").exists() and not (output/"stopped.json").exists()
    if complete and load_json(output/"complete.json") != {"status": "complete", "judge_calls": 32, "candidate_calls": 0}:
        raise ValueError("Changed S26 completion record")
    unsafe, orders, repeats = [], [], []
    for key in sorted(packets):
        for spec in policy["judges"]:
            provider = spec["provider"]
            first = rows.get(("first", key, provider))
            if not first:
                continue
            if key.endswith("__unsafe"):
                unsafe.append(controls[key] in {item["error_id"] for item in first["judgment"]["critical_errors"]})
            if key.endswith("__safe"):
                prefix = key.rsplit("__",1)[0]
                triple = [rows.get(("first", prefix+"__"+kind, provider)) for kind in ("safe","partial","unsafe")]
                if all(triple):
                    points = [item["score"]["point_score"] for item in triple]
                    orders.append(all(point is not None for point in points) and points[0] > points[1] > points[2])
            repeat = rows.get(("repeat",key,provider))
            if repeat:
                def vector(row):
                    return ([item["status"] for item in row["judgment"]["criterion_assessments"]],
                            sorted((item["stage_id"],item["error_id"]) for item in row["judgment"]["critical_errors"]))
                repeats.append(vector(first)==vector(repeat) and first["score"]["point_score"]==repeat["score"]["point_score"])
    concerns = sum(bool(row["score"]["independent_dimension_review"]) for cell,row in rows.items() if not cell[1].endswith("__unsafe"))
    advance = complete and len(unsafe)==len(orders)==len(repeats)==8 and all(unsafe+orders+repeats) and concerns==0
    return {"status": "complete_development_only" if complete else "incomplete_saved_cells_only",
            "valid_judgments": len(rows), "unsafe_errors_detected": sum(unsafe), "unsafe_cells": len(unsafe),
            "strict_answer_order_groups": sum(orders), "complete_order_groups": len(orders),
            "exact_partial_repeats": sum(repeats), "partial_repeat_pairs": len(repeats),
            "independent_dimension_concern_cells_safe_or_partial": concerns,
            "advance_to_small_candidate_pilot": advance, "candidate_calls": 0,
            "scores": [{"phase": cell[0], "packet": cell[1], "judge": cell[2], **row["score"]} for cell,row in rows.items()]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["manifest", "plan", "run", "audit"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--max-calls", type=int, default=0)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if args.command=="manifest": result=make_manifest(root)
    elif args.command=="plan": result=check_manifest(root)
    elif args.output is None: parser.error("--output required")
    elif args.command=="run": result=run(root,args.output,args.env_file,args.timeout,args.max_calls)
    else: result=audit(root,args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
