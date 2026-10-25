"""One approved Grok diagnostic: omit only max_output_tokens; never resume a run."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import UUID

from scripts import grok_trace_s43 as trace

live, capture, guard = trace.live, trace.capture, trace.live.guard
VERSION = "s44-single-output-cap-diagnostic-v1"
FREEZE = "config/grok_output_cap_s44_frozen_v1.json"


def packet(root):
    _, original, context = trace.packets(root)[1]
    payload = deepcopy(original)
    if payload.pop("max_output_tokens") != 8192:
        raise ValueError("Unexpected original output cap")
    if {**payload, "max_output_tokens": 8192} != original:
        raise ValueError("Only output cap may change")
    return payload, context


def snapshot(root):
    return {"version": VERSION, "s43_protocol_sha256": trace.audit(root),
        "maximum_attempts": 1, "automatic_retries": 0, "stop_threshold_usd": "1.00",
        "hard_ceiling": False, "only_change": "omit_max_output_tokens",
        "payload_sha256": hashlib.sha256(guard._json_bytes(packet(root)[0])).hexdigest(),
        "files": {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in
            ("scripts/grok_output_cap_s44.py", "tests/test_grok_output_cap_s44.py")}}


def audit(root):
    current = snapshot(root)
    if current != live.load_json(root/FREEZE):
        raise guard.AdmissionBlocked("Diagnostic differs from frozen scope")
    return trace.sha256_json(current)


def validate(root, path):
    protocol = audit(root)
    path = Path(path).absolute()
    path = live._private_path(root, path.relative_to(root).as_posix())
    if path.parent != root/"work/s44-authorizations" or path.stat().st_size > 16384:
        raise guard.AdmissionBlocked("Invalid private receipt location/size")
    receipt = capture.strict_json(path.read_bytes())
    fixed = {"version": VERSION, "protocol_sha256": protocol, "maximum_attempts": 1,
        "only_change": "omit_max_output_tokens", "stop_threshold_usd": "1.00",
        "hard_ceiling": False, "overshoot_accepted": True, "paid_calls_approved": True,
        "data_export_approved": True, "benchmark_restart_approved": False,
        "owner_reports_account_limit_set": False}
    extra = {"approval_id", "run_id", "issued_at", "expires_at", "authorization_text", "authorization_evidence"}
    if not isinstance(receipt, dict) or set(receipt) != set(fixed)|extra:
        raise guard.AdmissionBlocked("Exact receipt required")
    if any(type(receipt[k]) is not type(v) or receipt[k] != v for k,v in fixed.items()):
        raise guard.AdmissionBlocked("Unapproved scope")
    for k in ("approval_id", "run_id"):
        if not isinstance(receipt[k], str) or str(UUID(receipt[k])) != receipt[k]:
            raise ValueError("Canonical UUID required")
    if path.name != receipt["approval_id"]+".json":
        raise ValueError("Receipt filename mismatch")
    issued, expires = live._utc(receipt["issued_at"]), live._utc(receipt["expires_at"])
    if not issued <= datetime.now(timezone.utc) < expires or expires-issued > timedelta(hours=24):
        raise guard.AdmissionBlocked("Invalid approval window")
    for k in ("authorization_text", "authorization_evidence"):
        if not isinstance(receipt[k], str) or not receipt[k].strip():
            raise ValueError("Actual authorization evidence required")
    output = "work/s44-runs/"+receipt["run_id"]
    for p in (output, "work/s44-authorizations/consumed/"+path.name):
        if live._private_path(root, p).exists():
            raise guard.AdmissionBlocked("Consumed or existing output; no resume")
    for p in (output, path.relative_to(root).as_posix()):
        if live.subprocess.run(["git", "check-ignore", "-q", "--", p], cwd=root, capture_output=True).returncode:
            raise guard.AdmissionBlocked("Private artifacts must be ignored")
    return receipt


def execute(root, directory, protocol, credential, *, expires_at, connection_factory, mode):
    trace_dir = directory/"trace"; trace_dir.mkdir(mode=0o700)
    journal = capture.CaptureJournal(root, directory/"capture", 1, protocol, mode)
    terminal, accepted, category = "local_failure_or_interruption", False, None
    try:
        if audit(root) != protocol or datetime.now(timezone.utc) >= live._utc(expires_at):
            raise guard.AdmissionBlocked("Protocol changed or approval expired")
        payload, context = packet(root)
        def factory(host, *, timeout):
            return trace.ObservedConnection(connection_factory(host, timeout=timeout), trace_dir, 1, host, credential)
        result = journal.exchange("grok", payload,
            lambda raw: trace.workflow.score.decode(raw, "grok", "grok-4.7", context),
            credential=credential, connection_factory=factory)
        accepted, category = result["accepted"], result["category"]
        charge = result["accounting"]["provider_billed_usd_ticks"]
        terminal = ("unknown_charge" if charge is None else category if not accepted
            else "spend_threshold_reached" if charge >= trace.THRESHOLD else "diagnostic_complete")
    finally:
        credential = ""
        accounting = trace.usage.summarize(journal.accounts)
        summary = {"version": VERSION, "protocol_sha256": protocol, "mode": mode,
            "terminal": terminal, "accepted": accepted, "category": category,
            "attempts_reserved": journal.index, "attempts_without_accounting_record": journal.index-len(journal.accounts),
            "capture_accounting": accounting, "reported_known_subtotal_usd":
                format(Decimal(accounting["provider_reported_subtotal_usd_ticks"])/10_000_000_000, "f"),
            "maximum_attempts": 1, "automatic_retries": 0, "hard_ceiling": False,
            "only_change": "omit_max_output_tokens", "benchmark_resumed": False, "scores_added_to_benchmark": 0}
        guard._write_exclusive(directory/"report.json", guard._json_bytes(summary))
    return summary


def run(root, approval_file):
    receipt = validate(root, approval_file)
    consumed = live._private_path(root, "work/s44-authorizations/consumed", directory=True, create=True)
    guard._write_exclusive(consumed/(receipt["approval_id"]+".json"), guard._json_bytes({
        "receipt_sha256": trace.sha256_json(receipt), "consumed_at": trace.now(), "run_id": receipt["run_id"]}))
    parent = live._private_path(root, "work/s44-runs", directory=True, create=True)
    directory = parent/receipt["run_id"]; directory.mkdir(mode=0o700)
    guard._write_exclusive(directory/"approval.json", guard._json_bytes(receipt))
    key = ""
    try:
        try:
            key = live.read_setting(root/".env.local", "GROK_API_KEY", secret=True)
        except BaseException:
            guard._write_exclusive(directory/"report.json", guard._json_bytes({"version": VERSION,
                "terminal": "credential_load_failure", "attempts_reserved": 0,
                "authorization_consumed": True, "exception_text_retained": False}))
            raise
        return execute(root, directory, receipt["protocol_sha256"], key, expires_at=receipt["expires_at"],
            connection_factory=live.create_tls_connection, mode="live")
    finally:
        key = ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-file", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.approval_file:
            result = run(root, args.approval_file)
            print(json.dumps(result), flush=True)
            parser.exit(0 if result["terminal"] == "diagnostic_complete" else 1)
        else:
            print(json.dumps({"protocol_sha256": audit(root), "maximum_attempts": 1,
                "only_change": "omit_max_output_tokens", "calls_in_this_audit": 0}, indent=2))
    except Exception:
        parser.exit(2, "S44 blocked/stopped; inspect private capture. No automatic retry.\n")
