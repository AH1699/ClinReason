"""One-shot, explicitly authorized first-phase runner. `plan` never reads keys.

A local receipt records an operator's verified human authorization; it is not a
cryptographic proof of consent. No command here creates an approved receipt.
Historical S26–S40 runners, policies and snapshots remain unchanged.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from http.client import HTTPSConnection
import json
from pathlib import Path
import ssl
import stat
import subprocess
import threading
from uuid import UUID

from . import run_guard_s37 as guard, spending_s40, usage_s39 as usage, workflow_s38 as workflow
from . import spending_s41, transport_s41 as capture
from .config import load_json
from .local_settings import read_setting
from .provenance import sha256_json

POLICY = capture.POLICY
FREEZE = "config/live_s41_frozen_v1.json"
PROPOSAL = "config/first_phase_s41_proposal_v1.json"
VERSION = "s41-first-phase-live-v1"
KEY_NAMES = {"gemini": "GEMINI_API_KEY", "grok": "GROK_API_KEY", "minimax": "MINIMAX_API_KEY"}


def snapshot(root):
    paths = {str(p.relative_to(root)) for p in (root / "benchmark").glob("*.py")}
    paths.update({POLICY, spending_s40.FREEZE, ".gitignore", "tests/test_live_s41.py",
                  "tests/test_transport_s41.py", "tests/test_spending_s41.py"})
    return {"version": VERSION, "files": {p: hashlib.sha256((root/p).read_bytes()).hexdigest()
            for p in sorted(paths)}, "schedule_sha256": sha256_json(workflow.schedule(root)),
            "historical_workflow_sha256": sha256_json(workflow.snapshot(root))}


def proposal(root):
    scope = spending_s40.approval_scope(root)
    scope.update(version=VERSION, status="ready_for_explicit_authorization_not_approved",
                 protocol_sha256=sha256_json(snapshot(root)),
                 policy_sha256=sha256_json(load_json(root/POLICY)),
                 production_connector="verified_TLS_fixed_hosts_no_redirects_or_retries",
                 authorization="one_run_one_receipt_consumed_before_keys_or_network",
                 conversation_mode="visible_text_history_only_not_provider_native_reasoning_continuation",
                 generation_settings="S38 unchanged; Gemini medium/provider sampling defaults; Grok high/0.7/0.95; MiniMax adaptive/M3.1 max/fixed 1/0.95",
                 output_limits="8192; Gemini thought+answer, Grok visible-only, MiniMax generated completion; not equal compute",
                 provider_retention="store=false for Gemini/Grok; not a guarantee of zero provider retention; MiniMax account policy applies",
                 truncation="technical_stop_not_clinical_zero",
                 approval_template="docs/S41_LIVE_RUN_2026-10-24_EN.md")
    return scope


def audit(root):
    spending_s40.audit(root)
    if snapshot(root) != load_json(root/FREEZE) or proposal(root) != load_json(root/PROPOSAL):
        raise guard.AdmissionBlocked("S41 protocol or proposal differs from frozen bytes")
    return {"version": VERSION, "protocol_sha256": sha256_json(snapshot(root)),
            "production_capable": True, "live_authorized": False, "calls_in_this_audit": 0}


def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise guard.AdmissionBlocked("Approval timestamps must be UTC ending in Z")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _private_path(root, relative, *, directory=False, create=False):
    """Reject existing symlinks and group/other access inside the ignored work tree.

    Assumes a trusted local OS user; not a defense against a hostile same-user
    process swapping paths while a run is in progress.
    """
    parts = Path(relative).parts
    if not parts or parts[0] != "work" or any(p in {"..", "."} for p in parts):
        raise guard.AdmissionBlocked("Only local work paths are allowed")
    path = root
    for i, part in enumerate(parts):
        path = path/part
        if path.is_symlink():
            raise guard.AdmissionBlocked("Symlink in private run path")
        is_dir = i < len(parts)-1 or directory
        if create and is_dir and not path.exists():
            path.mkdir(mode=0o700)
            guard._sync_dir(path.parent)
        if path.exists():
            info = path.stat()
            if is_dir and not path.is_dir() or not is_dir and not path.is_file():
                raise guard.AdmissionBlocked("Unexpected private path type")
            # Existing work root may be shared; the dedicated S41 paths must not be.
            if i > 0 and stat.S_IMODE(info.st_mode) & 0o077:
                raise guard.AdmissionBlocked("S41 files/directories require private permissions")
    return path


def validate_approval(root, approval_file, now=None):
    now = now or datetime.now(timezone.utc)
    expected = audit(root)["protocol_sha256"]
    path = Path(approval_file).absolute()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        raise guard.AdmissionBlocked("Approval must be local to this checkout") from None
    path = _private_path(root, relative)
    if path.parent != root/"work/s41-authorizations" or path.stat().st_size > 16384:
        raise guard.AdmissionBlocked("Wrong approval location or size")
    receipt = capture.strict_json(path.read_bytes())
    fields = {"version", "approval_id", "run_id", "protocol_sha256", "phase", "maximum_attempts",
              "stop_threshold_usd", "hard_ceiling", "overshoot_accepted", "data_export_approved",
              "paid_calls_approved", "confirmation_authorized", "issued_at", "expires_at",
              "output_directory", "authorization_text", "authorization_evidence"}
    if not isinstance(receipt, dict) or set(receipt) != fields:
        raise guard.AdmissionBlocked("Approval fields must match the documented schema")
    fixed = {"version": VERSION, "protocol_sha256": expected, "phase": "first", "maximum_attempts": 816,
             "stop_threshold_usd": "55.00", "hard_ceiling": False, "overshoot_accepted": True,
             "data_export_approved": True, "paid_calls_approved": True, "confirmation_authorized": False}
    if any(receipt[k] != v or type(receipt[k]) is not type(v) for k, v in fixed.items()):
        raise guard.AdmissionBlocked("Explicit authorization for this exact scope is required")
    for name in ("approval_id", "run_id"):
        value = receipt[name]
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise guard.AdmissionBlocked("Canonical UUID required")
    if path.name != receipt["approval_id"] + ".json":
        raise guard.AdmissionBlocked("Receipt name must match approval ID")
    issued, expires = _utc(receipt["issued_at"]), _utc(receipt["expires_at"])
    if not issued <= now < expires or expires-issued > timedelta(hours=24):
        raise guard.AdmissionBlocked("Approval expired, future-dated or too long-lived")
    for name in ("authorization_text", "authorization_evidence"):
        if not isinstance(receipt[name], str) or not receipt[name].strip():
            raise guard.AdmissionBlocked("Record actual human authorization and its source")
    expected_output = "work/s41-runs/" + receipt["run_id"]
    if receipt["output_directory"] != expected_output:
        raise guard.AdmissionBlocked("Output must be the run's fresh private directory")
    if _private_path(root, expected_output).exists():
        raise guard.AdmissionBlocked("Output already exists; resume is prohibited")
    consumed = _private_path(root, "work/s41-authorizations/consumed/"+receipt["approval_id"]+".json")
    if consumed.exists():
        raise guard.AdmissionBlocked("Approval already consumed; no budget reset or retry")
    for private in (relative, expected_output):
        ignored = subprocess.run(["git", "check-ignore", "-q", "--", private],
                                 cwd=root, capture_output=True, check=False)
        if ignored.returncode != 0:
            raise guard.AdmissionBlocked("Local approval/output must be Git ignored")
    return receipt


def consume_approval(root, receipt):
    directory = _private_path(root, "work/s41-authorizations/consumed", directory=True, create=True)
    # O_EXCL provides the cross-process one-shot admission point.
    guard._write_exclusive(directory/(receipt["approval_id"]+".json"), guard._json_bytes({
        "approval_id": receipt["approval_id"], "run_id": receipt["run_id"],
        "protocol_sha256": receipt["protocol_sha256"], "receipt_sha256": sha256_json(receipt),
        "consumed_at": datetime.now(timezone.utc).isoformat(), "resume_allowed": False}))


def load_credentials(root):
    return {provider: read_setting(root/".env.local", name, secret=True) for provider, name in KEY_NAMES.items()}


def create_tls_connection(host, *, timeout):
    if host not in {v[0] for v in capture.ENDPOINTS.values()}:
        raise guard.AdmissionBlocked("Unapproved API host")
    return HTTPSConnection(host, timeout=timeout, context=ssl.create_default_context())


class Session:
    """First-phase orchestration without S38's artificial fixture-cost journal."""
    def __init__(self, root, directory, protocol, *, mode):
        self.root, self.directory, self.mode = root, Path(directory), mode
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        self.rows = workflow.schedule(root)
        self.catalog, self.controls = workflow.families(root), workflow.score.controls(root)
        self.answers, self.judgments, self.contexts = {}, {}, {}
        self.index, self.terminal, self.pending = 0, None, None
        self.capture = capture.CaptureJournal(root, self.directory/"capture", 816, protocol, mode)
        self.monitor = spending_s41.StopThreshold(root, self.directory/"spending", mode=mode)
        self.lock = threading.Lock()

    def step(self, credentials, *, connection_factory):
        with self.lock:
            if self.terminal:
                return None
            if not self.monitor.can_dispatch():
                self.terminal = self.monitor.stop_reason or "schedule_complete"
                return None
            if self.index == 72 and not workflow.control_gate(self.root, self.rows, self.judgments, self.contexts)["pass"]:
                self.terminal = "control_gate_failed"
                return None
            row = self.rows[self.index]
            result = None
            try:
                context = workflow.request_context(self.root, row, self.catalog, self.controls, self.answers)
                self.contexts[row["sequence"]], self.pending = deepcopy(context), row
                self.monitor.begin(row, context["payload"])
                def validate(raw):
                    if row["kind"] == "candidate":
                        return workflow.decode_candidate(raw, row["provider"], row["model"])
                    return workflow.score.decode(raw, row["provider"], row["model"], context["packet"])
                result = self.capture.exchange(row["provider"], context["payload"], validate,
                    credential=credentials[row["provider"]], connection_factory=connection_factory)
                self.index += 1
                if result["accepted"]:
                    if row["kind"] == "candidate":
                        self.answers[workflow.answer_key(row)] = result["result"]
                    else:
                        self.judgments[workflow.judgment_key(row)] = result["result"]
                settled = self.monitor.settle(result["accounting"], result["accepted"])
                self.pending = None
                self.terminal = (result["category"] if not result["accepted"] else settled["stop_reason"])
                if not self.terminal and self.index == len(self.rows):
                    self.terminal = "schedule_complete"
                guard._write_exclusive(self.directory/f'{self.index:04d}.progress.json', guard._json_bytes({
                    "mode": self.mode, "sequence": self.index, "terminal": self.terminal,
                    "accepted": result["accepted"], "spending": self.monitor.report()}))
                return {"sequence": self.index, "accepted": result["accepted"], "terminal": self.terminal}
            except BaseException:
                self.terminal = "local_failure_or_interruption"
                if self.monitor.pending is not None and self.monitor.stop_reason is None:
                    account_path = self.capture.directory/f'{row["sequence"]:04d}.accounting.json'
                    account = usage.account(None, {"model": row["model"]})
                    if account_path.exists():
                        try:
                            account = capture.strict_json(account_path.read_bytes())
                        except (ValueError, OSError):
                            pass
                    self.monitor.settle(account, False)
                raise

    def score_rows(self):
        # Reuse frozen, tested arithmetic only; replace its fixture metadata.
        records = workflow.OfflineSession.score_rows(self)
        for record in records:
            record["simulation_only"] = self.mode == "offline_fixture"
        return records

    def report(self):
        plan, records = workflow.design(self.root), self.score_rows()
        return {"version": VERSION, "mode": self.mode, "terminal": self.terminal,
            "complete": self.index == len(self.rows) and self.terminal == "schedule_complete",
            "attempts_reserved": self.monitor.attempts, "completed_exchanges": self.index,
            "clinical_validation": False, "model_rankings_approved": False,
            "spending": self.monitor.report(), "capture_accounting": usage.summarize(self.capture.accounts),
            "control_gate": workflow.control_gate(self.root, self.rows, self.judgments, self.contexts),
            "stability_diagnostics": workflow.stability_diagnostics(self.root, self.rows, self.judgments, self.contexts, records),
            "separate_judge_reports": {j["model"]: workflow.mix.summarize(
                [r for r in records if r["judge"] == j["model"] and not r["repeat"]],
                [c["model"] for c in plan["candidates"]], [f["family_id"] for f in plan["development"]])
                for j in plan["judges"]}, "score_records": records}


def run_live(root, approval_file):
    root = Path(root).resolve()
    receipt = validate_approval(root, approval_file)
    consume_approval(root, receipt)  # Even a subsequent credential error consumes it.
    parent = _private_path(root, "work/s41-runs", directory=True, create=True)
    session = Session(root, parent/receipt["run_id"], receipt["protocol_sha256"], mode="live")
    guard._write_exclusive(session.directory/"approval.json", guard._json_bytes(receipt))
    credentials = {}
    try:
        credentials = load_credentials(root)
        while session.terminal is None:
            if datetime.now(timezone.utc) >= _utc(receipt["expires_at"]):
                session.terminal = "approval_expired"
                break
            audit(root)  # Refuse source/config drift before every new dispatch.
            progress = session.step(credentials, connection_factory=create_tls_connection)
            if progress:
                print(json.dumps({**progress, "monitoring_amount_usd": session.monitor.report()["monitoring_amount_usd"]}), flush=True)
    except BaseException:
        session.terminal = "local_failure_or_interruption"
        raise guard.AdmissionBlocked("Run stopped; inspect private journals. No automatic retry.") from None
    finally:
        credentials.clear()
        guard._write_exclusive(session.directory/"report.json", guard._json_bytes(session.report()))
    return session.report()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    commands.add_parser("audit")
    live = commands.add_parser("run")
    live.add_argument("--approval-file", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "run":
            report = run_live(root, args.approval_file)
            print(json.dumps({"terminal": report["terminal"], "complete": report["complete"]}))
            if not report["complete"]:
                parser.exit(1, "S41 stopped before completion; retained attempts must not be retried automatically.\n")
        else:
            result = audit(root)
            print(json.dumps(proposal(root) if args.command == "plan" else result, ensure_ascii=False, indent=2))
    except Exception:
        parser.exit(2, "S41 blocked or stopped; no automatic retry. Check protocol and private journals.\n")


if __name__ == "__main__":
    main()
