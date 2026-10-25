"""Frozen focused boundary trial; no live calls without a new scoped approval."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
from uuid import UUID

from scripts import judge_cap_s49 as prior, medication_boundaries_s49 as draft

old, capture, guard, score = prior.old, prior.capture, prior.guard, prior.score
read_json, write_json, sha256_json = prior.read_json, prior.write_json, prior.sha256_json
account_response = prior.prior.previous.account
VERSION = "s50-medication-boundary-v1"
PLAN = "config/medication_boundary_s50_v1.json"
PROMPT = "config/medication_boundary_s50_judge.txt"
FREEZE = "config/medication_boundary_s50_frozen_v1.json"
MODEL, MAXIMUM, THRESHOLD = "gemini-3.8-flash", 56, 30_000_000_000
STATUSES = ("met", "partial", "missed", "unclear")
ROW_FIELDS = {"requirement_index", "status", "response_evidence", "rationale"}


def plan(root):
    value = read_json(root / PLAN)
    fixed = {"version": VERSION, "judge_provider": "gemini", "judge_model": MODEL,
        "family_id": "HC-MT-MEDSAFE-013", "first_pass_requests": 28, "repeat_requests": 28,
        "maximum_attempts": MAXIMUM, "candidate_calls": 0, "automatic_retries": 0,
        "max_output_tokens": 32768, "thinking_level": "medium", "sampling": "provider_defaults_unpinned",
        "stop_threshold_usd": "3.00", "hard_ceiling": False,
        "schedule": "packet_sha256_ascending_first_then_identical_repeat",
        "reference_status": "author_hypotheses_not_clinical_gold",
        "gate": {"accepted_judgments": 56, "first_author_hypothesis_matches": 16,
                 "exact_status_repeats": 28, "exploratory_packets_have_no_expected_status": 12},
        "live_authorization": "requires_separate_user_approval"}
    if guard._json_bytes(value) != guard._json_bytes(fixed):
        raise ValueError("Trial scope changed")
    return value


def schema(packet):
    index = packet["target_requirements"][0]["requirement_index"]
    return {"type": "object", "properties": {"criterion_assessments": {
        "type": "array", "minItems": 1, "maxItems": 1, "items": {
            "type": "object", "properties": {"requirement_index": {"type": "integer", "enum": [index]},
                "status": {"type": "string", "enum": list(STATUSES)},
                "response_evidence": {"type": "string"}, "rationale": {"type": "string"}},
            "required": sorted(ROW_FIELDS), "additionalProperties": False}}},
        "required": ["criterion_assessments"], "additionalProperties": False}


def validate(judgment, packet):
    if not isinstance(judgment, dict) or set(judgment) != {"criterion_assessments"}:
        raise ValueError("Unexpected focused judgment fields")
    rows = judgment["criterion_assessments"]
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError("Exactly one target required")
    row = rows[0]; expected = packet["target_requirements"][0]["requirement_index"]
    if (not isinstance(row, dict) or set(row) != ROW_FIELDS
            or type(row["requirement_index"]) is not int or row["requirement_index"] != expected
            or not isinstance(row["status"], str) or row["status"] not in STATUSES
            or not isinstance(row["rationale"], str) or not row["rationale"].strip()):
        raise ValueError("Invalid focused assessment")
    stage = packet["scoring_stage"]
    answer = packet["transcript"][1 if stage == "initial" else 3]["content"]
    score.validate_quote(row["response_evidence"], [answer], required=row["status"] in {"met", "partial"})


def decode(raw, packet):
    if not isinstance(raw, dict) or raw.get("status") != "completed" or raw.get("model") != MODEL:
        raise ValueError("Exact model and completed response required")
    chunks = [c["text"] for step in raw.get("steps", []) if step.get("type") == "model_output"
              for c in step.get("content", []) if c.get("type") == "text"]
    result = capture.strict_json("".join(chunks).encode("utf-8"))
    validate(result, packet)
    return result


def jobs(root):
    spec = plan(root); draft.audit(root); packets = draft.packets(root)
    ordered = sorted(packets, key=lambda key: sha256_json(packets[key]))
    result = []
    for phase in ("first", "repeat"):
        for key in ordered:
            packet = packets[key]; packet_hash = sha256_json(packet)
            payload = {"model": MODEL, "system_instruction": (root / PROMPT).read_text(),
                "input": json.dumps(packet, ensure_ascii=False), "store": False,
                "generation_config": {"max_output_tokens": spec["max_output_tokens"], "thinking_level": spec["thinking_level"]},
                "response_format": {"type": "text", "mime_type": "application/json", "schema": schema(packet)}}
            result.append({"row": {"sequence": len(result)+1, "phase": phase, "packet_key": key,
                "packet_sha256": packet_hash, "language": packet["language"], "stage": packet["scoring_stage"]},
                "packet": packet, "payload": payload})
    if len(result) != MAXIMUM or len({j["row"]["packet_sha256"] for j in result}) != 28:
        raise ValueError("Missing or duplicate packets")
    return result


def snapshot(root):
    selected = jobs(root)
    paths = (PLAN, PROMPT, draft.DATA, "scripts/medication_boundaries_s49.py",
             "scripts/medication_boundary_s50.py", "tests/test_medication_boundary_s50.py")
    return {"version": VERSION, "s49_protocol_sha256": prior.audit(root)["protocol_sha256"],
        "files": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
        "draft_audit": draft.audit(root), "schedule_sha256": sha256_json([j["row"] for j in selected]),
        "requests_sha256": sha256_json([j["payload"] for j in selected])}


def audit(root):
    current = snapshot(root)
    if current != read_json(root / FREEZE):
        raise ValueError("Frozen boundary protocol changed")
    return {"protocol_sha256": sha256_json(current), "plan": plan(root),
            "ready_for_separately_authorized_run": True, "live_calls_made_by_audit": 0}


def analyze(root, selected, judgments, mode):
    value, _, _ = draft.load(root)
    hypotheses = {p["id"]+"__"+lang: p["author_hypothesis"] for p in value["profiles"] for lang in draft.LANGS}
    by_cell, cells = {}, []
    for sequence, judgment in sorted(judgments.items()):
        if type(sequence) is not int or not 1 <= sequence <= MAXIMUM:
            raise ValueError("Unknown judgment sequence")
        job = selected[sequence-1]; validate(judgment, job["packet"])
        row = job["row"]; status = judgment["criterion_assessments"][0]["status"]
        by_cell[row["phase"], row["packet_key"]] = status
        cells.append({**row, "status": status, "author_hypothesis": hypotheses[row["packet_key"]]})
    known = [(actual, hypotheses[key]) for (phase, key), actual in by_cell.items() if phase == "first" and hypotheses[key] is not None]
    exploratory = [(key, actual) for (phase, key), actual in by_cell.items() if phase == "first" and hypotheses[key] is None]
    repeats = [{"packet_key": key, "first": by_cell["first", key], "repeat": status,
                "match": by_cell["first", key] == status}
               for (phase, key), status in by_cell.items() if phase == "repeat" and ("first", key) in by_cell]
    contrasts = []
    for pair in value["contrasts"]:
        for lang in draft.LANGS:
            for phase in ("first", "repeat"):
                a, b = pair["a"]+"__"+lang, pair["b"]+"__"+lang
                contrasts.append({"phase": phase, "language": lang, **pair,
                    "a_status": by_cell.get((phase, a)), "b_status": by_cell.get((phase, b)),
                    "interpretation": "descriptive_pair_not_clinical_correctness"})
    language_pairs = []
    for profile in value["profiles"]:
        for phase in ("first", "repeat"):
            en, zh = (by_cell.get((phase, profile["id"]+"__"+lang)) for lang in draft.LANGS)
            language_pairs.append({"profile": profile["id"], "phase": phase, "en": en, "zh-Hans": zh,
                                   "same_status": None if en is None or zh is None else en == zh})
    matches = sum(a == b for a, b in known); repeat_matches = sum(r["match"] for r in repeats)
    complete = len(judgments) == MAXIMUM
    gate = complete and len(known) == matches == 16 and len(repeats) == repeat_matches == 28 and len(exploratory) == 12
    return {"mode": mode, "simulation_only": mode == "offline_fixture", "valid_judgments": len(judgments),
        "expected_judgments": MAXIMUM, "first_author_hypothesis_observed": len(known),
        "first_author_hypothesis_expected": 16, "first_author_hypothesis_matches": matches,
        "exploratory_first_observed": len(exploratory), "exploratory_first_expected": 12,
        "repeat_pairs_observed": len(repeats), "repeat_pairs_expected": 28, "exact_status_repeats": repeat_matches,
        "complete": complete, "author_boundary_gate": gate, "cells": cells, "repeats": repeats,
        "contrasts": contrasts, "language_pairs": language_pairs, "numeric_scores": False,
        "clinical_accuracy": None, "calibration_complete": False, "rankings_approved": False,
        "next_paid_run_authorized": False,
        "interpretation": "Developer-hypothesis agreement and status repeatability only. Unlabelled cells have no correctness target; matching status does not prove matching rationale or clinical truth."}


def manifest(protocol, mode, selected):
    if mode not in {"live", "offline_fixture"}: raise ValueError("Explicit mode required")
    return {"version": VERSION, "protocol_sha256": protocol, "mode": mode,
        "schedule_sha256": sha256_json([j["row"] for j in selected]), "maximum_attempts": MAXIMUM,
        "stop_threshold_usd": "3.00", "resume_allowed": False}


def replay(root, directory, protocol, *, threshold=THRESHOLD):
    directory = Path(directory); saved = read_json(directory / "manifest.json"); mode = saved["mode"]
    selected = jobs(root)
    if saved != manifest(protocol, mode, selected): raise ValueError("Manifest changed")
    if mode == "live" and (threshold != THRESHOLD or audit(root)["protocol_sha256"] != protocol):
        raise ValueError("Live scope changed")
    cap = directory / "capture"
    if read_json(cap / "run.json") != {"mode": mode, "automatic_retries": 0, "max_attempts": MAXIMUM,
            "protocol_sha256": protocol, "resume_allowed": False, "costs_are_simulated": mode == "offline_fixture"}:
        raise ValueError("Capture scope changed")
    allowed = re.compile(r"(\d{4})\.(attempt\.json|payload\.json|raw\.bin|capture\.json|accounting\.json|accepted\.json|rejected\.json)")
    for p in cap.iterdir():
        match = allowed.fullmatch(p.name)
        if p.is_symlink() or not p.is_file() or p.name != "run.json" and (not match or not 1 <= int(match[1]) <= MAXIMUM):
            raise ValueError("Unexpected capture")
    attempts = sorted(int(p.name[:4]) for p in cap.glob("*.attempt.json"))
    if attempts != list(range(1, len(attempts)+1)):
        raise ValueError("Missing attempt prefix")
    if any(p.name != "run.json" and int(p.name[:4]) not in attempts for p in cap.iterdir()):
        raise ValueError("Orphan capture")
    accounts, judgments, failures = [], {}, []
    monitored, terminal = 0, None
    spec = next(v for v in draft.workflow.design(root)["judges"] if v["model"] == MODEL)
    for i in attempts:
        if terminal: raise ValueError("Dispatch after stop")
        job = selected[i-1]; stem = f"{i:04d}"
        expected = {"sequence": i, "provider": "gemini", "model": MODEL, "protocol_sha256": protocol,
            "payload_sha256": hashlib.sha256(guard._json_bytes(job["payload"])).hexdigest(),
            "delivery": "reserved_before_connection", "prospective_cost_bound": None,
            "automatic_retries": 0, "fixture_only": mode == "offline_fixture"}
        if read_json(cap / (stem+".attempt.json")) != expected: raise ValueError("Attempt binding changed")
        if (cap / (stem+".payload.json")).exists() and (cap / (stem+".payload.json")).read_bytes() != guard._json_bytes(job["payload"]):
            raise ValueError("Payload changed")
        if not all((cap / (stem+suffix)).exists() for suffix in (".payload.json", ".capture.json", ".accounting.json")):
            accounts.append(account_response(None, spec))
            terminal = "interrupted_unknown_delivery_or_charge"
            failures.append({"sequence": i, "category": terminal})
            continue
        meta = read_json(cap / (stem+".capture.json")); raw_path = cap / (stem+".raw.bin")
        body = raw_path.read_bytes() if raw_path.exists() else b""
        if (meta["mode"] != mode or meta["fixture_only"] != (mode == "offline_fixture")
                or meta["bytes_saved"] != len(body)
                or meta["body_sha256"] is not None and meta["body_sha256"] != hashlib.sha256(body).hexdigest()):
            raise ValueError("Raw response binding changed")
        account, raw = account_response(None, spec), None
        if (type(meta["status"]) is int and 200 <= meta["status"] < 300 and meta["body_eof"]
                and meta["category"] in {"accepted", "response_validation", "model_identity", "usage_accounting"}):
            raw = capture.strict_json(body)
            account = account_response(raw, spec, job["payload"])
        if read_json(cap / (stem+".accounting.json")) != account: raise ValueError("Accounting changed")
        accounts.append(account); delta = old.monitoring_delta(account, "gemini")["delta_ticks"]
        monitored += delta or 0
        if meta["category"] == "accepted":
            judgment = decode(raw, job["packet"])
            if (delta is None or read_json(cap / (stem+".accepted.json")) != {"result": judgment, "raw_sha256": meta["body_sha256"]}
                    or (cap / (stem+".rejected.json")).exists()):
                raise ValueError("Acceptance differs from raw response")
            judgments[i] = judgment
        else:
            if ((cap / (stem+".accepted.json")).exists()
                    or read_json(cap / (stem+".rejected.json"))["category"] != meta["category"]):
                raise ValueError("Rejection changed")
            failures.append({"sequence": i, "category": meta["category"], "http_status": meta["status"]})
        if delta is None: terminal = "unknown_charge"
        elif meta["category"] != "accepted": terminal = meta["category"]
        elif monitored >= threshold: terminal = "spend_threshold_reached"
    summary = analyze(root, selected, judgments, mode)
    return {"version": VERSION, "protocol_sha256": protocol, "mode": mode,
        "terminal": terminal or ("schedule_complete" if summary["complete"] else "incomplete_no_resume"),
        "attempts": len(attempts), "maximum_attempts": MAXIMUM, "candidate_calls": 0,
        "automatic_retries": 0, "monitoring_known_subtotal_usd": format(Decimal(monitored)/old.TICKS_PER_USD, "f"),
        "accounting": old.usage.summarize(accounts), "stop_threshold_usd": "3.00", "hard_ceiling": False,
        "failures": failures, "analysis": summary}


def execute(root, directory, protocol, credential, connection_factory, mode, *, threshold=THRESHOLD):
    if mode == "live" and (threshold != THRESHOLD or audit(root)["protocol_sha256"] != protocol):
        raise ValueError("Live scope changed")
    directory = Path(directory); selected = jobs(root)
    write_json(directory / "manifest.json", manifest(protocol, mode, selected))
    journal = capture.CaptureJournal(root, directory / "capture", MAXIMUM, protocol, mode)
    monitored = 0
    try:
        for job in selected:
            if mode == "live" and audit(root)["protocol_sha256"] != protocol:
                raise ValueError("Inputs changed during execution")
            result = journal.exchange("gemini", job["payload"], lambda raw: decode(raw, job["packet"]),
                                      credential=credential, connection_factory=connection_factory)
            delta = old.monitoring_delta(result["accounting"], "gemini")["delta_ticks"]
            monitored += delta or 0
            if mode == "live":
                print(json.dumps({"sequence": job["row"]["sequence"], "phase": job["row"]["phase"],
                    "accepted": result["accepted"], "known_monitoring_subtotal_usd": format(Decimal(monitored)/old.TICKS_PER_USD, "f")}), flush=True)
            if not result["accepted"] or delta is None or monitored >= threshold: break
    finally:
        credential = ""
        report = replay(root, directory, protocol, threshold=threshold)
        write_json(directory / "report.json", report)
    return report


def consume(root, protocol, run_id):
    path = old.prior._private_path(root, "work/s50-consumed-protocols", directory=True, create=True)
    write_json(path / (protocol+".json"), {"protocol_sha256": protocol, "run_id": run_id, "maximum_attempts": MAXIMUM})


def run_live(root, run_id, note, approved_protocol):
    checked = audit(root); protocol = checked["protocol_sha256"]
    if (approved_protocol != protocol or not isinstance(note, str) or not note.strip() or str(UUID(run_id)) != run_id):
        raise ValueError("Fresh scoped approval, matching protocol and canonical UUID required")
    relative = "work/s50-runs/"+run_id
    if subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=root, capture_output=True).returncode:
        raise ValueError("Private output must be ignored")
    parent = old.prior._private_path(root, "work/s50-runs", directory=True, create=True)
    if (parent / run_id).exists(): raise ValueError("Cannot reuse a run")
    consume(root, protocol, run_id); directory = parent / run_id; directory.mkdir(mode=0o700)
    write_json(directory / "authorization.json", {"authorization_evidence": note,
        "issued_at": datetime.now(timezone.utc).isoformat(), "protocol_sha256": protocol,
        "maximum_attempts": MAXIMUM, "stop_threshold_usd": "3.00", "last_request_overrun_accepted": True,
        "candidate_calls": 0, "no_old_allowance_reused": True})
    key = ""
    try:
        key = old.prior.read_setting(root / ".env.local", "GEMINI_API_KEY", secret=True)
        return execute(root, directory, protocol, key, old.prior.create_tls_connection, "live")
    finally: key = ""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("snapshot", "audit", "run", "report"))
    p.add_argument("--run-id"); p.add_argument("--authorization-note", default="")
    p.add_argument("--approved-protocol-sha256"); p.add_argument("--directory")
    args = p.parse_args(); root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "snapshot": result = snapshot(root)
        elif args.command == "audit": result = audit(root)
        elif args.command == "run": result = run_live(root, args.run_id, args.authorization_note, args.approved_protocol_sha256)
        else:
            directory = old.prior._private_path(root, args.directory, directory=True)
            result = replay(root, directory, audit(root)["protocol_sha256"])
            if result != read_json(directory / "report.json"): raise ValueError("Report differs from replay")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "run" and not result["analysis"]["complete"]:
            p.exit(1, "S50 stopped incomplete. No retry or automatic expansion.\n")
    except Exception:
        p.exit(2, "S50 blocked/stopped. Private evidence retained; no automatic retry.\n")


if __name__ == "__main__": main()
