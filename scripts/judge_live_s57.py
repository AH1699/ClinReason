"""One-use, approval-bound judge-only runner and read-only prefix inspection.

No old allowance, retry, resume, regenerated candidate or repaired judgment.
The trusted local operator must record fresh human approval for the exact freeze.
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

from scripts import judge_panel_s57 as engine

saved, panel = engine.saved, engine.panel
old, journal, guard = saved.live, saved.journal, saved.guard
capture, rehearsal = old.capture, old.rehearsal
VERSION = engine.VERSION
PLAN = "config/judge_live_s57_v1.json"
FREEZE = "config/judge_live_s57_frozen_v1.json"
READINESS = "data/audit/s56_saved_bank_readiness.json"
PRICE_URL = "https://ai.google.dev/gemini-api/docs/pricing"
FILES = (PLAN, "scripts/judge_panel_s57.py", "scripts/judge_live_s57.py",
         "tests/test_judge_panel_s57.py", "tests/test_judge_live_s57.py")


def plan(root):
    value = journal.read(root / PLAN)
    expected = {"version": VERSION, "status": "ready_for_explicit_approval", "maximum_attempts": 324,
        "new_candidate_calls": 0, "hard_ceiling": False, "last_request_overrun_possible": True,
        "automatic_retries": 0, "resume_allowed": False, "maximum_development_format_failures": 3,
        "bank_path": "work/s56-banks/panel-answer-bank.json",
        "bank_sha256": journal.read(root / READINESS)["bank_sha256"]}
    if (set(value) != set(expected) | {"stop_threshold_usd", "pricing_verification"}
            or any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items())):
        raise ValueError("Judge-only scope or failure policy changed")
    amount = value["stop_threshold_usd"]
    if (not isinstance(amount, str) or not Decimal(amount).is_finite()
            or Decimal(amount) <= 0 or Decimal(amount).as_tuple().exponent < -2):
        raise ValueError("Positive USD stop threshold required")
    return value


def snapshot(root):
    root = Path(root)
    spec, prior = plan(root), journal.read(root / READINESS)
    actual = {p: journal.digest((root / p).read_bytes()) for p in saved.FILES}
    historical = panel.sha256_json(old.snapshot(root))
    if actual != prior["files"] or historical != prior["source_protocol_sha256"]:
        raise ValueError("S54/S56 frozen inputs changed")
    return {"version": VERSION, "s54_protocol_sha256": historical,
        "s56_readiness_sha256": panel.sha256_json(prior), "s56_files": actual,
        "bank_sha256": spec["bank_sha256"], "schedule_sha256": panel.sha256_json(saved.schedule(root)),
        "failure_policy": deepcopy(engine.FAILURE_POLICY), "control_gate": {"expected_records": 36, **panel.old.GATE},
        "score_version": engine.score.VERSION, "arithmetic_sha256": panel.sha256_json(engine.score.ARITHMETIC),
        "files": {p: journal.digest((root / p).read_bytes()) for p in FILES}}


def validate_authorization(root, freeze, approval, now=None):
    now = now or datetime.now(timezone.utc)
    spec = plan(Path(root))
    price = spec["pricing_verification"]
    expected = {"source": PRICE_URL, "model": "gemini-3.8-flash", "service_tier": "standard",
        "input_per_million": 0.75, "output_per_million": 3.75,
        "output_includes_thinking": True, "cache_discount_used": False}
    model = next(s for s in panel.workflow.design(root)["judges"] if s["model"] == expected["model"])
    if (not isinstance(price, dict) or set(price) != set(expected) | {"verified_at", "verified_by", "evidence_note"}
            or any(type(price[k]) is not type(v) or price[k] != v for k, v in expected.items())
            or any(not isinstance(price[k], str) or not price[k].strip() for k in ("verified_by", "evidence_note"))
            or any(price[k] != model[k] for k in ("input_per_million", "output_per_million"))
            or not timedelta(0) <= now - old.stamp(price["verified_at"]) <= timedelta(hours=24)):
        raise ValueError("Fresh official price evidence matching accounting required")
    current = snapshot(Path(root))
    if guard._json_bytes(current) != guard._json_bytes(freeze):
        raise ValueError("Prospective protocol differs")
    protocol = panel.sha256_json(current)
    permissions = ("accept_provider_disclosure", "accept_reporting_policy", "accept_threshold_overrun",
                   "accept_paid_calls", "accept_bounded_format_failure_policy")
    fields = {"approval_id", "run_id", "protocol_sha256", "approved_at", "expires_at",
              "approved_by", "authorization_evidence", *permissions}
    if (not isinstance(approval, dict) or set(approval) != fields or approval["protocol_sha256"] != protocol
            or str(UUID(approval["approval_id"])) != approval["approval_id"]
            or str(UUID(approval["run_id"])) != approval["run_id"]
            or any(approval[k] is not True for k in permissions)
            or any(not isinstance(approval[k], str) or not approval[k].strip() for k in ("approved_by", "authorization_evidence"))
            or not old.stamp(approval["approved_at"]) <= now < old.stamp(approval["expires_at"])
            or old.stamp(approval["approved_at"]) < old.stamp(price["verified_at"])
            or old.stamp(approval["expires_at"]) - old.stamp(approval["approved_at"]) > timedelta(hours=24)):
        raise ValueError("Fresh explicit owner approval for exact protocol, price and failure policy required")
    return {"protocol_sha256": protocol, "plan": spec}


def verified_source(root):
    spec = plan(root)
    path = journal.safe_path(root / spec["bank_path"])
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Regular private bank required")
    bank = journal.read(path)
    if panel.sha256_json(bank) != spec["bank_sha256"]:
        raise ValueError("Saved bank pin differs")
    saved.verify_bank(root, bank)  # Replays sealed sources; self-hashes alone are insufficient.
    return bank


def consume_approval(directory, approval, protocol, run_id):
    if (str(UUID(run_id)) != run_id or approval["run_id"] != run_id
            or approval["protocol_sha256"] != protocol
            or str(UUID(approval["approval_id"])) != approval["approval_id"]):
        raise ValueError("Approval/run binding differs")
    journal.write(journal.safe_path(directory) / (approval["approval_id"] + ".json"), {
        "version": VERSION, "approval": approval, "protocol_sha256": protocol,
        "run_id": run_id, "consumed_before_credentials_or_network": True, "resume_allowed": False})


def result(core, outcome):
    return {**journal.result(core, outcome), "development_format_failures": core.format_failures}


class Session:
    """Fresh serial journal; an interrupted or failed writer cannot be reused."""

    def __init__(self, root, directory, bank, protocol, threshold, *, mode):
        if mode not in {"live", "offline_fixture"}:
            raise ValueError("Explicit mode required")
        self.root, self.directory = Path(root), journal.safe_path(directory)
        self.core = engine.Core(self.root, bank, threshold)
        self.protocol, self.mode, self.event = protocol, mode, 0
        self.poisoned, self.lock = True, threading.Lock()
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        journal.write(self.directory / "manifest.json", {"version": VERSION, "mode": mode,
            "protocol_sha256": protocol, "threshold_usd": threshold,
            "bank_sha256": panel.sha256_json(bank), "resume_allowed": False})
        journal.write(self.directory / "bank.json", bank)
        (self.directory / "events").mkdir(mode=0o700)
        guard._sync_dir(self.directory)
        self.poisoned = False

    def step(self, credential, connection_factory):
        with self.lock:
            if self.poisoned:
                raise ValueError("Interrupted writer; no retry/resume")
            if self.core.terminal:
                return None
            self.poisoned = True
            before = self.core.index
            request = self.core.prepare()
            self.event += 1
            event = self.directory / "events" / f"{self.event:04d}"
            event.mkdir(mode=0o700)
            guard._sync_dir(event.parent)
            journal.write(event / "reservation.json", old.reservation(self.core, before, request))
            if request is None:
                self.poisoned = False
                return None
            row, payload = request["row"], request["payload"]
            context = self.core.contexts[row["sequence"]]
            transport = capture.CaptureJournal(self.root, event / "capture", 1, self.protocol, self.mode)
            observed = transport.exchange("gemini", payload,
                lambda raw: engine.score.decode(raw, "gemini", row["model"], context["packet"]),
                credential=credential, connection_factory=connection_factory)
            forwarded = observed["category"] in rehearsal.BODY_CATEGORIES
            if forwarded:
                outcome = self.core.record((event / "capture/0001.raw.bin").read_bytes())
                if ((outcome["status"] == "accepted") != observed["accepted"]
                        or self.core.accounts[-1] != observed["accounting"]):
                    raise ValueError("Capture and scheduler disagree")
            else:
                self.core.terminal = "transport_failure_unknown_delivery_or_cost"
            journal.write(event / "result.json", {"category": observed["category"], "forwarded": forwarded,
                "capture_hashes": rehearsal.file_hashes(event / "capture"),
                "state": result(self.core, outcome) if forwarded else None})
            self.poisoned = False
            return {"event": self.event, "category": observed["category"], "terminal": self.core.terminal,
                "development_format_failures": self.core.format_failures}


def restore(root, directory, protocol):
    """Reconstruct a complete or interrupted prefix read-only, never resume it."""
    directory = journal.safe_path(directory)
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()) or path.is_file() and path.stat().st_nlink != 1:
            raise ValueError("Linked/nonregular artifact")
    if {p.name for p in directory.iterdir()} != {"manifest.json", "bank.json", "events"}:
        raise ValueError("Unexpected/incomplete run root")
    manifest, bank = journal.read(directory / "manifest.json"), journal.read(directory / "bank.json")
    if (manifest != {"version": VERSION, "mode": manifest["mode"], "protocol_sha256": protocol,
            "threshold_usd": manifest["threshold_usd"], "bank_sha256": panel.sha256_json(bank), "resume_allowed": False}
            or manifest["mode"] not in {"live", "offline_fixture"}):
        raise ValueError("Manifest or saved bank changed")
    if manifest["mode"] == "live":
        if (protocol != panel.sha256_json(snapshot(root))
                or manifest["threshold_usd"] != plan(root)["stop_threshold_usd"]
                or bank != verified_source(root)):
            raise ValueError("Live source or frozen protocol differs")
    core = engine.Core(root, bank, manifest["threshold_usd"])
    events = sorted((directory / "events").iterdir())
    if len(events) > 325 or any(not p.is_dir() or p.name != f"{i:04d}" for i, p in enumerate(events, 1)):
        raise ValueError("Event sequence differs")
    attempts, incomplete = 0, False
    for event in events:
        if core.terminal or incomplete:
            raise ValueError("Event after stop/interruption")
        if {p.name for p in event.iterdir()} - {"reservation.json", "capture", "result.json"}:
            raise ValueError("Unexpected event artifact")
        before = core.index
        request = core.prepare()
        if not (event / "reservation.json").exists():
            if list(event.iterdir()):
                raise ValueError("Capture before reservation")
            incomplete = True
            continue
        if journal.read(event / "reservation.json") != old.reservation(core, before, request):
            raise ValueError("Request/context/skips differ")
        if request is None:
            if {p.name for p in event.iterdir()} != {"reservation.json"}:
                raise ValueError("Capture after completion")
            continue
        cap = event / "capture"
        hashes = rehearsal.file_hashes(cap) if cap.exists() else {}
        attempts += int("0001.attempt.json" in hashes)
        has_result = (event / "result.json").exists()
        if not has_result and not {"0001.capture.json", "0001.accounting.json"} <= set(hashes):
            incomplete = True
            continue
        required = {"run.json", "0001.attempt.json", "0001.payload.json", "0001.capture.json", "0001.accounting.json"}
        if (not required <= set(hashes)
                or ("0001.accepted.json" in hashes) == ("0001.rejected.json" in hashes)):
            raise ValueError("Incomplete sealed capture")
        meta = journal.read(cap / "0001.capture.json")
        row, payload = request["row"], request["payload"]
        rawpath = cap / "0001.raw.bin"
        raw = rawpath.read_bytes() if rawpath.exists() else b""
        if ((cap / "0001.payload.json").read_bytes() != guard._json_bytes(payload)
                or journal.read(cap / "run.json") != {"mode": manifest["mode"], "automatic_retries": 0,
                    "max_attempts": 1, "protocol_sha256": protocol, "resume_allowed": False,
                    "costs_are_simulated": manifest["mode"] != "live"}
                or journal.read(cap / "0001.attempt.json") != {"sequence": 1, "provider": "gemini",
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
            accepted = outcome["status"] == "accepted"
            if (accepted != (meta["category"] == "accepted")
                    or core.accounts[-1] != journal.read(cap / "0001.accounting.json")):
                raise ValueError("Replayed outcome/accounting differs")
            if accepted and journal.read(cap / "0001.accepted.json") != {
                    "result": core.judgments[engine.workflow.judgment_key(row)], "raw_sha256": journal.digest(raw)}:
                raise ValueError("Accepted interpretation differs from raw reply")
            state = result(core, outcome)
        else:
            if journal.read(cap / "0001.accounting.json")["status"] != "unknown":
                raise ValueError("Unverified transport charge is not known")
            core.terminal = "transport_failure_unknown_delivery_or_cost"
        if not forwarded or outcome["status"] != "accepted":
            if journal.read(cap / "0001.rejected.json") != {"category": meta["category"],
                    "exception_text_retained": False, "charge_may_have_occurred": True, "retry": False}:
                raise ValueError("Rejection receipt differs")
        expected = {"category": meta["category"], "forwarded": forwarded, "capture_hashes": hashes, "state": state}
        if has_result and journal.read(event / "result.json") != expected:
            raise ValueError("Capture/result binding differs")
        if not has_result:
            incomplete = True
    return engine.report(core, manifest["mode"], attempts, incomplete or core.terminal is None), core


def replay(root, directory, protocol):
    return restore(root, directory, protocol)[0]


def run_live(root, freeze, approval, run_id):
    checked = validate_authorization(root, freeze, approval)
    if approval["run_id"] != run_id:
        raise ValueError("Approval belongs to another run")
    bank = verified_source(root)
    parent = panel.old.prior._private_path(root, "work/s57-runs", directory=True, create=True)
    consumed = panel.old.prior._private_path(root, "work/s57-consumed-approvals", directory=True, create=True)
    if (parent / run_id).exists():
        raise ValueError("Run exists; no reopening")
    for relative in ("work/s57-runs/" + run_id, "work/s57-consumed-approvals/" + approval["approval_id"] + ".json"):
        if subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=root, capture_output=True).returncode:
            raise ValueError("Private records must be ignored")
    consume_approval(consumed, approval, checked["protocol_sha256"], run_id)
    credential = None
    try:
        session = Session(root, parent / run_id, bank, checked["protocol_sha256"],
                          checked["plan"]["stop_threshold_usd"], mode="live")
        credential = panel.old.prior.read_setting(root / ".env.local", panel.old.prior.KEY_NAMES["gemini"], secret=True)
        while not session.core.terminal:
            validate_authorization(root, freeze, approval)
            progress = session.step(credential, panel.old.prior.create_tls_connection)
            if progress:
                print(json.dumps(progress), flush=True)
    except BaseException:
        raise guard.AdmissionBlocked("Stopped; approval consumed. Inspect saved prefix; no retry/resume.") from None
    finally:
        credential = None
    return replay(root, session.directory, checked["protocol_sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("snapshot", "verify-source", "preflight", "run", "replay"))
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "snapshot":
        value = snapshot(root)
    elif args.command == "verify-source":
        bank = verified_source(root)
        value = {"verified_stages": len(bank["answers"]), "bank_sha256": panel.sha256_json(bank), "live_calls": 0}
    elif args.command == "replay":
        freeze = journal.read(args.freeze)
        if freeze != snapshot(root):
            raise ValueError("Frozen replay implementation differs")
        value = replay(root, args.directory, panel.sha256_json(freeze))
    else:
        freeze, approval = journal.read(args.freeze), journal.read(args.approval)
        value = (run_live(root, freeze, approval, args.run_id) if args.command == "run"
                 else validate_authorization(root, freeze, approval))
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
