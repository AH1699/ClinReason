"""One separately authorized supplemental S48 judgment, changing only output cap."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
from uuid import UUID

from scripts import judge_saved_bank_s48 as prior

old, score, capture, guard = prior.old, prior.score, prior.capture, prior.guard
read_json, write_json, sha256_json = prior.read_json, prior.write_json, prior.sha256_json
VERSION = "s49-one-cell-output-cap-v1"
PLAN = "config/judge_cap_s49_v1.json"
FREEZE = "config/judge_cap_s49_frozen_v1.json"
SOURCE = "work/s48-runs/599d4390-fd99-4185-a627-b152034637b0"
MODEL = "gemini-3.8-flash"
THRESHOLD = 2_500_000_000


def source(root):
    checked, bank = prior.audit(root), prior.source(root)
    directory = old.prior._private_path(root, SOURCE, directory=True)
    report = prior.replay(root, directory, bank, checked["protocol_sha256"])
    if (report != read_json(directory / "report.json") or report["mode"] != "live"
            or report["attempts"] != 52 or report["accepted_judgments"] != 51
            or len(report["candidate_score_records"]) != 7 or not report["gate"]["pass"]
            or report["terminal"] != "response_validation"):
        raise ValueError("Expected exact stopped S48 source")
    selected = prior.jobs(root, bank, "live")
    job, initial_job = selected[51], selected[50]
    cap = directory / "capture"
    raw = read_json(cap / "0052.raw.bin")
    if raw["status"] != "incomplete" or read_json(cap / "0052.capture.json")["status"] != 200:
        raise ValueError("Expected incomplete successful-HTTP response")
    if (cap / "0052.payload.json").read_bytes() != guard._json_bytes(job["context"]["payload"]):
        raise ValueError("Source request differs from reconstructed packet")
    initial = read_json(cap / "0051.accepted.json")["result"]
    hashes = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Linked source artifact")
        if path.is_file():
            hashes[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    bundle = {"job": job, "initial": initial, "initial_packet": initial_job["context"]["packet"]}
    return {"mode": "live", "source_sha256": sha256_json(hashes),
        "source_protocol_sha256": checked["protocol_sha256"], "bundle_sha256": sha256_json(bundle), "bundle": bundle}


def request(value):
    job = value["bundle"]["job"]
    row, context = job["row"], job["context"]
    required = {"sequence": 52, "kind": "judge", "block": "development", "family_id": "HC-MT-MEDSAFE-013",
        "language": "zh-Hans", "provider": "gemini", "model": MODEL, "stage": "update",
        "profile": None, "candidate_model": "MiniMax-M3", "repeat": False}
    if row != required or sha256_json(value["bundle"]) != value["bundle_sha256"]:
        raise ValueError("Source cell or bundle changed")
    original = context["payload"]
    if original["generation_config"]["max_output_tokens"] != 8192:
        raise ValueError("Source cap changed")
    payload = deepcopy(original)
    payload["generation_config"]["max_output_tokens"] = 32768
    restored = deepcopy(payload); restored["generation_config"]["max_output_tokens"] = 8192
    if restored != original:
        raise ValueError("Only output allowance may change")
    expected_initial = score.stage_packet(context["full"], "initial", context["packet"]["level_definitions"])
    if expected_initial != value["bundle"]["initial_packet"]:
        raise ValueError("Initial judgment belongs to another conversation")
    score.validate(value["bundle"]["initial"], expected_initial)
    return payload


def pins(value):
    payload = request(value)
    return {k: value[k] for k in ("source_sha256", "source_protocol_sha256", "bundle_sha256")} | {
        "original_payload_sha256": hashlib.sha256(guard._json_bytes(value["bundle"]["job"]["context"]["payload"])).hexdigest(),
        "supplemental_payload_sha256": hashlib.sha256(guard._json_bytes(payload)).hexdigest()}


def plan(root):
    spec = read_json(root / PLAN)
    fixed = {"version": VERSION, "maximum_attempts": 1, "automatic_retries": 0, "candidate_calls": 0,
        "stop_threshold_usd": "0.25", "hard_ceiling": False, "model": MODEL, "source_directory": SOURCE,
        "old_output_cap": 8192, "new_output_cap": 32768, "thinking_level": "medium"}
    if any(type(spec[k]) is not type(v) or spec[k] != v for k, v in fixed.items()):
        raise ValueError("Supplement scope changed")
    return spec


def verify(root, value, mode):
    if value["mode"] != mode or mode not in {"live", "offline_fixture"}:
        raise ValueError("Source mode differs")
    actual = pins(value)
    if mode == "live" and actual != plan(root)["source_pins"]:
        raise ValueError("Source differs from prospective freeze")


def snapshot(root):
    spec = plan(root)
    paths = (PLAN, "scripts/judge_cap_s49.py", "tests/test_judge_cap_s49.py")
    return {"version": VERSION, "s48_protocol_sha256": prior.audit(root)["protocol_sha256"],
        "files": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
        "source_pins": spec["source_pins"]}


def audit(root):
    current = snapshot(root)
    if current != read_json(root / FREEZE):
        raise ValueError("Supplement differs from frozen inputs")
    return {"protocol_sha256": sha256_json(current), "plan": plan(root), "live_calls": 0}


def manifest(value, protocol, mode):
    return {"version": VERSION, "mode": mode, "protocol_sha256": protocol, "source_pins": pins(value),
        "maximum_attempts": 1, "stop_threshold_usd": "0.25", "resume_allowed": False}


def replay(root, directory, value, protocol, *, threshold=THRESHOLD):
    directory = Path(directory); saved = read_json(directory / "manifest.json")
    verify(root, value, saved["mode"])
    if saved != manifest(value, protocol, saved["mode"]):
        raise ValueError("Manifest changed")
    if saved["mode"] == "live" and (threshold != THRESHOLD or audit(root)["protocol_sha256"] != protocol):
        raise ValueError("Live scope changed")
    cap = directory / "capture"; payload = request(value)
    expected_run = {"mode": saved["mode"], "automatic_retries": 0, "max_attempts": 1,
        "protocol_sha256": protocol, "resume_allowed": False, "costs_are_simulated": saved["mode"] == "offline_fixture"}
    if read_json(cap / "run.json") != expected_run:
        raise ValueError("Capture scope changed")
    allowed = re.compile(r"0001\.(attempt\.json|payload\.json|raw\.bin|capture\.json|accounting\.json|accepted\.json|rejected\.json)")
    if any(p.is_symlink() or not p.is_file() or p.name != "run.json" and not allowed.fullmatch(p.name) for p in cap.iterdir()):
        raise ValueError("Unexpected or repeated capture")
    attempts = int((cap / "0001.attempt.json").exists())
    if not attempts and any(p.name != "run.json" for p in cap.iterdir()):
        raise ValueError("Orphan capture")
    accounts, judgment, raw = [], None, None
    terminal, category, monitored = "not_dispatched_no_resume", None, 0
    if attempts:
        expected_attempt = {"sequence": 1, "provider": "gemini", "model": MODEL, "protocol_sha256": protocol,
            "payload_sha256": hashlib.sha256(guard._json_bytes(payload)).hexdigest(),
            "delivery": "reserved_before_connection", "prospective_cost_bound": None,
            "automatic_retries": 0, "fixture_only": saved["mode"] == "offline_fixture"}
        if read_json(cap / "0001.attempt.json") != expected_attempt:
            raise ValueError("Attempt binding changed")
        if (cap / "0001.payload.json").exists() and (cap / "0001.payload.json").read_bytes() != guard._json_bytes(payload):
            raise ValueError("Payload changed")
        account = prior.previous.captured_account(root, value["bundle"]["job"]["row"], cap)
        accounts.append(account)
        monitored = old.monitoring_delta(account, "gemini")["delta_ticks"]
        if not all((cap / p).exists() for p in ("0001.payload.json", "0001.capture.json", "0001.accounting.json")):
            terminal = "interrupted_unknown_delivery_or_charge"
        else:
            meta = read_json(cap / "0001.capture.json"); raw_path = cap / "0001.raw.bin"
            body = raw_path.read_bytes() if raw_path.exists() else b""
            if (meta["mode"] != saved["mode"] or meta["bytes_saved"] != len(body)
                    or meta["fixture_only"] != (saved["mode"] == "offline_fixture")
                    or meta["body_sha256"] is not None and meta["body_sha256"] != hashlib.sha256(body).hexdigest()
                    or read_json(cap / "0001.accounting.json") != account):
                raise ValueError("Response or accounting binding changed")
            category = meta["category"]
            if category == "accepted":
                raw = capture.strict_json(body)
                judgment = score.decode(raw, "gemini", MODEL, value["bundle"]["job"]["context"]["packet"])
                if (type(meta["status"]) is not int or not 200 <= meta["status"] < 300 or not meta["body_eof"]
                        or read_json(cap / "0001.accepted.json") != {"result": judgment, "raw_sha256": meta["body_sha256"]}
                        or (cap / "0001.rejected.json").exists()):
                    raise ValueError("Acceptance differs from raw response")
            elif read_json(cap / "0001.rejected.json")["category"] != category:
                raise ValueError("Rejection binding changed")
            terminal = ("unknown_charge" if monitored is None else category if judgment is None
                        else "spend_threshold_reached" if monitored >= threshold else "supplement_complete")
    combined = None
    if judgment is not None:
        _, combined = score.combine(value["bundle"]["initial"], judgment, value["bundle"]["job"]["context"]["full"],
                                    {"version": score.VERSION, **score.ARITHMETIC})
    return {"version": VERSION, "protocol_sha256": protocol, "mode": saved["mode"], "source_pins": pins(value),
        "terminal": terminal, "category": category, "attempts": attempts, "maximum_attempts": 1,
        "accepted": judgment is not None, "candidate_calls": 0, "reused_initial_judgments": 1,
        "source_sequence": 52, "candidate_model": "MiniMax-M3", "judge_model": MODEL,
        "family_id": "HC-MT-MEDSAFE-013", "language": "zh-Hans", "new_output_cap": 32768,
        "initial_output_cap": 8192, "supplemental_score": combined,
        "update_statuses": [a["status"] for a in judgment["criterion_assessments"]] if judgment else [],
        "critical_error_ids": [e["error_id"] for e in judgment["critical_errors"]] if judgment else [],
        "observation_decisions": [o["decision"] for o in judgment["dimension_observations"]] if judgment else [],
        "usage": {k: raw.get("usage", {}).get(k) for k in ("total_input_tokens", "total_output_tokens", "total_thought_tokens")} if raw else None,
        "accounting": old.usage.summarize(accounts),
        "monitoring_amount_usd": None if monitored is None else format(Decimal(monitored) / old.TICKS_PER_USD, "f"),
        "stop_threshold_usd": "0.25", "hard_ceiling": False, "automatic_retries": 0,
        "s48_unchanged": True, "s48_complete": False, "scores_pooled": False,
        "clinical_validation": False, "model_rankings_approved": False,
        "interpretation": "Supplement only, mixed initial/update output caps. No causal truncation proof, uniform-cap panel mean, retrospective repair or clinical adjudication."}


def execute(root, directory, value, protocol, credential, connection_factory, mode, *, threshold=THRESHOLD):
    verify(root, value, mode)
    if mode == "live" and (threshold != THRESHOLD or audit(root)["protocol_sha256"] != protocol):
        raise ValueError("Live scope changed")
    directory = Path(directory)
    write_json(directory / "manifest.json", manifest(value, protocol, mode))
    journal = capture.CaptureJournal(root, directory / "capture", 1, protocol, mode)
    try:
        journal.exchange("gemini", request(value),
            lambda raw: score.decode(raw, "gemini", MODEL, value["bundle"]["job"]["context"]["packet"]),
            credential=credential, connection_factory=connection_factory)
    finally:
        credential = ""
        report = replay(root, directory, value, protocol, threshold=threshold)
        write_json(directory / "report.json", report)
    return report


def consume(root, protocol, run_id):
    path = old.prior._private_path(root, "work/s49-consumed-protocols", directory=True, create=True)
    write_json(path / (protocol + ".json"), {"protocol_sha256": protocol, "run_id": run_id, "maximum_attempts": 1})


def run_live(root, run_id, note):
    checked, value = audit(root), source(root); verify(root, value, "live")
    if not isinstance(note, str) or not note.strip() or str(UUID(run_id)) != run_id:
        raise ValueError("Actual approval and canonical UUID required")
    relative = "work/s49-runs/" + run_id
    if subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=root, capture_output=True).returncode:
        raise ValueError("Private output must be ignored")
    parent = old.prior._private_path(root, "work/s49-runs", directory=True, create=True)
    if (parent / run_id).exists():
        raise ValueError("Cannot reuse a run")
    consume(root, checked["protocol_sha256"], run_id)
    directory = parent / run_id; directory.mkdir(mode=0o700)
    write_json(directory / "authorization.json", {"authorization_evidence": note,
        "issued_at": datetime.now(timezone.utc).isoformat(), "protocol_sha256": checked["protocol_sha256"],
        "maximum_attempts": 1, "stop_threshold_usd": "0.25", "last_request_overrun_accepted": True,
        "candidate_calls": 0, "no_old_allowance_reused": True})
    key = ""
    try:
        key = old.prior.read_setting(root / ".env.local", "GEMINI_API_KEY", secret=True)
        return execute(root, directory, value, checked["protocol_sha256"], key, old.prior.create_tls_connection, "live")
    finally:
        key = ""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("source", "snapshot", "audit", "run", "report"))
    p.add_argument("--run-id"); p.add_argument("--authorization-note", default=""); p.add_argument("--directory")
    args = p.parse_args(); root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "source": result = pins(source(root))
        elif args.command == "snapshot": result = snapshot(root)
        elif args.command == "audit": result = audit(root)
        elif args.command == "run": result = run_live(root, args.run_id, args.authorization_note)
        else:
            checked, value = audit(root), source(root)
            directory = old.prior._private_path(root, args.directory, directory=True)
            result = replay(root, directory, value, checked["protocol_sha256"])
            if result != read_json(directory / "report.json"):
                raise ValueError("Final report differs from replay")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "run" and not result["accepted"]:
            p.exit(1, "S49 supplement rejected; no retry.\n")
    except Exception:
        p.exit(2, "S49 blocked/stopped. Captures stay private; no automatic retry.\n")


if __name__ == "__main__":
    main()
