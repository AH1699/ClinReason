"""Mocked integration of S46 HTTP capture and S52's durable mixed scheduler.

Only built-in simulated connections are constructible here. No caller-supplied
connection factory, credential, live mode, retry or resume command exists.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass, field
from http.client import IncompleteRead
import json
from pathlib import Path
import threading

from scripts import mixed_capture_s52 as journal, mixed_policy_s53 as policy, transport_s46 as capture

panel, guard = journal.panel, journal.guard
VERSION = "s53-mixed-transport-rehearsal-v1"
BODY_CATEGORIES = {"accepted", "response_validation", "usage_accounting", "model_identity", "json_format"}
CAPTURE_FILES = {"run.json", *{"0001." + suffix for suffix in
    ("attempt.json", "payload.json", "raw.bin", "capture.json", "accounting.json", "accepted.json", "rejected.json")}}


@dataclass(frozen=True)
class Fixture:
    body: bytes = b""
    status: int = 200
    headers: dict = field(default_factory=dict)
    fault: str | None = None

    def check(self):
        if (type(self.body) is not bytes or type(self.status) is not int
                or not isinstance(self.headers, dict)
                or any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.headers.items())
                or self.fault not in {None, "connect_timeout", "response_timeout", "read_timeout", "incomplete_read", "interrupt"}):
            raise ValueError("Explicit in-memory fixture required")


class _Response:
    def __init__(self, fixture):
        self.fixture, self.status, self.closed = fixture, fixture.status, False
        self.offset = 0

    def getheader(self, key):
        return self.fixture.headers.get(key)

    def read(self, size):
        body, fault = self.fixture.body, self.fixture.fault
        if fault == "incomplete_read":
            raise IncompleteRead(body[:size], len(body) + 1)
        if self.offset >= len(body):
            if fault == "read_timeout":
                raise TimeoutError("simulated read timeout")
            if fault == "interrupt":
                raise KeyboardInterrupt()
            return b""
        result = body[self.offset:self.offset + size]
        self.offset += len(result)
        return result

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, fixture):
        self.fixture, self.response = fixture, _Response(fixture)
        self.closed, self.requests = False, []

    def request(self, method, path, body, headers):
        self.requests.append((method, path, body, headers))  # Memory-only fake credential.

    def getresponse(self):
        if self.fixture.fault == "response_timeout":
            raise TimeoutError("simulated response timeout")
        return self.response

    def close(self):
        self.closed = True


def snapshot(root):
    return {"version": VERSION, "policy": policy.policy(root), "s52": journal.snapshot(root),
        "files": {name: journal.digest((root / name).read_bytes()) for name in
            ("scripts/mixed_transport_s53.py", "scripts/mixed_policy_s53.py", "tests/test_mixed_transport_s53.py")}}


def file_hashes(directory):
    paths = list(directory.iterdir())
    if any(not p.is_file() or p.is_symlink() or p.stat().st_nlink != 1 or p.name not in CAPTURE_FILES for p in paths):
        raise ValueError("Unexpected capture file")
    return {p.name: journal.digest(p.read_bytes()) for p in sorted(paths)}


def bridge(directory, event, category, forwarded, protocol):
    return {"version": VERSION, "event": event, "protocol_sha256": protocol,
        "category": category, "forwarded_to_scheduler": forwarded,
        "capture_sha256": file_hashes(directory), "simulation_only": True, "live_calls": 0}


class Rehearsal:
    def __init__(self, root, directory, records=None, *, mode, source_mode="fixture_unverified",
                 fixture_threshold_usd="1.00"):
        if mode != "offline_transport_fixture":
            raise ValueError("No live transport authorization or factory in S53")
        self.root, self.directory = Path(root), journal.safe_path(directory)
        frozen = snapshot(self.root)
        self.protocol = panel.sha256_json(frozen)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        journal.write(self.directory / "manifest.json", {"snapshot": frozen, "protocol_sha256": self.protocol,
            "mode": mode, "simulation_only": True, "live_calls": 0, "resume_allowed": False})
        self.scheduler = journal.Journal(self.root, self.directory / "scheduler", records,
            mode="offline_fixture", source_mode=source_mode, fixture_threshold_usd=fixture_threshold_usd)
        (self.directory / "captures").mkdir(mode=0o700)
        guard._sync_dir(self.directory)
        self._lock, self._poisoned, self._stopped = threading.Lock(), False, False
        self.last_connection = None

    def step(self, fixture):
        with self._lock:
            if self._poisoned:
                raise ValueError("Interrupted writer; no retry or resume")
            if self._stopped:
                return None
            if type(fixture) is not Fixture:
                raise ValueError("Only an explicit Fixture is accepted, never a transport callable")
            fixture.check()
            fixture = deepcopy(fixture)
            self._poisoned = True
            request = self.scheduler.prepare()
            if request is None:
                self._stopped, self._poisoned = True, False
                return None
            event = self.scheduler._event
            directory = self.directory / "captures" / f"{event:04d}"
            directory.mkdir(mode=0o700)
            guard._sync_dir(directory.parent)
            row, payload = request["row"], request["payload"]
            core = self.scheduler._core
            context = core.contexts[row["sequence"]]
            transport = capture.CaptureJournal(self.root, directory / "transport", 1, self.protocol, "offline_fixture")
            self.last_connection = None
            def validate(raw):
                return (panel.workflow.decode_candidate(raw, row["provider"], row["model"]) if row["kind"] == "candidate"
                        else panel.score.decode(raw, row["provider"], row["model"], context["packet"]))
            def factory(host, *, timeout):
                if host != capture.ENDPOINTS[row["provider"]][0] or timeout != transport.policy["socket_timeout_seconds"]:
                    raise ValueError("Unexpected endpoint or timeout")
                if fixture.fault == "connect_timeout":
                    raise TimeoutError("simulated connection timeout")
                self.last_connection = _Connection(fixture)
                return self.last_connection
            result = transport.exchange(row["provider"], payload, validate,
                credential="S53-FIXTURE-ONLY", connection_factory=factory)
            forwarded = result["category"] in BODY_CATEGORIES
            if forwarded:
                raw = (directory / "transport/0001.raw.bin").read_bytes()
                outcome = self.scheduler.record(raw)
                if ((outcome["status"] == "accepted") != result["accepted"]
                        or core.accounts[-1] != result["accounting"]):
                    raise ValueError("Transport/scheduler interpretation mismatch")
                self._stopped = core.terminal is not None
            else:
                self._stopped = True
            journal.write(directory / "bridge.json", bridge(directory / "transport", event,
                result["category"], forwarded, self.protocol))
            if not forwarded:
                journal.write(self.directory / "stopped.json", {"event": event, "category": result["category"],
                    "reason": "transport_failure_no_scheduler_forwarding", "resume_allowed": False})
            self._poisoned = False
            return {"event": event, "category": result["category"], "forwarded_to_scheduler": forwarded,
                    "stopped": self._stopped, "simulation_only": True, "live_calls": 0}


def replay(root, directory):
    """Read only; correlate HTTP captures with S52's independently rebuilt journal."""
    root, directory = Path(root), journal.safe_path(directory)
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()) or path.is_file() and path.stat().st_nlink != 1:
            raise ValueError("Linked or nonregular integration artifact")
    names = {p.name for p in directory.iterdir()}
    if not {"manifest.json", "scheduler", "captures"} <= names or names - {"manifest.json", "scheduler", "captures", "stopped.json"}:
        raise ValueError("Incomplete/unexpected integration root")
    frozen = snapshot(root)
    protocol = panel.sha256_json(frozen)
    expected = {"snapshot": frozen, "protocol_sha256": protocol, "mode": "offline_transport_fixture",
                "simulation_only": True, "live_calls": 0, "resume_allowed": False}
    if guard._json_bytes(journal.read(directory / "manifest.json")) != guard._json_bytes(expected):
        raise ValueError("Integration policy/source binding changed")
    reconstructed = journal.replay(root, directory / "scheduler")
    events = sorted((directory / "scheduler/events").iterdir())
    captures = sorted((directory / "captures").iterdir())
    if any(not p.is_dir() or p.name != f"{i:04d}" for i, p in enumerate(captures, 1)):
        raise ValueError("Capture gap or unexpected entry")
    bridged, forwarded_count, stopped, partial = 0, 0, None, None
    for i, event in enumerate(events, 1):
        capdir = directory / "captures" / event.name
        if stopped or partial:
            raise ValueError("Scheduler event after transport stop/interruption")
        reservation_path = event / "reservation.json"
        if not reservation_path.exists():
            if capdir.exists(): raise ValueError("Capture before scheduler reservation")
            partial = "interrupted_scheduler_reservation"
            continue
        reservation = journal.read(reservation_path)
        row = reservation["row"]
        if row is None:
            if capdir.exists(): raise ValueError("Capture after schedule completion")
            continue
        if not capdir.exists():
            partial = "interrupted_before_transport_capture"
            continue
        if {p.name for p in capdir.iterdir()} - {"transport", "bridge.json"}:
            raise ValueError("Unexpected bridge entry")
        transport = capdir / "transport"
        if not (capdir / "bridge.json").exists():
            if transport.exists(): file_hashes(transport)
            partial = "interrupted_before_bridge_record"
            continue
        value = journal.read(capdir / "bridge.json")
        hashes = file_hashes(transport)
        required = {"run.json", "0001.attempt.json", "0001.payload.json", "0001.capture.json", "0001.accounting.json"}
        if not required <= set(hashes) or ("0001.accepted.json" in hashes) == ("0001.rejected.json" in hashes):
            raise ValueError("Incomplete sealed transport capture")
        meta = journal.read(transport / "0001.capture.json")
        payload = journal.read(event / "payload.json")
        if ((transport / "0001.payload.json").read_bytes() != guard._json_bytes(payload)
                or journal.read(transport / "run.json") != {"mode": "offline_fixture", "automatic_retries": 0,
                    "max_attempts": 1, "protocol_sha256": protocol, "resume_allowed": False, "costs_are_simulated": True}
                or journal.read(transport / "0001.attempt.json") != {"sequence": 1, "provider": row["provider"],
                    "model": row["model"], "protocol_sha256": protocol, "payload_sha256": reservation["payload_sha256"],
                    "delivery": "reserved_before_connection", "prospective_cost_bound": None,
                    "automatic_retries": 0, "fixture_only": True}):
            raise ValueError("Wrong capture request/protocol binding")
        rawpath = transport / "0001.raw.bin"
        raw = rawpath.read_bytes() if rawpath.exists() else b""
        if (meta["bytes_saved"] != len(raw) or meta["mode"] != "offline_fixture" or meta["fixture_only"] is not True
                or meta["body_sha256"] != (journal.digest(raw) if meta["delivery"] == "response_received" else None)):
            raise ValueError("Captured body metadata mismatch")
        forwarded = meta["category"] in BODY_CATEGORIES
        if guard._json_bytes(value) != guard._json_bytes(bridge(transport, i, meta["category"], forwarded, protocol)):
            raise ValueError("Bridge/capture hash binding differs")
        if forwarded:
            if (type(meta["status"]) is not int or not 200 <= meta["status"] < 300 or meta["body_eof"] is not True
                    or not (event / "result.json").exists() or (event / "raw.bin").read_bytes() != raw
                    or journal.read(event / "result.json")["accounting"] != journal.read(transport / "0001.accounting.json")
                    or (journal.read(event / "result.json")["outcome"]["status"] == "accepted") != (meta["category"] == "accepted")):
                raise ValueError("Unsafe or inconsistent forwarding to scheduler")
            forwarded_count += 1
        else:
            if any((event / name).exists() for name in ("raw.bin", "receipt.json", "result.json")):
                raise ValueError("Failed transport must not be accepted by raw-body-only parser")
            if journal.read(transport / "0001.accounting.json")["status"] != "unknown":
                raise ValueError("Unverified transport cost cannot become zero/known")
            stopped = {"event": i, "category": meta["category"],
                "reason": "transport_failure_no_scheduler_forwarding", "resume_allowed": False}
        bridged += 1
    if len(captures) > len(events) or any(not (directory / "scheduler/events" / p.name).exists() for p in captures):
        raise ValueError("Orphan capture")
    stopfile = directory / "stopped.json"
    if stopfile.exists() and (stopped is None or journal.read(stopfile) != stopped):
        raise ValueError("Invalid stop marker")
    if stopped is not None and not stopfile.exists(): partial = "interrupted_before_stop_marker"
    return {"version": VERSION, "simulation_only": True, "live_calls": 0, "read_only": True,
        "resume_allowed": False, "capture_directories": len(captures), "sealed_bridges": bridged,
        "forwarded_replies": forwarded_count, "transport_stop": stopped, "incomplete_tail": partial,
        "unresolved_bridge_entries": int(partial is not None),
        # A crash writing bridge.json may occur AFTER the scheduler recorded the
        # reply/accounting. Do not count that as another outstanding attempt.
        "unforwarded_unresolved_attempts": int((stopped is not None or partial is not None)
                                              and reconstructed["unresolved_fixture_reservation"]),
        "scheduler": reconstructed, "reporting_contract": policy.reporting_manifest(root)["reporting"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("replay",))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(Path(__file__).resolve().parents[1], args.directory), ensure_ascii=False, indent=2))
