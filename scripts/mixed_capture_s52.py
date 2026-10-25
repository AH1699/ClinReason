"""Durable OFFLINE supplied-byte journal around S51; never HTTP, keys or resume.

Replay independently reads the journal and reconstructs the frozen S51 state
machine. It is not an independent clinical scorer or a live transport test.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading

from scripts import mixed_panel_s51 as panel

VERSION = "s52-mixed-capture-offline-v1"
guard = panel.guard


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return panel.saved.capture.strict_json(path.read_bytes())


def write(path, value):
    guard._write_exclusive(path, guard._json_bytes(value))


def safe_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked journal path")
    return path


def snapshot(root):
    # S51 readiness audits the historical freeze chain. Per-request replay also
    # reconstructs and compares the full context, not just this summary.
    return {"s51": panel.readiness(root), "adapter_sha256": digest(Path(__file__).read_bytes()),
            "tests_sha256": digest((root / "tests/test_mixed_capture_s52.py").read_bytes())}


def source(root, records, source_mode):
    if source_mode == "fixture_unverified":
        if records is None:
            raise ValueError("Explicit fixture imports required")
        return deepcopy(records), {"mode": source_mode, "historical_provenance_verified": False}
    if source_mode == "verified_saved_bank" and records is None:
        value = panel.verified_source(root)
        return value["bank"]["answers"], {"mode": source_mode, "historical_provenance_verified": True,
            **{k: value[k] for k in ("source_sha256", "source_protocol_sha256", "bank_sha256")}}
    raise ValueError("Invalid import mode; real provenance cannot be asserted by supplied records")


def reservation(core, before, request):
    return {"row": request["row"] if request else None,
        "skips": [{"sequence": i, **core.outcomes[i]} for i in range(before + 1, core.index + 1)
                  if core.outcomes[i]["status"] == "skipped"],
        "context_sha256": panel.sha256_json(core.contexts[request["row"]["sequence"]]) if request else None,
        "payload_sha256": digest(guard._json_bytes(request["payload"])) if request else None,
        "delivery": "reserved_for_supplied_fixture_only", "live_calls": 0, "retry": False}


def result(core, outcome):
    return {"outcome": outcome, "accounting": core.accounts[-1], "terminal": core.terminal,
            "index": core.index, "monitored_ticks": core.monitored,
            "unknown_attempts": core.unknown, "closed_lanes": deepcopy(core.closed_lanes)}


class Journal:
    """Fresh-directory-only writer. A write/parser failure poisons this object.

    Raw bytes precede the receipt and interpretation. No credential, transport
    callback, retry, reopening or resume API exists. All money is simulated.
    """

    def __init__(self, root, directory, records=None, *, mode, source_mode="fixture_unverified",
                 fixture_threshold_usd="1.00"):
        if mode != "offline_fixture":
            raise ValueError("Live execution is not available")
        self.root, self.directory = Path(root), safe_path(directory)
        records, provenance = source(self.root, records, source_mode)
        self._core = panel.Rehearsal(self.root, records, mode=mode,
                                     fixture_threshold_usd=fixture_threshold_usd)
        self._lock, self._poisoned, self._pending, self._event = threading.Lock(), True, None, 0
        self.manifest = {"version": VERSION, "mode": mode, "simulation_only": True,
            "snapshot": snapshot(self.root), "imports_sha256": panel.sha256_json(records),
            "source": provenance, "fixture_threshold_usd": fixture_threshold_usd,
            "automatic_retries": 0, "resume_allowed": False, "live_calls": 0}
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        write(self.directory / "manifest.json", self.manifest)
        write(self.directory / "imports.json", records)
        (self.directory / "events").mkdir(mode=0o700)
        guard._sync_dir(self.directory)
        self._poisoned = False

    def prepare(self):
        with self._lock:
            if self._poisoned or self._pending is not None:
                raise ValueError("Stopped or pending journal; no retry/resume")
            if self._core.terminal:
                return None
            self._poisoned = True
            self._event += 1
            directory = self.directory / "events" / f"{self._event:04d}"
            directory.mkdir(mode=0o700)
            guard._sync_dir(directory.parent)
            before = self._core.index
            request = self._core.prepare()
            write(directory / "reservation.json", reservation(self._core, before, request))
            if request is None:
                write(self.directory / "report.json", self._core.report())
            else:
                write(directory / "payload.json", request["payload"])
                self._pending = directory
            self._poisoned = False
            return deepcopy(request)

    def record(self, raw_bytes):
        with self._lock:
            if self._poisoned or self._pending is None:
                raise ValueError("No pending supplied-byte reservation")
            self._poisoned = True
            if type(raw_bytes) is not bytes:
                raise ValueError("Only supplied bytes are accepted; no transport callable")
            directory = self._pending
            guard._write_exclusive(directory / "raw.bin", raw_bytes)
            write(directory / "receipt.json", {"sha256": digest(raw_bytes), "bytes": len(raw_bytes),
                  "complete_supplied_bytes": True, "http_delivery_tested": False})
            outcome = self._core.record(raw_bytes)
            write(directory / "result.json", result(self._core, outcome))
            if self._core.terminal:
                write(self.directory / "report.json", self._core.report())
            self._pending = None
            self._poisoned = False
            return deepcopy(outcome)


def replay(root, directory):
    """Read only. An incomplete tail is terminal, never a resume instruction.

    A complete receipt without result can be reinterpreted for inspection only.
    Raw bytes without a receipt may be partial and are never decoded/accounted.
    Malformed/tampered files raise; they are not silently repaired or skipped.
    """
    root, directory = Path(root), safe_path(directory)
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()) or path.is_file() and path.stat().st_nlink != 1:
            raise ValueError("Linked or nonregular capture")
    names = {p.name for p in directory.iterdir()}
    if not {"manifest.json", "imports.json", "events"} <= names or names - {
            "manifest.json", "imports.json", "events", "report.json"}:
        raise ValueError("Incomplete or unexpected journal root")
    manifest, records = read(directory / "manifest.json"), read(directory / "imports.json")
    mode = manifest["source"]["mode"]
    expected_records, provenance = source(root, records if mode == "fixture_unverified" else None, mode)
    expected = {"version": VERSION, "mode": "offline_fixture", "simulation_only": True,
        "snapshot": snapshot(root), "imports_sha256": panel.sha256_json(expected_records),
        "source": provenance, "fixture_threshold_usd": manifest["fixture_threshold_usd"],
        "automatic_retries": 0, "resume_allowed": False, "live_calls": 0}
    if guard._json_bytes(manifest) != guard._json_bytes(expected) or records != expected_records:
        raise ValueError("Manifest/import/protocol binding differs")
    core = panel.Rehearsal(root, records, mode="offline_fixture",
                           fixture_threshold_usd=manifest["fixture_threshold_usd"])
    events = sorted((directory / "events").iterdir())
    if len(events) > 453 or any(not p.is_dir() or p.name != f"{i:04d}" for i, p in enumerate(events, 1)):
        raise ValueError("Missing, duplicate or unexpected event sequence")
    status = "capture_prefix_ended"
    for index, event in enumerate(events):
        if core.terminal:
            raise ValueError("Event after terminal stop")
        names = {p.name for p in event.iterdir()}
        order = ["reservation.json", "payload.json", "raw.bin", "receipt.json", "result.json"]
        if names not in [set(order[:i]) for i in range(6)] or any(not p.is_file() for p in event.iterdir()):
            raise ValueError("Orphan, reordered or unexpected capture file")
        before = core.index
        request = core.prepare()
        if "reservation.json" not in names:
            status = "interrupted_before_reservation"
        else:
            if guard._json_bytes(read(event / "reservation.json")) != guard._json_bytes(reservation(core, before, request)):
                raise ValueError("Request/context/skipped-row binding differs")
            if request is None:
                if names != {"reservation.json"}:
                    raise ValueError("Payload after schedule completion")
                status = "terminal_reconstructed"
                continue
            if "payload.json" in names and (event / "payload.json").read_bytes() != guard._json_bytes(request["payload"]):
                raise ValueError("Payload bytes differ")
            if "receipt.json" not in names:
                status = "interrupted_unconfirmed_reply"
            else:
                raw = (event / "raw.bin").read_bytes()
                receipt = {"sha256": digest(raw), "bytes": len(raw), "complete_supplied_bytes": True,
                           "http_delivery_tested": False}
                if guard._json_bytes(read(event / "receipt.json")) != guard._json_bytes(receipt):
                    raise ValueError("Raw-byte receipt differs")
                outcome = core.record(raw)
                if "result.json" not in names:
                    status = "captured_reply_reconstructed_without_result"
                else:
                    if guard._json_bytes(read(event / "result.json")) != guard._json_bytes(result(core, outcome)):
                        raise ValueError("Reconstructed result/accounting differs")
                    status = "terminal_reconstructed" if core.terminal else "capture_prefix_ended"
                    continue
        if index != len(events) - 1:
            raise ValueError("Event after incomplete tail")
    report = core.report()
    if (directory / "report.json").exists():
        if status != "terminal_reconstructed" or read(directory / "report.json") != report:
            raise ValueError("Saved report does not match a terminal replay")
        status = "complete_verified"
    return {"version": VERSION, "replay_status": status, "read_only": True,
        "resume_allowed": False, "simulation_only": True, "live_calls": 0,
        "unresolved_fixture_reservation": core.pending is not None,
        "source": provenance, "events": len(events), "report": report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("replay",))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    value = replay(Path(__file__).resolve().parents[1], args.directory)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
