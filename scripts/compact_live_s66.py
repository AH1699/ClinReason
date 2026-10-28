"""Single-use approval/capture/replay adapter for the frozen S65 feasibility test.

No approval is created here. Local attestations record the trusted operator's
receipt of human consent; they do not authenticate against a hostile OS user.
Fixture mode has no credential reads, external factory or network connection.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import threading
from uuid import UUID

from scripts import compact_feasibility_s65 as previous
from scripts import standalone_live_s62 as old

pilot, capture, guard = previous.pilot, previous.capture, previous.capture.guard
read, write, digest, stamp = old.read, old.write, old.digest, old.stamp
read_setting, tls, _private_path = old.read_setting, old.tls, old._private_path
VERSION = "s66-compact-feasibility-live-v1"
PLAN = "config/compact_live_s66_v1.json"
FREEZE = "config/compact_live_s66_frozen_v1.json"
AUDIT = "data/audit/s65_compact_feasibility_rehearsal.json"
FILES = (PLAN, AUDIT, previous.FREEZE, "scripts/compact_live_s66.py", "tests/test_compact_live_s66.py")
KEY_NAMES = {"gemini": "GEMINI_API_KEY", "minimax": "MINIMAX_API_KEY"}
SOURCE_KINDS = ("verified_s62_packets", "portable_fixture_substitutes")


def plan(root):
    value = read(root / PLAN)
    fixed = {"version": VERSION, "status": "ready_for_explicit_approval", "maximum_attempts": 16,
        "judge_requests": 12, "candidate_turns": 4, "stop_threshold_usd": "3.00", "hard_ceiling": False,
        "last_request_overrun_possible": True, "max_in_flight": 1, "automatic_retries": 0,
        "resume_allowed": False, "max_request_bytes": 65536, "socket_timeout_seconds": 900,
        "exchange_deadline_seconds": 1800, "source_selection": "unchanged_frozen_s65",
        "relevance_review": "required_separately_never_inferred_from_structural_gate", "clinical_validation": False,
        "pricing_sources": [old.PRICE_URLS["gemini"], "https://ai.google.dev/api/interactions-api",
                            old.PRICE_URLS["minimax"], old.MODEL_URLS["minimax"]]}
    if (set(value) != set(fixed) | {"pricing_verified_at", "pricing_evidence"}
            or any(guard._json_bytes(value[k]) != guard._json_bytes(v) for k, v in fixed.items())
            or not isinstance(value["pricing_evidence"], str) or not value["pricing_evidence"].strip()):
        raise ValueError("Changed S66 execution scope")
    stamp(value["pricing_verified_at"])
    return value


def snapshot(root):
    root = Path(root)
    prepared = previous.snapshot(root)
    if prepared != read(root / previous.FREEZE):
        raise ValueError("Frozen S65 preparation changed")
    result = read(root / AUDIT)
    if result["preparation_sha256"] != pilot.sha256_json(prepared):
        raise ValueError("S65 request/input binding changed")
    return {"version": VERSION, "s65": prepared, "plan": plan(root),
        "files": {p: digest(pilot.public_path(root, p).read_bytes()) for p in FILES},
        "selected_packet_sha256": result["selected_packet_sha256"],
        "judge_payload_sha256": {k: v for k, v in result["fixture_payload_sha256"].items()
                                 if k.startswith(("first__", "repeat__"))},
        "pricing": previous.policy(root)["pricing"],
        "endpoints": {k: list(capture.ENDPOINTS[k]) for k in KEY_NAMES}}


def checked_freeze(root):
    value = snapshot(root)
    if value != read(root / FREEZE):
        raise ValueError("Live adapter freeze changed")
    return value


def validate_authorization(root, freeze, approval, now=None):
    now = now or datetime.now(timezone.utc)
    current = checked_freeze(root)
    if freeze != current:
        raise ValueError("Approval protocol differs from current frozen adapter")
    checked_at = stamp(current["plan"]["pricing_verified_at"])
    if not timedelta(0) <= now - checked_at <= timedelta(hours=24):
        raise ValueError("Refresh public price/model evidence before dispatch")
    flags = {"accept_paid_calls", "accept_provider_disclosure", "accept_threshold_overrun",
             "accept_no_retries_or_resume", "accept_failure_gates", "accept_provisional_reporting"}
    fields = flags | {"approval_id", "run_id", "protocol_sha256", "approved_at", "expires_at",
                      "approved_by", "authorization_evidence"}
    if (not isinstance(approval, dict) or set(approval) != fields
            or approval["protocol_sha256"] != pilot.sha256_json(current)
            or any(approval[k] is not True for k in flags)
            or any(not isinstance(approval[k], str) or not approval[k].strip()
                   for k in ("approved_by", "authorization_evidence"))
            or any(str(UUID(approval[k])) != approval[k] for k in ("approval_id", "run_id"))
            or not checked_at <= stamp(approval["approved_at"]) <= now < stamp(approval["expires_at"])
            or stamp(approval["expires_at"]) - stamp(approval["approved_at"]) > timedelta(hours=24)):
        raise ValueError("Fresh explicit human approval for this protocol required")
    return {"protocol_sha256": pilot.sha256_json(current), "maximum_attempts": 16,
            "stop_threshold_usd": "3.00", "hard_ceiling": False}


def receipt_value(approval, protocol):
    return {"version": VERSION, "approval": approval, "protocol_sha256": protocol,
            "consumed_before_credentials_or_network": True, "resume_allowed": False}


def consume_approval(root, approval, protocol):
    if (approval["protocol_sha256"] != protocol
            or any(str(UUID(approval[k])) != approval[k] for k in ("approval_id", "run_id"))):
        raise ValueError("Canonical approval/run binding required")
    parent = _private_path(root, "work/s66-consumed-approvals", directory=True, create=True)
    target = parent / (approval["approval_id"] + ".json")
    if subprocess.run(["git", "check-ignore", "-q", "--", str(target)], cwd=root, capture_output=True).returncode:
        raise ValueError("Approval receipts must be ignored")
    write(target, receipt_value(approval, protocol))


def check_items(root, items, source_kind, frozen):
    """Only exact original packets may reach live transport; explicit fake substitutes stay offline."""
    if source_kind not in SOURCE_KINDS or not isinstance(items, list) or len(items) != 6:
        raise ValueError("Six source-bound packets required")
    spec, catalog, controls = previous.public_controls(root)
    ids = [r["id"] for r in controls] + [f"historical-source-{e}" for e in previous.policy(root)["historical_source_events"]]
    if [r.get("id") for r in items] != ids or items[:3] != controls:
        raise ValueError("Selected control identity/order changed")
    for index, row in enumerate(items):
        if set(row) != {"id", "kind", "packet", "expected_error"}:
            raise ValueError("Unexpected input fields")
        previous.refs.score.check_packet(row["packet"])
        if index >= 3 and (row["kind"] != "source_probe" or row["expected_error"] is not None):
            raise ValueError("Source probe metadata changed")
        if source_kind == "verified_s62_packets" and pilot.sha256_json(row["packet"]) != frozen["selected_packet_sha256"][row["id"]]:
            raise ValueError("Original source packet changed")
    return spec, catalog, deepcopy(items)


class Core(previous.Engine):
    def __init__(self, root, inputs):
        super().__init__(root, deepcopy(inputs), mode="offline_transport_fixture")
        self.model_specs = {(v["provider"], v["model"]): v for v in self.plan["pricing"]["models"].values()}

    def prepare(self):
        request = super().prepare()
        if request is None:
            return None
        row = request["row"]
        context = self.contexts[row["id"]]
        context.update(provider=row["provider"], model=row["model"])
        return {"row": row, "context": deepcopy(context)}

    def consume(self, result, raw_bytes):
        row = deepcopy(self.pending)
        try:
            raw = capture.strict_json(raw_bytes)
        except (ValueError, UnicodeDecodeError):
            raw = None
        super().consume(result, raw)
        if self.stop == "simulated_spend_threshold_reached":
            self.stop = "spend_threshold_reached"
        return {"status": self.outcomes[row["id"]], "category": result["category"]}


def report(core, mode):
    value = core.report()
    checks = {"all_12_judgments_valid": len(core.judgments) == 12,
        "all_6_repeat_vectors_match": value["matching_fixture_repeat_vectors"] == 6,
        "both_unsafe_errors_detected": value["fixture_unsafe_error_matches"] == 2,
        "safe_partial_without_errors": value["fixture_safe_partial_error_records"] == 0,
        "all_4_candidate_turns_complete": len(core.answers) == 4,
        "no_unknown_cost": core.unknown == 0, "no_unsettled_attempt": core.pending is None,
        "schedule_exhausted": core.stop == "schedule_exhausted"}
    # Explicit allowlist: never export rationale, source text, approval or raw reasoning.
    return {"version": VERSION, "mode": mode, "simulation_only": mode == "offline_fixture",
        "live_calls": 0 if mode == "offline_fixture" else len(core.accounts) + int(core.pending is not None),
        "live_call_count_basis": "reserved_attempts_may_not_have_reached_provider",
        "measured_model_scores": 0, "settled_attempts": len(core.accounts), "maximum_attempts": 16,
        "accepted_judgments": len(core.judgments), "accepted_candidate_turns": len(core.answers),
        "matching_repeat_vectors": value["matching_fixture_repeat_vectors"],
        "unsafe_error_matches": value["fixture_unsafe_error_matches"],
        "safe_partial_error_records": value["fixture_safe_partial_error_records"],
        "monitoring_usd": str(Decimal(core.monitored) / previous.TICKS_PER_USD),
        "cost_basis": "simulated_token_estimates" if mode == "offline_fixture" else "token_estimates_not_invoice",
        "unknown_cost_attempts": core.unknown, "unsettled_attempts": int(core.pending is not None),
        "terminal": core.stop, "skipped": value["skipped"],
        "unreached": value["unreached"] - int(core.pending is not None),
        "outcomes": deepcopy(core.outcomes), "closed_lanes": sorted(core.closed),
        "technical_gate": {"checks": checks, "pass": all(checks.values()), "clinical_validation": False},
        "relevance_review": "pending_separate_local_review", "overall_feasibility_passed": False,
        "broader_run_authorized": False, "clinical_validation": False, "hard_ceiling": False,
        "last_request_overrun_possible": True}


def reservation(core, before, request, mode, now):
    return {**old.previous.reservation(core, before, request),
        "delivery": "reserved_before_transport", "simulation_only": mode == "offline_fixture", "reserved_at": now}


def settled(core, outcome, result, directory):
    return {"outcome": outcome, "category": result["category"], "accounting": result["accounting"],
        "capture_hashes": old.previous.capture_hashes(directory), "terminal": core.stop,
        "monitored_ticks": core.monitored, "unknown_attempts": core.unknown, "closed_lanes": sorted(core.closed)}


def input_pins(root, frozen):
    parent = old.snapshot(root)
    return {**parent["s61"]["files"], **parent["files"],
            **pilot.verify(root)["files"], pilot.MANIFEST: digest((root / pilot.MANIFEST).read_bytes()),
            **frozen["s65"]["files"], **frozen["files"], FREEZE: digest((root / FREEZE).read_bytes())}


def ordered_inputs(items):
    # S65 embeds packet JSON as a string in the request. Preserve insertion order
    # across journaling; canonicalizing objects would silently change that string.
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


class Session:
    def __init__(self, root, directory, *, mode, source_directory=None, fixture_items=None, freeze=None, approval=None):
        self.root, self.mode = Path(root), mode
        if mode not in {"live", "offline_fixture"}:
            raise ValueError("Explicit execution mode required")
        self.freeze = checked_freeze(self.root)
        self.approval = deepcopy(approval)
        self.protocol = pilot.sha256_json(self.freeze)
        if mode == "live":
            if fixture_items is not None:
                raise ValueError("No substituted live inputs")
            validate_authorization(self.root, freeze, approval)
        elif freeze is not None or approval is not None:
            raise ValueError("Offline fixtures cannot carry paid authorization")
        if fixture_items is not None:
            if source_directory is not None:
                raise ValueError("Select one fixture source")
            source_kind, items = "portable_fixture_substitutes", fixture_items
        else:
            if source_directory is None:
                raise ValueError("Verified historical source directory required")
            source_kind = "verified_s62_packets"
            items = previous.source_inputs(self.root, Path(source_directory).absolute())[2]
        self.inputs = check_items(self.root, items, source_kind, self.freeze)
        self.source_kind = source_kind
        self.core = Core(self.root, self.inputs)
        if mode == "live":
            expected = self.root / "work/s66-runs" / approval["run_id"]
            if Path(directory).absolute() != expected.absolute():
                raise ValueError("Run path must match approved ID")
            _private_path(self.root, "work/s66-runs", directory=True, create=True)
            self.directory = _private_path(self.root, "work/s66-runs/" + approval["run_id"])
            if self.directory.exists() or subprocess.run(["git", "check-ignore", "-q", "--", str(self.directory)],
                    cwd=root, capture_output=True).returncode:
                raise ValueError("Fresh ignored run directory required")
            consume_approval(self.root, approval, self.protocol)
        else:
            self.directory = old.previous.safe_directory(self.root, directory)
        self.input_pins = input_pins(self.root, self.freeze)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        write(self.directory / "manifest.json", {"snapshot": self.freeze, "protocol_sha256": self.protocol,
            "mode": mode, "approval": approval, "source_kind": source_kind,
            "source_items_sha256": pilot.sha256_json(ordered_inputs(self.inputs[2])), "resume_allowed": False})
        write(self.directory / "inputs.json", ordered_inputs(self.inputs[2]))
        (self.directory / "events").mkdir(mode=0o700)
        guard._sync_dir(self.directory)
        self.lock, self.poisoned, self.closed, self.event = threading.Lock(), False, False, 0

    def step(self, fixture=None):
        with self.lock:
            if self.poisoned:
                raise ValueError("Interrupted writer; no retry or resume")
            if self.closed:
                return None
            if self.mode == "offline_fixture":
                if type(fixture) is not old.previous.Fixture:
                    raise ValueError("Built-in fixture required")
                fixture.check()
                fixture = deepcopy(fixture)
            elif fixture is not None:
                raise ValueError("No fixture or external factory in live mode")
            self.poisoned = True
            if any(digest(pilot.public_path(self.root, p).read_bytes()) != h for p, h in self.input_pins.items()):
                raise ValueError("Bound files changed before dispatch")
            if read(self.directory / "inputs.json") != ordered_inputs(self.inputs[2]):
                raise ValueError("Saved input copy changed")
            at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            before = self.core.index
            request = self.core.prepare()
            if request is None:
                write(self.directory / "report.json", report(self.core, self.mode))
                self.closed, self.poisoned = True, False
                return None
            if self.mode == "live":
                validate_authorization(self.root, self.freeze, self.approval, now=stamp(at))
                receipt = _private_path(self.root, "work/s66-consumed-approvals/" + self.approval["approval_id"] + ".json")
                if receipt.stat().st_nlink != 1 or read(receipt) != receipt_value(self.approval, self.protocol):
                    raise ValueError("Consumed approval receipt changed")
            row, context = request["row"], request["context"]
            if row["kind"] == "judge" and self.source_kind == "verified_s62_packets":
                if pilot.sha256_json(context["payload"]) != self.freeze["judge_payload_sha256"][row["id"]]:
                    raise ValueError("Frozen judge request changed")
            self.event += 1
            if self.event > 16:
                raise ValueError("Request allowance exhausted")
            event = self.directory / "events" / f"{self.event:04d}"
            event.mkdir(mode=0o700)
            guard._sync_dir(event.parent)
            write(event / "reservation.json", reservation(self.core, before, request, self.mode, at))
            write(event / "payload.json", context["payload"])
            journal = capture.CaptureJournal(self.root, event / "transport", 1, self.protocol, self.mode)
            journal.specs = deepcopy(self.core.model_specs)
            def factory(host, *, timeout):
                if host != capture.ENDPOINTS[row["provider"]][0] or timeout != 900:
                    raise ValueError("Unexpected fixture endpoint or timeout")
                if fixture.fault == "connect_timeout":
                    raise TimeoutError("Fixture timeout")
                return old.previous.fake._Connection(fixture)
            credential = None
            try:
                credential = ("S66-FIXTURE-ONLY" if self.mode == "offline_fixture" else
                    read_setting(self.root / ".env.local", KEY_NAMES[row["provider"]], secret=True))
                result = journal.exchange(row["provider"], context["payload"], self.core.decode,
                    credential=credential, connection_factory=factory if self.mode == "offline_fixture" else tls)
            finally:
                credential = None
            raw = event / "transport/0001.raw.bin"
            outcome = self.core.consume(result, raw.read_bytes() if raw.exists() else b"")
            write(event / "result.json", settled(self.core, outcome, result, event / "transport"))
            if self.core.stop:
                write(self.directory / "report.json", report(self.core, self.mode))
                self.closed = True
            self.poisoned = False
            return {"event": self.event, "outcome": outcome, "terminal": self.core.stop,
                    "monitoring_usd": str(Decimal(self.core.monitored) / previous.TICKS_PER_USD), "mode": self.mode}


def replay(root, directory):
    root = Path(root)
    directory = old.previous.safe_directory(root, directory)
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()) or path.is_file() and path.stat().st_nlink != 1:
            raise ValueError("Linked/nonregular journal artifact")
    names = {p.name for p in directory.iterdir()}
    if not {"manifest.json", "inputs.json", "events"} <= names or names - {"manifest.json", "inputs.json", "events", "report.json"}:
        raise ValueError("Incomplete/unexpected journal root")
    manifest = read(directory / "manifest.json")
    frozen = checked_freeze(root)
    protocol = pilot.sha256_json(frozen)
    mode, approval, source_kind = manifest["mode"], manifest["approval"], manifest["source_kind"]
    serialized = read(directory / "inputs.json")
    if not isinstance(serialized, str):
        raise ValueError("Ordered source snapshot required")
    items = capture.strict_json(serialized.encode("utf-8"))
    if mode not in {"live", "offline_fixture"} or manifest != {"snapshot": frozen, "protocol_sha256": protocol,
            "mode": mode, "approval": approval, "source_kind": source_kind,
            "source_items_sha256": pilot.sha256_json(serialized), "resume_allowed": False}:
        raise ValueError("Journal manifest/input binding differs")
    inputs = check_items(root, items, source_kind, frozen)
    if mode == "live":
        validate_authorization(root, frozen, approval, now=stamp(approval["approved_at"]))
        expected = root / "work/s66-runs" / approval["run_id"]
        receipt = _private_path(root, "work/s66-consumed-approvals/" + approval["approval_id"] + ".json")
        if (source_kind != "verified_s62_packets" or directory != expected or receipt.stat().st_nlink != 1
                or read(receipt) != receipt_value(approval, protocol)):
            raise ValueError("Live approval/run/source receipt differs")
    elif approval is not None:
        raise ValueError("Fixture journal with paid approval")
    core = Core(root, inputs)
    events = sorted((directory / "events").iterdir())
    if len(events) > 16 or any(not p.is_dir() or p.name != f"{i:04d}" for i, p in enumerate(events, 1)):
        raise ValueError("Invalid event sequence")
    partial, last_time = None, None
    for event in events:
        if partial is not None or core.stop:
            raise ValueError("Event after interruption or stop")
        names = {p.name for p in event.iterdir()}
        order = ["reservation.json", "payload.json", "transport", "result.json"]
        if names not in [set(order[:i]) for i in range(5)]:
            raise ValueError("Orphan/reordered event artifact")
        before = core.index
        request = core.prepare()
        if request is None:
            raise ValueError("Event beyond permitted schedule")
        if request["row"]["kind"] == "judge" and source_kind == "verified_s62_packets":
            if pilot.sha256_json(request["context"]["payload"]) != frozen["judge_payload_sha256"][request["row"]["id"]]:
                raise ValueError("Frozen judge request changed")
        partial = "interrupted_before_reservation"
        if "reservation.json" not in names: continue
        saved = read(event / "reservation.json")
        at = stamp(saved["reserved_at"])
        if last_time is not None and at < last_time:
            raise ValueError("Reservation time moved backwards")
        last_time = at
        if mode == "live": validate_authorization(root, frozen, approval, now=at)
        if saved != reservation(core, before, request, mode, saved["reserved_at"]):
            raise ValueError("Reservation/context differs")
        partial = "interrupted_before_payload"
        if "payload.json" not in names: continue
        if (event / "payload.json").read_bytes() != guard._json_bytes(request["context"]["payload"]):
            raise ValueError("Payload differs")
        partial = "interrupted_before_complete_capture"
        if "transport" not in names: continue
        captured = old.reconstruct_capture(core, event / "transport", protocol, mode)
        if captured is None:
            if "result.json" in names: raise ValueError("Result without complete capture")
            continue
        result, raw = captured
        outcome = core.consume(result, raw)
        partial = "captured_reply_reconstructed_without_result"
        if "result.json" not in names: continue
        if read(event / "result.json") != settled(core, outcome, result, event / "transport"):
            raise ValueError("Reconstructed outcome differs")
        partial = None
    path = directory / "report.json"
    if path.exists():
        if partial is not None or not core.stop and core.prepare() is not None:
            raise ValueError("Report before terminal state")
        if read(path) != report(core, mode):
            raise ValueError("Report differs from raw reconstruction")
    return {"version": VERSION, "protocol_sha256": protocol, "read_only": True, "resume_allowed": False,
            "events": len(events), "incomplete_tail": partial, "report_verified": path.exists(),
            "source_kind": source_kind, "report": report(core, mode)}


def fixture_for(core):
    """Preview on a copy; never consumes a real request or alters caller state."""
    clone = deepcopy(core)
    if clone.prepare() is None:
        return old.previous.Fixture()
    return old.previous.Fixture(guard._json_bytes(previous.next_fixture(clone)))


def run_live(root, source_directory, freeze, approval):
    directory = Path(root) / "work/s66-runs" / approval["run_id"]
    session = Session(root, directory, mode="live", source_directory=source_directory, freeze=freeze, approval=approval)
    try:
        while True:
            value = session.step()
            if value is None: break
            print(json.dumps(value), flush=True)
    except BaseException:
        raise guard.AdmissionBlocked("Stopped; approval consumed. Inspect prefix; never retry/resume.") from None
    return replay(root, directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("proposal", "snapshot", "preflight", "rehearse", "run", "replay"))
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--source-directory", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "snapshot":
        value = snapshot(root)
    elif args.command == "proposal":
        frozen = checked_freeze(root)
        value = {"protocol_sha256": pilot.sha256_json(frozen), "plan": frozen["plan"],
                 "live_authorized": False, "new_live_calls": 0}
    elif args.command == "replay":
        if args.directory is None: parser.error("replay requires --directory")
        value = replay(root, args.directory)
    elif args.command == "rehearse":
        if args.directory is None or args.source_directory is None: parser.error("rehearse requires source and output directories")
        session = Session(root, args.directory, mode="offline_fixture", source_directory=args.source_directory)
        while session.step(fixture_for(session.core)) is not None: pass
        value = replay(root, args.directory)
    else:
        if args.approval is None: parser.error("preflight/run require an existing private human approval")
        relative = args.approval.absolute().relative_to(root)
        path = _private_path(root, str(relative))
        if path.parent != root / "work/s66-approvals" or path.stat().st_nlink != 1 or path.stat().st_size > 16384:
            raise ValueError("Regular bounded private S66 approval file required")
        frozen, approval = checked_freeze(root), read(path)
        if args.command == "run":
            if args.source_directory is None: parser.error("run requires --source-directory")
            value = run_live(root, args.source_directory, frozen, approval)
        else:
            value = validate_authorization(root, frozen, approval)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
