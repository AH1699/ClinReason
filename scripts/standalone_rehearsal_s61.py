"""Durable fixture-only transport integration and read-only replay for S60.

Only built-in simulated connections; no key, external factory, live or resume API.
Reuse the S46 capture protections without reopening any historical experiment.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import threading

from scripts import standalone_engine_s61 as engine
from scripts import mixed_transport_s53 as fake

pilot, capture, guard = engine.pilot, engine.capture, engine.guard
Fixture = fake.Fixture
FILES = (engine.PLAN, "scripts/standalone_engine_s61.py", "scripts/standalone_rehearsal_s61.py",
         "tests/test_standalone_rehearsal_s61.py", "scripts/transport_s46.py",
         "scripts/minimax_accounting_s46.py", "scripts/mixed_transport_s53.py",
         "benchmark/workflow_s38.py", "benchmark/run_guard_s37.py", "benchmark/usage_s39.py",
         "benchmark/spending_s40.py", capture.POLICY, engine.workflow.ROSTER, engine.workflow.mix.PLAN)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return capture.strict_json(path.read_bytes())


def write(path, value):
    guard._write_exclusive(path, guard._json_bytes(value))


def safe_directory(root, path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked output path")
    roots = ((root / "work").resolve(), Path(tempfile.gettempdir()).resolve(), Path("/private/tmp"))
    if not any(path.is_relative_to(p) and path != p for p in roots):
        raise ValueError("Rehearsals belong in private work or a temporary directory")
    return path


def snapshot(root):
    return {"version": engine.VERSION, "s60_manifest_sha256": pilot.sha256_json(pilot.verify(root)),
        "policy": engine.policy(root),
        "files": {p: digest(pilot.public_path(root, p).read_bytes()) for p in FILES},
        "fixture_model_specs": engine.workflow.design(root)["candidates"] + engine.workflow.design(root)["judges"]}


def reservation(core, before, request):
    row, context = request["row"], request["context"]
    return {"row": row, "context_sha256": pilot.sha256_json(context),
        "payload_sha256": digest(guard._json_bytes(context["payload"])),
        "skipped_jobs": {r["id"]: core.outcomes[r["id"]] for r in core.rows[before:core.index]},
        "delivery": "reserved_before_simulated_connection", "simulation_only": True}


def capture_hashes(directory):
    paths = sorted(directory.iterdir())
    if any(p.is_symlink() or not p.is_file() or p.stat().st_nlink != 1 or p.name not in fake.CAPTURE_FILES for p in paths):
        raise ValueError("Unexpected or linked capture artifact")
    return {p.name: digest(p.read_bytes()) for p in paths}


def settled(core, outcome, result, directory):
    return {"outcome": outcome, "category": result["category"], "accounting": result["accounting"],
        "capture_hashes": capture_hashes(directory), "terminal": core.terminal,
        "monitored_ticks": core.monitored, "unknown_attempts": core.unknown,
        "closed_candidate_models": sorted(core.closed_candidates)}


class Rehearsal:
    def __init__(self, root, directory, *, mode, fixture_threshold_usd="1.00"):
        if mode != "offline_transport_fixture":
            raise ValueError("No live mode in S61")
        self.root = Path(root)
        self.directory = safe_directory(self.root, directory)
        self.core = engine.Engine(self.root, mode=mode, fixture_threshold_usd=fixture_threshold_usd)
        frozen = snapshot(self.root)
        self.protocol = pilot.sha256_json(frozen)
        self.input_pins = {**self.core.parent["files"], **frozen["files"],
                           pilot.MANIFEST: digest((self.root / pilot.MANIFEST).read_bytes())}
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        write(self.directory / "manifest.json", {"snapshot": frozen, "protocol_sha256": self.protocol,
            "fixture_threshold_usd": fixture_threshold_usd, "simulation_only": True, "live_calls": 0,
            "resume_allowed": False})
        (self.directory / "events").mkdir(mode=0o700)
        guard._sync_dir(self.directory)
        self._lock, self._poisoned, self._closed, self._event = threading.Lock(), False, False, 0
        self.last_connection = None

    def step(self, fixture):
        with self._lock:
            if self._poisoned:
                raise ValueError("Interrupted writer; no retry or resume")
            if self._closed:
                return None
            if type(fixture) is not Fixture:
                raise ValueError("Explicit built-in Fixture required, never a connection callable")
            fixture.check()
            fixture = deepcopy(fixture)
            self._poisoned = True
            if any(digest(pilot.public_path(self.root, p).read_bytes()) != expected
                   for p, expected in self.input_pins.items()):
                raise ValueError("Inputs changed during rehearsal; no retry or resume")
            before = self.core.index
            request = self.core.prepare()
            if request is None:
                write(self.directory / "report.json", self.core.report())
                self._closed, self._poisoned = True, False
                return None
            self._event += 1
            directory = self.directory / "events" / f"{self._event:04d}"
            directory.mkdir(mode=0o700)
            guard._sync_dir(directory.parent)
            write(directory / "reservation.json", reservation(self.core, before, request))
            context = request["context"]
            write(directory / "payload.json", context["payload"])
            transport = capture.CaptureJournal(self.root, directory / "transport", 1, self.protocol, "offline_fixture")
            self.last_connection = None
            def factory(host, *, timeout):
                if host != capture.ENDPOINTS[context["provider"]][0] or timeout != transport.policy["socket_timeout_seconds"]:
                    raise ValueError("Unexpected fixture endpoint or timeout")
                if fixture.fault == "connect_timeout":
                    raise TimeoutError("simulated timeout")
                self.last_connection = fake._Connection(fixture)
                return self.last_connection
            result = transport.exchange(context["provider"], context["payload"], self.core.decode,
                credential="S61-FIXTURE-ONLY", connection_factory=factory)
            raw_path = directory / "transport/0001.raw.bin"
            raw = raw_path.read_bytes() if raw_path.exists() else b""
            outcome = self.core.consume(result, raw)
            write(directory / "result.json", settled(self.core, outcome, result, directory / "transport"))
            if self.core.terminal:
                write(self.directory / "report.json", self.core.report())
                self._closed = True
            self._poisoned = False
            return {"event": self._event, "outcome": outcome, "terminal": self.core.terminal,
                    "simulation_only": True, "live_calls": 0}


def reconstruct_capture(core, directory, protocol):
    """Check durable capture bindings, then reinterpret only complete 2xx bodies."""
    files = capture_hashes(directory)
    required = {"run.json", "0001.attempt.json", "0001.payload.json", "0001.capture.json", "0001.accounting.json"}
    if not required <= set(files) or ("0001.accepted.json" in files) == ("0001.rejected.json" in files):
        return None
    row = core.pending
    context = core.contexts[row["id"]]
    payload = context["payload"]
    if (read(directory / "run.json") != {"mode": "offline_fixture", "automatic_retries": 0,
            "max_attempts": 1, "protocol_sha256": protocol, "resume_allowed": False, "costs_are_simulated": True}
            or read(directory / "0001.attempt.json") != {"sequence": 1, "provider": context["provider"],
                "model": context["model"], "protocol_sha256": protocol,
                "payload_sha256": digest(guard._json_bytes(payload)), "delivery": "reserved_before_connection",
                "prospective_cost_bound": None, "automatic_retries": 0, "fixture_only": True}
            or (directory / "0001.payload.json").read_bytes() != guard._json_bytes(payload)):
        raise ValueError("Capture request/protocol binding differs")
    meta = read(directory / "0001.capture.json")
    raw = (directory / "0001.raw.bin").read_bytes() if "0001.raw.bin" in files else b""
    if (meta["bytes_saved"] != len(raw) or meta["mode"] != "offline_fixture" or meta["fixture_only"] is not True
            or meta["body_sha256"] != (digest(raw) if meta["delivery"] == "response_received" else None)):
        raise ValueError("Capture body binding differs")
    category, parsed = meta["category"], None
    spec = core.model_specs[context["provider"], context["model"]]
    account = capture.account(None, spec, payload)
    if category in fake.BODY_CATEGORIES:
        if type(meta["status"]) is not int or not 200 <= meta["status"] < 300 or meta["body_eof"] is not True:
            raise ValueError("Incomplete/non-2xx response cannot enter decoder")
        expected = "json_format"
        try:
            raw_json = capture.strict_json(raw)
            account = capture.account(raw_json, spec, payload)
            expected = "model_identity"
            if not isinstance(raw_json, dict) or raw_json.get("model") != context["model"]:
                raise ValueError("Identity mismatch")
            expected = "usage_accounting"
            if account["status"] == "unknown":
                raise ValueError("Unknown usage")
            expected = "response_validation"
            parsed = core.decode(raw_json)
            expected = "accepted"
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, UnicodeDecodeError):
            pass
        if expected != category:
            raise ValueError("Reconstructed capture category differs")
    elif "0001.accepted.json" in files:
        raise ValueError("Failed transport cannot contain an accepted reply")
    if read(directory / "0001.accounting.json") != account:
        raise ValueError("Reconstructed accounting differs")
    if category == "accepted":
        if read(directory / "0001.accepted.json") != {"result": parsed, "raw_sha256": digest(raw)}:
            raise ValueError("Accepted-result binding differs")
    else:
        if read(directory / "0001.rejected.json") != {"category": category, "exception_text_retained": False,
                                                       "charge_may_have_occurred": True, "retry": False}:
            raise ValueError("Rejection marker differs")
    return {"category": category, "accepted": category == "accepted", "result": parsed, "accounting": account}, raw


def replay(root, directory):
    root = Path(root)
    directory = safe_directory(root, directory)
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()) or path.is_file() and path.stat().st_nlink != 1:
            raise ValueError("Linked or nonregular journal artifact")
    names = {p.name for p in directory.iterdir()}
    if not {"manifest.json", "events"} <= names or names - {"manifest.json", "events", "report.json"}:
        raise ValueError("Unexpected/incomplete journal root")
    manifest = read(directory / "manifest.json")
    frozen = snapshot(root)
    protocol = pilot.sha256_json(frozen)
    expected = {"snapshot": frozen, "protocol_sha256": protocol, "fixture_threshold_usd": manifest["fixture_threshold_usd"],
                "simulation_only": True, "live_calls": 0, "resume_allowed": False}
    if manifest != expected:
        raise ValueError("Journal source/protocol changed")
    core = engine.Engine(root, mode="offline_transport_fixture", fixture_threshold_usd=manifest["fixture_threshold_usd"])
    events = sorted((directory / "events").iterdir())
    if len(events) > 480 or any(not p.is_dir() or p.name != f"{i:04d}" for i, p in enumerate(events, 1)):
        raise ValueError("Event sequence gap or invalid entry")
    partial = None
    for event in events:
        if partial is not None or core.terminal:
            raise ValueError("Event after stop or interrupted tail")
        names = {p.name for p in event.iterdir()}
        order = ["reservation.json", "payload.json", "transport", "result.json"]
        if names not in [set(order[:i]) for i in range(5)]:
            raise ValueError("Orphan or reordered event files")
        before = core.index
        request = core.prepare()
        if request is None:
            raise ValueError("Unexpected event after schedule end")
        partial = "interrupted_before_reservation"
        if "reservation.json" not in names:
            continue
        if read(event / "reservation.json") != reservation(core, before, request):
            raise ValueError("Reservation/context binding differs")
        partial = "interrupted_before_payload"
        if "payload.json" not in names:
            continue
        if (event / "payload.json").read_bytes() != guard._json_bytes(request["context"]["payload"]):
            raise ValueError("Payload bytes differ")
        partial = "interrupted_before_complete_capture"
        if "transport" not in names:
            continue
        captured = reconstruct_capture(core, event / "transport", protocol)
        if captured is None:
            if "result.json" in names:
                raise ValueError("Settled result without complete capture")
            continue
        result, raw = captured
        outcome = core.consume(result, raw)
        partial = "captured_reply_reconstructed_without_result"
        if "result.json" not in names:
            continue
        if read(event / "result.json") != settled(core, outcome, result, event / "transport"):
            raise ValueError("Reconstructed result/accounting differs")
        partial = None
    report_path = directory / "report.json"
    if report_path.exists():
        if partial is not None:
            raise ValueError("Report after incomplete event")
        if not core.terminal and core.prepare() is not None:
            raise ValueError("Report before a terminal state")
        if read(report_path) != core.report():
            raise ValueError("Saved report differs from reconstructed state")
    return {"version": engine.VERSION, "protocol_sha256": protocol, "read_only": True, "simulation_only": True, "live_calls": 0,
            "resume_allowed": False, "events": len(events), "incomplete_tail": partial,
            "report_verified": report_path.exists(), "report": core.report()}


def next_fixture(core):
    """Built-in arbitrary plumbing data, not model answers or clinical judgments."""
    row = next((r for r in core.rows[core.index:] if not (
        r["kind"] == "candidate" and core.provider(r)["model"] in core.closed_candidates)
        and all(core.outcomes.get(d, {}).get("status") == "accepted" for d in r["dependencies"])), None)
    if row is None or core.terminal:
        return Fixture()
    context = core.context(row)
    if row["kind"] == "candidate":
        text = "Synthetic fixture reply, not clinical advice." if core.cells[row["cell_id"]]["language"] == "en" else "这是模拟回复，不是模型成绩或医疗建议。"
    else:
        packet = context["packet"]
        stage = packet["scoring_stage"]
        value = {"criterion_assessments": [{"stage_id": stage, "requirement_index": a["requirement_index"],
            "status": "met", "response_evidence": packet["transcript"][-1]["content"],
            "rationale": "Mechanical fixture only."} for a in packet["criterion_anchors"]], "critical_errors": []}
        if row.get("control_key", "").endswith("__unsafe"):
            error = packet["turn_labels"][0]["critical_errors"][0]
            value["critical_errors"] = [{"stage_id": stage, "error_id": error["id"], "severity": error["severity"],
                                          "rationale": "Mechanical fixture only."}]
        if stage == "update":
            value["dimension_observations"] = [{"dimension": d, "decision": "no_distinct_failure", "response_evidence": "",
                "new_fact": "Fixture update.", "independent_consequence_or_failure": "", "overlap_note": "Fixture only."}
                for d in ("safety", "revision")]
        text = json.dumps(value, ensure_ascii=False)
    raw = {"model": context["model"], "status": "completed", "service_tier": "standard"}
    if context["provider"] == "gemini":
        raw["steps"] = [{"type": "model_output", "content": [{"type": "text", "text": text}]}]
        raw["usage"] = {"total_input_tokens": 7, "total_output_tokens": 20, "total_thought_tokens": 22,
                        "total_tokens": 49, "total_cached_tokens": 0, "total_tool_use_tokens": 0}
    else:
        raw["choices"] = [{"finish_reason": "stop", "message": {"content": text, "reasoning_content": "FIXTURE_REASONING_NOT_FOR_HISTORY"}}]
        raw["usage"] = {"prompt_tokens": 7, "completion_tokens": 42, "total_tokens": 49,
                        "prompt_tokens_details": {"cached_tokens": 0}}
    return Fixture(guard._json_bytes(raw))


def public_summary(value):
    report = value["report"]
    return {"version": engine.VERSION, "simulation_only": True, "live_calls": 0, "measured_model_scores": 0,
        "protocol_sha256": value["protocol_sha256"], "events": value["events"],
        "read_only_replay_verified": value["report_verified"], "incomplete_tail": value["incomplete_tail"],
        "terminal": report["terminal"], "expected_conversations": 64,
        "complete_fixture_first_conversations": sum(c["first"]["score"] is not None for c in report["conversations"]),
        "complete_fixture_repeat_conversations": sum(c["repeat"]["score"] is not None for c in report["conversations"]),
        "outcomes": report["outcomes"], "unresolved_reservations": report["unresolved_reservations"],
        "unknown_simulated_cost_attempts": report["unknown_simulated_cost_attempts"],
        "new_families": 0, "clinical_validation": False, "paid_execution_ready": False,
        "next": ["Select prospective live control/technical failure gates and freeze settings.",
                 "Verify current availability/prices and seek fresh bounded export/spending approval."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("simulate", "replay"))
    parser.add_argument("directory", nargs="?", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "simulate":
        if args.directory is not None:
            parser.error("simulate uses a new temporary directory; no supplied records")
        with tempfile.TemporaryDirectory(prefix="clinreason-s61-") as folder:
            writer = Rehearsal(root, Path(folder).resolve() / "run", mode="offline_transport_fixture")
            while writer.step(next_fixture(writer.core)) is not None:
                pass
            value = replay(root, writer.directory)
            value["protocol_sha256"] = writer.protocol
    else:
        if args.directory is None:
            parser.error("replay requires a private journal directory")
        value = replay(root, args.directory)
        value["protocol_sha256"] = read(args.directory / "manifest.json")["protocol_sha256"]
    print(json.dumps(public_summary(value) if args.summary else value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
