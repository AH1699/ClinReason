"""Approval-bound mixed-panel runner. The proposal alone refuses paid execution.

Read-only snapshot/preflight do not load credentials. Run requires separately
prepared pricing evidence, a frozen protocol and a fresh explicit owner approval.
The approval journal is a trusted-local-operator record, not an identity service.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import threading
from uuid import UUID

from scripts import mixed_transport_s53 as rehearsal
from scripts.minimax_accounting_s46 import PRIORITY_RATES

journal, panel, capture = rehearsal.journal, rehearsal.panel, rehearsal.capture
guard, policy = panel.guard, rehearsal.policy
VERSION = "s54-mixed-live-v1"
PLAN = "config/mixed_live_s54_v1.json"
PRICING_URLS = {"gemini": "https://ai.google.dev/gemini-api/docs/pricing",
                "minimax": "https://platform.minimax.io/docs/pricing/overview"}


def stamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp ending in Z required")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def rates(root):
    models = set(panel.plan(root)["candidate_models"] + panel.plan(root)["judge_models"])
    values = {s["model"]: s for s in panel.workflow.design(root)["candidates"]
              if s["model"] in models}
    return {"models": values, "m3_default_echo_monitoring":
            deepcopy(PRIORITY_RATES),
            "input_token_scope_max": 16000, "cache_discount_used": False,
            "invoice_or_hard_cap": False}


def snapshot(root):
    root = Path(root)
    return {"version": VERSION, "s53": rehearsal.snapshot(root), "rates": rates(root),
        "files": {p: journal.digest((root / p).read_bytes()) for p in
                  (PLAN, "scripts/mixed_live_s54.py", "tests/test_mixed_live_s54.py")}}


def validate_authorization(root, freeze, approval, now=None):
    """Pure admission check. A generic go-ahead or an old budget is insufficient."""
    now = now or datetime.now(timezone.utc)
    spec = journal.read(Path(root) / PLAN)
    if (set(spec) != {"version", "status", "maximum_attempts", "stop_threshold_usd",
            "hard_ceiling", "last_request_overrun_possible", "automatic_retries",
            "resume_allowed", "pricing_verification", "reporting_policy"}
            or spec["version"] != VERSION or spec["status"] != "ready_for_explicit_approval"
            or type(spec["maximum_attempts"]) is not int or spec["maximum_attempts"] != 452
            or spec["hard_ceiling"] is not False or spec["last_request_overrun_possible"] is not True
            or type(spec["automatic_retries"]) is not int or spec["automatic_retries"] != 0
            or spec["resume_allowed"] is not False or spec["reporting_policy"] != policy.PATH):
        raise ValueError("Live plan remains disabled or its scope differs")
    amount = spec["stop_threshold_usd"]
    if (not isinstance(amount, str) or not Decimal(amount).is_finite()
            or Decimal(amount) <= 0 or Decimal(amount).as_tuple().exponent < -2):
        raise ValueError("Explicit positive USD stop threshold required")
    price = spec["pricing_verification"]
    if (not isinstance(price, dict) or set(price) != {"verified_at", "verified_by", "sources", "rates", "evidence_note"}
            or price["sources"] != PRICING_URLS or price["rates"] != rates(root)
            or not isinstance(price["verified_by"], str) or not price["verified_by"].strip()
            or not isinstance(price["evidence_note"], str) or not price["evidence_note"].strip()
            or not timedelta(0) <= now - stamp(price["verified_at"]) <= timedelta(hours=24)):
        raise ValueError("Fresh official pricing evidence matching the estimator is required")
    current = snapshot(Path(root))
    if guard._json_bytes(freeze) != guard._json_bytes(current):
        raise ValueError("Prospective freeze differs from current code/policy/rates")
    protocol = panel.sha256_json(current)
    if (set(approval) != {"approval_id", "run_id", "protocol_sha256", "approved_at", "expires_at",
            "approved_by", "authorization_evidence", "accept_provider_disclosure",
            "accept_reporting_policy", "accept_threshold_overrun", "accept_paid_calls"}
            or approval["protocol_sha256"] != protocol
            or str(UUID(approval["approval_id"])) != approval["approval_id"]
            or str(UUID(approval["run_id"])) != approval["run_id"]
            or any(approval[k] is not True for k in ("accept_provider_disclosure",
                       "accept_reporting_policy", "accept_threshold_overrun", "accept_paid_calls"))
            or any(not isinstance(approval[k], str) or not approval[k].strip()
                   for k in ("approved_by", "authorization_evidence"))
            or not stamp(approval["approved_at"]) <= now < stamp(approval["expires_at"])
            or stamp(approval["expires_at"]) - stamp(approval["approved_at"]) > timedelta(hours=24)):
        raise ValueError("Fresh explicit, unexpired owner approval for this exact protocol required")
    return {"protocol_sha256": protocol, "plan": spec}


def consume_approval(directory, approval, protocol, run_id):
    """Exclusive write happens before credentials or network; never refundable."""
    if (str(UUID(run_id)) != run_id or approval["run_id"] != run_id
            or approval["protocol_sha256"] != protocol
            or str(UUID(approval["approval_id"])) != approval["approval_id"]):
        raise ValueError("Canonical run UUID required")
    directory = journal.safe_path(directory)
    journal.write(directory / (approval["approval_id"] + ".json"), {
        "version": VERSION, "approval": approval, "protocol_sha256": protocol,
        "run_id": run_id, "consumed_before_credentials_or_network": True,
        "resume_allowed": False})


def reservation(core, before, request):
    value = journal.reservation(core, before, request)
    value.pop("live_calls")
    value["delivery"] = "reserved_before_transport"
    return value


class Session:
    """Serial fresh-directory writer. Internal state computation reuses S51.

    Persisted records truthfully distinguish live versus offline test transport;
    no S51/S52 fixture-labelled journal is used as a live record.
    """
    def __init__(self, root, directory, records, protocol, threshold, *, mode):
        if mode not in {"live", "offline_fixture"}:
            raise ValueError("Explicit mode required")
        self.root, self.directory = Path(root), journal.safe_path(directory)
        self.core = panel.Rehearsal(self.root, records, mode="offline_fixture", fixture_threshold_usd=threshold)
        self.protocol, self.mode, self.event = protocol, mode, 0
        self.poisoned, self.lock = True, threading.Lock()
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        journal.write(self.directory / "manifest.json", {"version": VERSION, "mode": mode,
            "protocol_sha256": protocol, "threshold_usd": threshold,
            "imports_sha256": panel.sha256_json(records), "resume_allowed": False})
        journal.write(self.directory / "imports.json", records)
        (self.directory / "events").mkdir(mode=0o700)
        guard._sync_dir(self.directory)
        self.poisoned = False

    def step(self, credentials, connection_factory):
        with self.lock:
            if self.poisoned:
                raise ValueError("Interrupted writer; no retry/resume")
            if self.core.terminal:
                return None
            self.poisoned = True
            before = self.core.index
            request = self.core.prepare()
            self.event += 1
            directory = self.directory / "events" / f"{self.event:04d}"
            directory.mkdir(mode=0o700)
            guard._sync_dir(directory.parent)
            journal.write(directory / "reservation.json", reservation(self.core, before, request))
            if request is None:
                self.poisoned = False
                return None
            row, payload = request["row"], request["payload"]
            context = self.core.contexts[row["sequence"]]
            transport = capture.CaptureJournal(self.root, directory / "capture", 1, self.protocol, self.mode)
            def validate(raw):
                return (panel.workflow.decode_candidate(raw, row["provider"], row["model"]) if row["kind"] == "candidate"
                        else panel.score.decode(raw, row["provider"], row["model"], context["packet"]))
            result = transport.exchange(row["provider"], payload, validate,
                credential=credentials[row["provider"]], connection_factory=connection_factory)
            forwarded = result["category"] in rehearsal.BODY_CATEGORIES
            if forwarded:
                outcome = self.core.record((directory / "capture/0001.raw.bin").read_bytes())
                if ((outcome["status"] == "accepted") != result["accepted"] or self.core.accounts[-1] != result["accounting"]):
                    raise ValueError("Capture and scheduler interpretation differs")
            else:
                self.core.terminal = "transport_failure_unknown_delivery_or_cost"
            journal.write(directory / "result.json", {"category": result["category"],
                "forwarded": forwarded, "capture_hashes": rehearsal.file_hashes(directory / "capture"),
                "state": journal.result(self.core, outcome) if forwarded else None})
            self.poisoned = False
            return {"event": self.event, "category": result["category"], "terminal": self.core.terminal}


def report(core, mode, attempted, interrupted=False):
    value = core.report()
    for name in ("mode", "version", "simulation_only", "live_calls", "simulated_attempts",
                 "simulated_monitoring_usd", "unknown_simulated_charge_attempts"):
        value.pop(name)
    return {**value, "version": VERSION, "mode": mode, "simulation_only": mode != "live",
        "transport_attempts": attempted, "live_calls": attempted if mode == "live" else 0,
        "monitoring_estimate_usd": format(Decimal(core.monitored) / panel.old.TICKS_PER_USD, "f"),
        "unknown_charge_attempts": core.unknown + int(core.pending is not None and attempted > len(core.accounts)),
        "unresolved_request_reservation": core.pending is not None,
        "interrupted": interrupted, "reporting": policy.reporting_manifest(core.root)["reporting"]}


def replay(root, directory, protocol):
    """Read-only prefix inspection. Incomplete tails never authorize resumption."""
    directory = journal.safe_path(directory)
    for p in directory.rglob("*"):
        if p.is_symlink() or not (p.is_dir() or p.is_file()) or p.is_file() and p.stat().st_nlink != 1:
            raise ValueError("Linked/nonregular run artifact")
    if {p.name for p in directory.iterdir()} != {"manifest.json", "imports.json", "events"}:
        raise ValueError("Unexpected/incomplete run root")
    manifest, records = journal.read(directory / "manifest.json"), journal.read(directory / "imports.json")
    if (manifest != {"version": VERSION, "mode": manifest["mode"], "protocol_sha256": protocol,
        "threshold_usd": manifest["threshold_usd"], "imports_sha256": panel.sha256_json(records), "resume_allowed": False}
            or manifest["mode"] not in {"live", "offline_fixture"}):
        raise ValueError("Changed run manifest")
    if manifest["mode"] == "live" and records != panel.verified_source(Path(root))["bank"]["answers"]:
        raise ValueError("Live imports lack pinned source provenance")
    if manifest["mode"] == "live" and (protocol != panel.sha256_json(snapshot(Path(root)))
            or manifest["threshold_usd"] != journal.read(Path(root) / PLAN)["stop_threshold_usd"]):
        raise ValueError("Live run differs from its frozen source or spending policy")
    core = panel.Rehearsal(Path(root), records, mode="offline_fixture", fixture_threshold_usd=manifest["threshold_usd"])
    events = sorted((directory / "events").iterdir())
    if len(events) > 453 or any(not p.is_dir() or p.name != f"{i:04d}" for i,p in enumerate(events,1)):
        raise ValueError("Event sequence differs")
    attempts, incomplete = 0, False
    for i, event in enumerate(events):
        if core.terminal or incomplete:
            raise ValueError("Event after stop/interruption")
        if {p.name for p in event.iterdir()} - {"reservation.json", "capture", "result.json"}:
            raise ValueError("Unexpected event artifact")
        before = core.index
        request = core.prepare()
        if not (event / "reservation.json").exists():
            if list(event.iterdir()): raise ValueError("Capture before reservation")
            incomplete = True
            continue
        if journal.read(event / "reservation.json") != reservation(core, before, request):
            raise ValueError("Reservation/context differs")
        cap = event / "capture"
        if request is None:
            if {p.name for p in event.iterdir()} != {"reservation.json"}: raise ValueError("Capture after completion")
            continue
        if cap.exists():
            hashes = rehearsal.file_hashes(cap)
            attempts += int("0001.attempt.json" in hashes)
        has_result = (event / "result.json").exists()
        if not has_result and (not cap.exists() or not {"0001.capture.json", "0001.accounting.json"} <= set(hashes)):
            incomplete = True
            continue
        required = {"run.json", "0001.attempt.json", "0001.payload.json", "0001.capture.json", "0001.accounting.json"}
        if (not required <= set(hashes)
                or ("0001.accepted.json" in hashes) == ("0001.rejected.json" in hashes)):
            raise ValueError("Incomplete sealed capture")
        saved = journal.read(event / "result.json") if has_result else None
        meta = journal.read(cap / "0001.capture.json")
        row, payload = request["row"], request["payload"]
        rawpath = cap / "0001.raw.bin"
        raw = rawpath.read_bytes() if rawpath.exists() else b""
        if ((cap / "0001.payload.json").read_bytes() != guard._json_bytes(payload)
                or journal.read(cap / "run.json") != {"mode": manifest["mode"], "automatic_retries": 0,
                     "max_attempts": 1, "protocol_sha256": protocol, "resume_allowed": False,
                     "costs_are_simulated": manifest["mode"] != "live"}
                or journal.read(cap / "0001.attempt.json") != {"sequence": 1, "provider": row["provider"],
                     "model": row["model"], "protocol_sha256": protocol,
                     "payload_sha256": journal.digest(guard._json_bytes(payload)), "delivery": "reserved_before_connection",
                     "prospective_cost_bound": None, "automatic_retries": 0, "fixture_only": manifest["mode"] != "live"}
                or meta["bytes_saved"] != len(raw) or meta["mode"] != manifest["mode"]
                or meta["fixture_only"] != (manifest["mode"] != "live")
                or meta["body_sha256"] != (journal.digest(raw) if meta["delivery"] == "response_received" else None)):
            raise ValueError("Capture binding differs")
        forwarded = meta["category"] in rehearsal.BODY_CATEGORIES
        state = None
        if forwarded:
            if type(meta["status"]) is not int or not 200 <= meta["status"] < 300 or meta["body_eof"] is not True:
                raise ValueError("HTTP failure cannot be forwarded")
            outcome = core.record(raw)
            if ((outcome["status"] == "accepted") != (meta["category"] == "accepted")
                    or core.accounts[-1] != journal.read(cap / "0001.accounting.json")):
                raise ValueError("Replayed interpretation differs")
            state = journal.result(core, outcome)
        else:
            if journal.read(cap / "0001.accounting.json")["status"] != "unknown":
                raise ValueError("Unverified transport cost is not known")
            core.terminal = "transport_failure_unknown_delivery_or_cost"
        if has_result and saved != {"category": meta["category"], "forwarded": forwarded, "capture_hashes": hashes, "state": state}:
            raise ValueError("Capture/result binding differs")
        if not has_result:
            incomplete = True  # Inspect complete saved evidence; never resume or rewrite.
    return report(core, manifest["mode"], attempts, incomplete or core.terminal is None)


def run_live(root, freeze, approval, run_id):
    checked = validate_authorization(root, freeze, approval)
    if approval["run_id"] != run_id:
        raise ValueError("Approval belongs to another run")
    source = panel.verified_source(Path(root))  # Before consuming a paid allowance.
    parent = panel.old.prior._private_path(root, "work/s54-runs", directory=True, create=True)
    consumed = panel.old.prior._private_path(root, "work/s54-consumed-approvals", directory=True, create=True)
    if (parent / run_id).exists():
        raise ValueError("Run already exists; no reopening")
    for relative in ("work/s54-runs/" + run_id, "work/s54-consumed-approvals/" + approval["approval_id"] + ".json"):
        if subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=root, capture_output=True).returncode:
            raise ValueError("Run and approval records must be ignored")
    consume_approval(consumed, approval, checked["protocol_sha256"], run_id)
    session = Session(root, parent / run_id, source["bank"]["answers"], checked["protocol_sha256"],
                      checked["plan"]["stop_threshold_usd"], mode="live")
    keys = {}
    try:
        for provider in PRICING_URLS:
            keys[provider] = panel.old.prior.read_setting(Path(root) / ".env.local",
                panel.old.prior.KEY_NAMES[provider], secret=True)
        while not session.core.terminal:
            validate_authorization(root, freeze, approval)  # Recheck expiry and freeze before each exchange.
            progress = session.step(keys, panel.old.prior.create_tls_connection)
            if progress: print(json.dumps(progress), flush=True)
    except BaseException:
        raise guard.AdmissionBlocked("Run stopped; approval consumed. Inspect local prefix; no retry/resume.") from None
    finally:
        keys.clear()
    return replay(root, session.directory, checked["protocol_sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("snapshot", "preflight", "run", "replay"))
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "snapshot": value = snapshot(root)
    elif args.command == "replay":
        freeze = journal.read(args.freeze)
        if freeze != snapshot(root): raise ValueError("Replay source freeze differs")
        value = replay(root, args.directory, panel.sha256_json(freeze))
    else:
        freeze, approval = journal.read(args.freeze), journal.read(args.approval)
        value = (run_live(root, freeze, approval, args.run_id) if args.command == "run"
                 else validate_authorization(root, freeze, approval))
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
