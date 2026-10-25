"""Two-call, separately authorized Grok diagnostic; no benchmark resume.

Captures allowlisted correlation headers and TLS observations privately. These
observations aid tracing; they do not prove which upstream component denied a
request. Never disable TLS verification, change endpoints or repair a payload.
"""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import UUID

from benchmark import live_s41 as live, transport_s41 as capture, usage_s39 as usage
from benchmark import workflow_s38 as workflow
from benchmark.provenance import sha256_json

VERSION = "s43-grok-two-call-trace-v1"
FREEZE = "config/grok_trace_s43_frozen_v1.json"
THRESHOLD = 10_000_000_000  # $1; a post-request stop threshold, NOT a hard ceiling.
HEADERS = ("x-request-id", "request-id", "x-xai-request-id", "x-correlation-id",
           "cf-ray", "traceparent", "server", "date", "content-type", "content-length", "retry-after")
ORIGINAL_HASH = "4308985e8ec686f97acc7ad2d2281d230fb9015d3cfb62ff330510252f8bf64d"


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def packets(root):
    row = workflow.schedule(root)[9]
    if (row["model"], row["family_id"], row["language"], row["stage"]) != (
            "grok-4.7", "HC-MT-MEDSAFE-019", "en", "initial"):
        raise ValueError("Original rejected row drift")
    context = workflow.request_context(root, row, workflow.families(root), workflow.score.controls(root), {})
    if hashlib.sha256(live.guard._json_bytes(context["payload"])).hexdigest() != ORIGINAL_HASH:
        raise ValueError("Original rejected payload changed")
    neutral = {"model": "grok-4.7", "input": [{"role": "user", "content": "Reply with exactly DIAGNOSTIC_OK."}],
        "store": False, "max_output_tokens": 8192, "temperature": 0.7, "top_p": 0.95,
        "reasoning": {"effort": "high"}}
    return [("neutral", neutral, None), ("unchanged_rejected_request", context["payload"], context["packet"])]


def snapshot(root):
    base = live.audit(root)["protocol_sha256"]
    paths = ["scripts/grok_trace_s43.py", "tests/test_grok_trace_s43.py"]
    return {"version": VERSION, "s41_protocol_sha256": base, "maximum_attempts": 2,
        "threshold_ticks": THRESHOLD, "hard_ceiling": False, "automatic_retries": 0,
        "payload_sha256": [hashlib.sha256(live.guard._json_bytes(p)).hexdigest() for _, p, _ in packets(root)],
        "files": {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}}


def audit(root):
    current = snapshot(root)
    if current != live.load_json(root/FREEZE):
        raise live.guard.AdmissionBlocked("S43 frozen diagnostic changed")
    return sha256_json(current)


def safe_headers(response, credential):
    values, omitted = {}, []
    for name in HEADERS:
        value = response.getheader(name)
        if value is None:
            continue
        if (not isinstance(value, str) or len(value) > 256 or not value.isascii()
                or any(ord(c) < 32 or ord(c) == 127 for c in value) or credential and credential in value):
            omitted.append(name)
        else:
            values[name] = value
    return {"allowlisted_response_headers": values, "omitted_allowlisted_fields": omitted,
            "other_headers_retained": False}


class ObservedConnection:
    def __init__(self, connection, directory, sequence, host, credential):
        self.connection, self.directory = connection, Path(directory)
        self.sequence, self.host, self.credential = sequence, host, credential

    def record(self, event, value):
        live.guard._write_exclusive(self.directory/f"{self.sequence:04d}.{event}.json",
            live.guard._json_bytes({"observed_at_utc": now(), "host": self.host, **value}))

    def request(self, method, path, body, headers):
        if self.host != "api.x.ai" or method != "POST" or path != "/v1/responses":
            raise ValueError("Unexpected diagnostic destination")
        self.record("connect-start", {"method": method, "path": path,
            "payload_sha256": hashlib.sha256(body).hexdigest(), "request_headers_retained": False})
        self.connection.connect()
        sock = self.connection.sock
        cert = sock.getpeercert()
        self.record("tls", {"tls_version": sock.version(), "peer_address": sock.getpeername(),
            "certificate_subject": cert.get("subject"), "certificate_issuer": cert.get("issuer"),
            "certificate_dns_names": [v for k,v in cert.get("subjectAltName", []) if k == "DNS"],
            "certificate_sha256": hashlib.sha256(sock.getpeercert(binary_form=True)).hexdigest(),
            "verification": "default_certificate_and_hostname_checks_not_disabled"})
        self.record("send-start", {"method": method, "path": path})
        self.connection.request(method, path, body=body, headers=headers)

    def getresponse(self):
        response = self.connection.getresponse()
        try:
            self.record("response-headers", {"status": response.status, **safe_headers(response, self.credential)})
        except BaseException:
            response.close()
            raise
        return response

    def close(self):
        self.credential = ""
        self.connection.close()


def validate_receipt(root, path):
    protocol = audit(root)
    path = Path(path).absolute()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        raise live.guard.AdmissionBlocked("Receipt must be local") from None
    path = live._private_path(root, relative)
    if path.parent != root/"work/s43-authorizations" or path.stat().st_size > 16384:
        raise live.guard.AdmissionBlocked("Invalid receipt location/size")
    receipt = capture.strict_json(path.read_bytes())
    fixed = {"version": VERSION, "protocol_sha256": protocol, "maximum_attempts": 2,
        "stop_threshold_usd": "1.00", "hard_ceiling": False, "overshoot_accepted": True,
        "paid_calls_approved": True, "data_export_approved": True, "benchmark_restart_approved": False}
    additional = {"approval_id", "run_id", "issued_at", "expires_at", "authorization_text", "authorization_evidence"}
    if not isinstance(receipt, dict) or set(receipt) != set(fixed)|additional:
        raise live.guard.AdmissionBlocked("Exact diagnostic receipt required")
    if any(receipt[k] != v or type(receipt[k]) is not type(v) for k,v in fixed.items()):
        raise live.guard.AdmissionBlocked("Diagnostic scope not explicitly approved")
    for key in ("approval_id", "run_id"):
        if not isinstance(receipt[key], str) or str(UUID(receipt[key])) != receipt[key]:
            raise ValueError("Canonical UUID required")
    if path.name != receipt["approval_id"]+".json":
        raise ValueError("Receipt filename mismatch")
    issued, expires = live._utc(receipt["issued_at"]), live._utc(receipt["expires_at"])
    if not issued <= datetime.now(timezone.utc) < expires or expires-issued > timedelta(hours=24):
        raise live.guard.AdmissionBlocked("Expired or invalid diagnostic authorization")
    if any(not isinstance(receipt[k], str) or not receipt[k].strip() for k in ("authorization_text", "authorization_evidence")):
        raise ValueError("Actual authorization evidence required")
    for relative in ("work/s43-runs/"+receipt["run_id"], "work/s43-authorizations/consumed/"+receipt["approval_id"]+".json"):
        if live._private_path(root, relative).exists():
            raise live.guard.AdmissionBlocked("Used authorization or output; no resume")
    for relative in (path.relative_to(root).as_posix(), "work/s43-runs/"+receipt["run_id"]):
        if live.subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=root, capture_output=True).returncode:
            raise live.guard.AdmissionBlocked("Private files must be ignored")
    return receipt


def execute(root, directory, protocol, credential, *, connection_factory, expires_at, mode):
    """Called after one-shot admission; injection seam supports offline tests."""
    trace_dir = directory/"trace"; trace_dir.mkdir(mode=0o700)
    journal = capture.CaptureJournal(root, directory/"capture", 2, protocol, mode)
    results, total, terminal = [], 0, None
    try:
        for sequence, (name, payload, packet) in enumerate(packets(root), 1):
            if datetime.now(timezone.utc) >= live._utc(expires_at):
                terminal = "approval_expired"; break
            audit(root)
            if total >= THRESHOLD:
                terminal = "spend_threshold_reached"; break
            def factory(host, *, timeout):
                return ObservedConnection(connection_factory(host, timeout=timeout), trace_dir, sequence, host, credential)
            def validate(raw):
                if packet is None:
                    return workflow.decode_candidate(raw, "grok", "grok-4.7")
                return workflow.score.decode(raw, "grok", "grok-4.7", packet)
            outcome = journal.exchange("grok", payload, validate, credential=credential, connection_factory=factory)
            charge = outcome["accounting"]["provider_billed_usd_ticks"]
            if type(charge) is int and charge >= 0:
                total += charge
            terminal = ("unknown_charge" if charge is None else outcome["category"] if not outcome["accepted"]
                        else "spend_threshold_reached" if total >= THRESHOLD else None)
            result = {"sequence": sequence, "name": name, "accepted": outcome["accepted"],
                "category": outcome["category"], "reported_charge_ticks": charge,
                "reported_total_ticks": total, "terminal": terminal}
            live.guard._write_exclusive(directory/f"{sequence:04d}.result.json", live.guard._json_bytes(result))
            results.append(result)
            print(json.dumps(result), flush=True)
            if terminal:
                break
        terminal = terminal or "diagnostic_complete"
    except BaseException:
        terminal = "local_failure_or_interruption"
        raise
    finally:
        credential = ""
        accounting = usage.summarize(journal.accounts)
        known_ticks = accounting["provider_reported_subtotal_usd_ticks"]
        summary = {"version": VERSION, "protocol_sha256": protocol, "terminal": terminal,
            "mode": mode, "attempts_reserved": journal.index, "results": results, "capture_accounting": accounting,
            "attempts_without_accounting_record": journal.index-len(journal.accounts),
            "reported_known_total_usd": format(Decimal(known_ticks)/10_000_000_000, "f"),
            "hard_ceiling": False, "benchmark_resumed": False, "scores_added_to_benchmark": 0}
        live.guard._write_exclusive(directory/"report.json", live.guard._json_bytes(summary))
    return summary


def run(root, approval_file):
    receipt = validate_receipt(root, approval_file)
    consumed = live._private_path(root, "work/s43-authorizations/consumed", directory=True, create=True)
    live.guard._write_exclusive(consumed/(receipt["approval_id"]+".json"), live.guard._json_bytes({
        "receipt_sha256": sha256_json(receipt), "consumed_at": now(), "run_id": receipt["run_id"]}))
    parent = live._private_path(root, "work/s43-runs", directory=True, create=True)
    directory = parent/receipt["run_id"]; directory.mkdir(mode=0o700)
    live.guard._write_exclusive(directory/"approval.json", live.guard._json_bytes(receipt))
    key = ""
    try:
        try:
            key = live.read_setting(root/".env.local", "GROK_API_KEY", secret=True)
        except BaseException:
            live.guard._write_exclusive(directory/"report.json", live.guard._json_bytes({
                "version": VERSION, "protocol_sha256": receipt["protocol_sha256"], "mode": "live",
                "terminal": "credential_load_failure", "attempts_reserved": 0,
                "benchmark_resumed": False, "scores_added_to_benchmark": 0,
                "exception_text_retained": False, "authorization_consumed": True}))
            raise
        return execute(root, directory, receipt["protocol_sha256"], key,
            connection_factory=live.create_tls_connection, expires_at=receipt["expires_at"], mode="live")
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
            parser.exit(0 if result["terminal"] == "diagnostic_complete" else 1)
        else:
            print(json.dumps({"protocol_sha256": audit(root), "maximum_attempts": 2,
                "stop_threshold_usd": "1.00", "hard_ceiling": False, "approved": False}, indent=2))
    except Exception:
        parser.exit(2, "S43 blocked/stopped; inspect private journals. No automatic retry.\n")
