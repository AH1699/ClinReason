"""Offline-only preparation and captured transport rehearsal; no live dispatcher.

Never reads credentials. Public output contains counts/hashes, not saved replies.
The future paid adapter must freeze and authorize its own journal/admission code.
"""

import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile

from benchmark import workflow_s38 as workflow
from benchmark.spending_s40 import monitoring_delta, TICKS_PER_USD
from scripts import evidence_refs_s65 as refs, evidence_refs_s64 as old_refs
from scripts import standalone_pilot_s60 as pilot, standalone_rehearsal_s61 as fixtures
from scripts import audit_standalone_s63 as historical
from scripts import transport_s46 as capture

PLAN = "config/compact_feasibility_s65_v1.json"
FREEZE = "config/compact_feasibility_s65_frozen_v1.json"
FILES = (PLAN, "scripts/evidence_refs_s65.py", "scripts/compact_feasibility_s65.py",
    "scripts/evidence_refs_s64.py", "scripts/audit_standalone_s63.py",
    "tests/test_evidence_refs_s65.py", "tests/test_compact_feasibility_s65.py",
    "data/audit/s64_evidence_reference_prototype.json")


def read(path):
    return capture.strict_json(Path(path).read_bytes())


def policy(root):
    value = read(root / PLAN)
    if (value["live_call_allowance"] != 0 or value["maximum_future_requests"] != 16
            or value["automatic_retries"] != 0 or value["resume_allowed"] is not False
            or value["max_in_flight"] != 1 or value["output_limit"] != 32768
            or value["status"] != "offline_preparation_not_live_authorization"):
        raise ValueError("Changed offline scope; no implicit live admission")
    return value


def snapshot(root):
    parent = historical.live.snapshot(root)
    if parent != read(root / historical.live.FREEZE):
        raise ValueError("Historical freeze changed")
    return {"version": policy(root)["version"], "mode": "offline_preparation",
        "parent_s62_sha256": pilot.sha256_json(parent),
        "files": {p: hashlib.sha256(pilot.public_path(root, p).read_bytes()).hexdigest() for p in FILES}}


def public_controls(root):
    spec, catalog, _, _ = pilot.inputs(root)
    packets, records = pilot.controls(root, catalog)
    records = {r["key"]: r for r in records}
    result = [{"id": key, "kind": "control", "packet": packets[key],
               "expected_error": records[key]["hypothesized_error_id"]}
              for key in policy(root)["control_keys"]]
    return spec, catalog, result


def source_inputs(root, directory):
    """Replay and hash-check the closed run before reading its three source packets."""
    spec, catalog, controls = public_controls(root)
    result = historical.audit(root, directory, read(root / historical.live.FREEZE))
    plan = policy(root)
    if result["source_journal_sha256"] != plan["source_journal_sha256"]:
        raise ValueError("Source journal binding changed")
    evidence = read(root / "data/audit/s64_evidence_reference_prototype.json")
    accepted = {r["packet_sha256"] for r in evidence["accepted_control_packet_exercises"]}
    if any(pilot.sha256_json(r["packet"]) not in accepted for r in controls):
        raise ValueError("Selected control was not previously format-valid")
    records = {r["event"]: r for r in evidence["historical_rejected_packets"]}
    rows = list(controls)
    for event in plan["historical_source_events"]:
        packet = json.loads(read(directory / "events" / f"{event:04d}" / "payload.json")["input"])
        if pilot.sha256_json(packet) != records[event]["packet_sha256"]:
            raise ValueError("Historical source packet changed")
        rows.append({"id": f"historical-source-{event}", "kind": "source_probe", "packet": packet, "expected_error": None})
    if historical.tree_hash(root, directory) != plan["source_journal_sha256"]:
        raise ValueError("Source changed during read-only preparation")
    return spec, catalog, rows


def candidate_payload(root, spec, catalog, cell, stage, initial=None):
    history = pilot.candidate_history(catalog[cell["family_id"]]["family"], cell["language"], stage, initial)
    payload = capture.guard.candidate_payload("minimax", cell["model"], history,
        (root / spec["candidate_instruction"]).read_text(), output_limit=32768)
    payload["thinking"] = {"type": "adaptive"}
    if cell["model"] == "MiniMax-M3.1-Flash":
        payload.pop("service_tier")
        payload["reasoning_effort"] = "max"
    return payload


def size_readout(root, item):
    old = old_refs.judge_input(root, item["packet"])
    new = refs.judge_input(root, item["packet"])
    # Matched serialization/settings for a like-for-like FULL INPUT comparison.
    lengths = [len(json.dumps(v, ensure_ascii=False)) for v in (old, new)]
    return {"id": item["id"], "packet_sha256": pilot.sha256_json(item["packet"]),
        "language": item["packet"]["language"], "stage": item["packet"]["scoring_stage"],
        "s64_input_characters": lengths[0], "s65_input_characters": lengths[1],
        "reduction_percent": round(100 * (1-lengths[1]/lengths[0]), 2),
        "provider_request_utf8_bytes": len(capture.guard._json_bytes(refs.payload(root, item["packet"]))),
        "provider_tokens_measured": False}


class Engine:
    """Serial fixture state, independent known-cost failure lanes, global cost stop."""
    def __init__(self, root, inputs, *, mode):
        if mode != "offline_transport_fixture":
            raise ValueError("S65 has no paid runner")
        self.root, self.plan = root, policy(root)
        self.spec, self.catalog, items = inputs
        if len(items) != 6 or len({r["id"] for r in items}) != 6:
            raise ValueError("Exactly six distinct prepared packets required")
        self.items = {r["id"]: deepcopy(r) for r in items}
        self.rows = [{"id": f'{phase}__{r["id"]}', "kind": "judge", "source": r["id"], "phase": phase,
                      "provider": "gemini", "model": self.plan["judge"]["model"]}
                     for phase in ("first", "repeat") for r in items]
        for cell in self.plan["candidate_diagnostics"]:
            self.rows += [{"id": f'{cell["model"]}__{stage}', "kind": "candidate", "stage": stage,
                           "provider": "minimax", "model": cell["model"], "cell": deepcopy(cell)}
                          for stage in refs.score.STAGES]
        self.index, self.monitored, self.unknown = 0, 0, 0
        self.pending, self.stop = None, None
        self.closed, self.outcomes, self.contexts = set(), {}, {}
        self.answers, self.judgments, self.accounts = {}, {}, []

    def prepare(self):
        if self.pending is not None:
            raise ValueError("Attempt outstanding; no duplicate dispatch")
        if self.stop:
            return None
        while self.index < len(self.rows):
            row = self.rows[self.index]
            lane = "judge" if row["kind"] == "judge" else row["model"]
            if lane in self.closed:
                self.outcomes[row["id"]] = "skipped_lane_closed"
                self.index += 1
                continue
            self.stop = "local_preparation_failure"
            if row["kind"] == "judge":
                packet = self.items[row["source"]]["packet"]
                payload = refs.payload(self.root, packet)
                first = self.contexts.get("first__" + row["source"])
                if row["phase"] == "repeat" and (first is None or payload != first["payload"]):
                    raise ValueError("Repeat request changed")
            else:
                packet = None
                initial = self.answers[row["model"] + "__initial"]["text"] if row["stage"] == "update" else None
                payload = candidate_payload(self.root, self.spec, self.catalog, row["cell"], row["stage"], initial)
            if len(capture.guard._json_bytes(payload)) > self.plan["max_request_bytes"]:
                raise ValueError("Prepared request exceeds byte ceiling")
            self.pending = deepcopy(row)
            self.contexts[row["id"]] = {"payload": payload, "packet": deepcopy(packet)}
            self.stop = None
            return {"row": deepcopy(row), **deepcopy(self.contexts[row["id"]])}
        self.stop = "schedule_exhausted"
        return None

    def decode(self, raw):
        row = self.pending
        return (refs.decode(raw, row["model"], self.contexts[row["id"]]["packet"]) if row["kind"] == "judge"
                else workflow.decode_candidate(raw, "minimax", row["model"]))

    def consume(self, result, raw):
        if self.pending is None or self.stop:
            raise ValueError("No outstanding attempt")
        self.stop = "local_settlement_failure"
        row = self.pending
        self.accounts.append(deepcopy(result["accounting"]))
        delta = monitoring_delta(result["accounting"], row["provider"])["delta_ticks"]
        self.monitored += delta or 0
        if result["accepted"]:
            value = self.decode(raw)
            if value != result["result"] or delta is None:
                raise ValueError("Captured result/accounting mismatch")
            (self.judgments if row["kind"] == "judge" else self.answers)[row["id"]] = value
        self.outcomes[row["id"]] = "accepted" if result["accepted"] else "rejected"
        self.stop = None
        if delta is None:
            self.unknown += 1
            self.stop = "unknown_delivery_or_cost"
        elif not result["accepted"]:
            self.closed.add("judge" if row["kind"] == "judge" else row["model"])
        if not self.stop and self.monitored >= int(Decimal(self.plan["proposed_stop_threshold_usd"]) * TICKS_PER_USD):
            self.stop = "simulated_spend_threshold_reached"
        self.pending = None
        self.index += 1

    def report(self):
        pairs, unsafe, nonunsafe = 0, 0, 0
        for key, item in self.items.items():
            a, b = [self.judgments.get(phase + "__" + key) for phase in ("first", "repeat")]
            if a is not None and b is not None:
                pairs += workflow.vector(a) == workflow.vector(b)
            if item["kind"] == "control":
                for value in (a, b):
                    if value is None: continue
                    if item["expected_error"]:
                        unsafe += any(e["error_id"] == item["expected_error"] for e in value["critical_errors"])
                    else:
                        nonunsafe += bool(value["critical_errors"])
        return {"simulation_only": True, "live_calls": 0, "measured_model_scores": 0,
            "attempts": len(self.accounts), "terminal": self.stop, "accepted_judge_fixtures": len(self.judgments),
            "matching_fixture_repeat_vectors": pairs, "fixture_unsafe_error_matches": unsafe,
            "fixture_safe_partial_error_records": nonunsafe, "accepted_candidate_fixtures": len(self.answers),
            "unknown_simulated_cost_attempts": self.unknown,
            "skipped": sum(v.startswith("skipped") for v in self.outcomes.values()),
            "unreached": len(self.rows)-len(self.outcomes), "unsettled": self.pending is not None,
            "relevance_review": "not_performed_on_live_judgments", "clinical_validation": False,
            "live_acceptance_passed": False, "paid_execution_ready": False}


def next_fixture(core):
    """Arbitrary authored answers/statuses to exercise plumbing, NOT model output."""
    row = core.pending
    if row["kind"] == "judge":
        packet = core.contexts[row["id"]]["packet"]
        spans = [s for s in refs.catalog(packet)["spans"] if s["assistant_turn"] == len(packet["transcript"])//2]
        value = {"packet_sha256": pilot.sha256_json(packet), "evidence_version": refs.VERSION,
            "criterion_assessments": [{"stage_id": packet["scoring_stage"], "requirement_index": a["requirement_index"],
                "status": "met", "response_evidence_ref": {"first": spans[0]["id"], "last": spans[-1]["id"]},
                "rationale": "Mechanical fixture, no clinical judgment."} for a in packet["criterion_anchors"]], "critical_errors": []}
        error_id = core.items[row["source"]]["expected_error"]
        if error_id:
            error = next(e for e in packet["turn_labels"][0]["critical_errors"] if e["id"] == error_id)
            value["critical_errors"] = [{"stage_id": "update", "error_id": error_id, "severity": error["severity"], "rationale": "Fixture only."}]
        if packet["scoring_stage"] == "update":
            value["dimension_observations"] = [{"dimension": d, "decision": "no_distinct_failure",
                "response_evidence_ref": None, "new_fact": "Fixture update.",
                "independent_consequence_or_failure": "", "overlap_note": "Fixture only."} for d in ("safety", "revision")]
        return {"model": row["model"], "status": "completed", "service_tier": "standard",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}],
            "usage": {"total_input_tokens": 1000, "total_output_tokens": 300, "total_thought_tokens": 100,
                      "total_tokens": 1400, "total_cached_tokens": 0, "total_tool_use_tokens": 0}}
    return {"model": row["model"], "service_tier": "standard",
        "choices": [{"finish_reason": "stop", "message": {"content": "Offline fixture / 离线模拟回复。",
            "reasoning_content": "FIXTURE_REASONING_NOT_FOR_HISTORY"}}],
        "usage": {"prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600,
                  "completion_tokens_details": {"reasoning_tokens": 80}}}


def step(core, directory, raw, *, fault=None):
    """Only a built-in fake connection can reach the existing capture transport."""
    row = core.pending
    writer = capture.CaptureJournal(core.root, directory, 1, pilot.sha256_json(core.plan), "offline_fixture")
    writer.specs = {(s["provider"], s["model"]): s for s in core.plan["pricing"]["models"].values()}
    fixture = fixtures.Fixture(capture.guard._json_bytes(raw))
    def factory(host, *, timeout):
        if host != capture.ENDPOINTS[row["provider"]][0] or timeout != writer.policy["socket_timeout_seconds"]:
            raise ValueError("Unexpected fixture endpoint or timeout")
        if fault == "connect_timeout":
            raise TimeoutError("Simulated timeout")
        return fixtures.fake._Connection(fixture)
    result = writer.exchange(row["provider"], core.contexts[row["id"]]["payload"], core.decode,
        credential="OFFLINE_FIXTURE_NOT_A_KEY", connection_factory=factory)
    raw_path = directory / "0001.raw.bin"
    captured = capture.strict_json(raw_path.read_bytes()) if raw_path.exists() else None
    core.consume(result, captured)


def rehearse(root, inputs):
    core = Engine(root, inputs, mode="offline_transport_fixture")
    with tempfile.TemporaryDirectory(prefix="clinreason-s65-fixture-") as directory:
        while core.prepare() is not None:
            step(core, Path(directory) / f"event-{core.index:02d}", next_fixture(core))
    return {"version": core.plan["version"], "preparation_sha256": pilot.sha256_json(snapshot(root)), "report": core.report(),
        "request_sizes": [size_readout(root, item) for item in inputs[2]],
        "selected_packet_sha256": {r["id"]: pilot.sha256_json(r["packet"]) for r in inputs[2]},
        "fixture_payload_sha256": {k: pilot.sha256_json(v["payload"]) for k, v in core.contexts.items()},
        "candidate_update_hashes_are_fixture_only": True, "historical_scores_changed": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-directory", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if snapshot(root) != read(root / FREEZE):
        raise ValueError("Preparation freeze changed")
    directory = args.source_directory.absolute()
    result = rehearse(root, source_inputs(root, directory))
    source_hash = policy(root)["source_journal_sha256"]
    if historical.tree_hash(root, directory) != source_hash:
        raise ValueError("Historical journal changed during rehearsal")
    result.update(source_journal_sha256=source_hash, source_journal_unchanged=True)
    print(json.dumps(result, indent=2))
