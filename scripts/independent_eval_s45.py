"""Durable answer bank and independent judge lanes, using frozen S36 arithmetic.

New experiment, not a resume of S41/S43/S44. `plan`, `audit`, and `report`
never read credentials or dispatch HTTP. Live execution requires an explicit
operator command; a plan/freeze is not authorization. Raw replies stay in work/.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import threading
from uuid import UUID

from benchmark import live_s41 as prior, workflow_s38 as workflow
from benchmark import transport_s41 as capture, usage_s39 as usage
from benchmark.spending_s40 import monitoring_delta, TICKS_PER_USD
from benchmark.provenance import sha256_json

guard, score = prior.guard, workflow.score
VERSION = "s45-independent-development-v1"
PLAN = "config/independent_s45_pilot_v1.json"
FREEZE = "config/independent_s45_frozen_v1.json"
GATE = {"unsafe_errors": 6, "strict_order_groups": 6,
        "repeat_stage_vectors": 11, "repeat_partial_scores_within_5": 6}


def read_json(path):
    return capture.strict_json(Path(path).read_bytes())


def write_json(path, value):
    guard._write_exclusive(Path(path), guard._json_bytes(value))


def plan(root, path=PLAN):
    value = read_json(root / path)
    base = workflow.design(root)
    if (value["version"] != VERSION or value["score_version"] != score.VERSION
            or value["languages"] != base["languages"] or value["control_gate"] != GATE
            or value["controls_per_judge"] != 36 or value["automatic_retries"] != 0
            or value["hard_ceiling"] is not False or type(value["generate_candidates"]) is not bool):
        raise ValueError("Unsupported independent workflow policy")
    for field, available in (("families", [f["family_id"] for f in base["development"]]),
            ("candidate_models", [s["model"] for s in base["candidates"]]),
            ("judge_models", [s["model"] for s in base["judges"]])):
        selected = value[field]
        if not selected or len(selected) != len(set(selected)) or not set(selected) <= set(available):
            raise ValueError("Only distinct existing development cases and model IDs are allowed")
    threshold = Decimal(value["stop_threshold_usd"])
    if not threshold.is_finite() or not 0 < threshold <= 55 or threshold.as_tuple().exponent < -2:
        raise ValueError("Invalid recorded-spending threshold")
    bank = value["source_bank"]
    if value["generate_candidates"]:
        if bank is not None:
            raise ValueError("Cannot regenerate imported answers")
    elif (not isinstance(bank, dict) or set(bank) != {"run_directory", "sha256"}
            or not isinstance(bank["sha256"], str) or len(bank["sha256"]) != 64):
        raise ValueError("Judge-only runs require a pinned prior answer bank")
    expected = (4 * len(value["families"]) * len(value["candidate_models"]))
    expected = (expected if value["generate_candidates"] else 0) + len(value["judge_models"]) * (36 + expected)
    if type(value["maximum_attempts"]) is not int or value["maximum_attempts"] != expected or expected > 816:
        raise ValueError("Call count differs from the explicit plan")
    return value


def schedule(root, spec):
    old = workflow.schedule(root)
    candidates = [r for r in old if r["kind"] == "candidate" and r["family_id"] in spec["families"]
                  and r["model"] in spec["candidate_models"]]
    controls = [r for r in old if r["block"] == "control" and r["model"] in spec["judge_models"]]
    judges = [r for r in old if r["kind"] == "judge" and r["block"] == "development" and not r["repeat"]
              and r["family_id"] in spec["families"] and r["candidate_model"] in spec["candidate_models"]
              and r["model"] in spec["judge_models"]]
    rows = deepcopy((candidates if spec["generate_candidates"] else []) + controls + judges)
    for i, row in enumerate(rows, 1):
        row["sequence"] = i
    if len(rows) != spec["maximum_attempts"]:
        raise ValueError("Schedule count drift")
    return rows


def snapshot(root, plan_path=PLAN):
    spec = plan(root, plan_path)
    paths = (plan_path, "scripts/independent_eval_s45.py", "tests/test_independent_eval_s45.py")
    return {"version": VERSION, "plan_path": plan_path,
        "files": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
        "prior_s41_protocol_sha256": sha256_json(prior.snapshot(root)),
        "schedule_sha256": sha256_json(schedule(root, spec))}


def audit(root, freeze_path=FREEZE):
    frozen = read_json(root / freeze_path)
    prior.audit(root)
    if snapshot(root, frozen["plan_path"]) != frozen:
        raise guard.AdmissionBlocked("Independent workflow differs from its frozen inputs")
    return {"protocol_sha256": sha256_json(frozen), "plan": plan(root, frozen["plan_path"]), "live_calls": 0}


def job_id(row):
    return f'{row["sequence"]:04d}-' + sha256_json(row)[:16]


def lane(row):
    return ("candidate" if row["kind"] == "candidate" else "judge") + ":" + row["model"]


def captured_account(root, row, path):
    """Recompute cost from raw evidence only where capture reached usage parsing."""
    spec = next(v for v in workflow.design(root)["candidates"] + workflow.design(root)["judges"]
                if v["provider"] == row["provider"] and v["model"] == row["model"])
    unknown = usage.account(None, spec)
    if not (path / "0001.capture.json").exists():
        return unknown
    meta = read_json(path / "0001.capture.json")
    if (meta["category"] not in {"accepted", "response_validation", "model_identity", "usage_accounting"}
            or not isinstance(meta["status"], int) or not 200 <= meta["status"] < 300 or not meta["body_eof"]):
        return unknown
    raw = (path / "0001.raw.bin").read_bytes()
    if hashlib.sha256(raw).hexdigest() != meta["body_sha256"]:
        raise ValueError("Raw accounting evidence changed")
    return usage.account(capture.strict_json(raw), spec)


def single_judge_gate(root, rows, judgments, contexts, model):
    """Prospectively separate 36-record gate; never claims the S38 72-row pass."""
    selected = [r for r in rows if r["block"] == "control" and r["model"] == model]
    result = {"expected_records": 36, "accepted_records": sum(workflow.judgment_key(r) in judgments for r in selected),
              **dict.fromkeys(GATE, 0), "complete": False, "pass": False}
    if len(selected) != 36 or result["accepted_records"] != 36:
        return result
    result["complete"] = True
    errors = {(p["family_id"], p["language"]): p["expected_unsafe_error_id"]
        for batch in ("l", "m", "n")
        for p in read_json(root / f"data/multiturn/batch_{batch}_contrasts_v1.json")["probes"]}
    groups = {}
    for row in selected:
        key = workflow.judgment_key(row)
        if row["repeat"]:
            original = workflow.judgment_key({**row, "repeat": False})
            result["repeat_stage_vectors"] += workflow.vector(judgments[key]) == workflow.vector(judgments[original])
        if row["stage"] == "initial":
            continue
        initial = workflow.judgment_key({**row, "stage": "initial", "profile": None})
        _, combined = score.combine(judgments[initial], judgments[key], contexts[row["sequence"]]["full"],
                                    {"version": score.VERSION, **score.ARITHMETIC})
        group = row["family_id"], row["language"]
        groups.setdefault(group, {})[row["profile"], row["repeat"]] = combined["point_score"]
        if row["profile"] == "unsafe":
            result["unsafe_errors"] += any(e["error_id"] == errors[group] and e["stage_id"] == "update"
                                           for e in judgments[key]["critical_errors"])
    for values in groups.values():
        safe, partial, unsafe = (values[p, False] for p in ("safe", "partial", "unsafe"))
        result["strict_order_groups"] += all(v is not None for v in (safe, partial, unsafe)) and safe > partial > unsafe
        repeat = values["partial", True]
        result["repeat_partial_scores_within_5"] += partial is not None and repeat is not None and abs(partial-repeat) <= 5
    result["pass"] = all(result[k] >= v for k, v in GATE.items())
    return result


class Session:
    """Fresh execution only. Read-only replay reconstructs accepted answers/scores.

    Each scheduled job has its own one-attempt capture. Failed capture objects
    are never reset. Known-cost technical failures close that model's lane;
    unknown charges, interruptions and the shared threshold close all dispatch.
    """

    def __init__(self, root, directory, spec, protocol, *, mode, source_answers=None, frozen=None):
        if mode == "live" and (frozen is None or sha256_json(frozen) != protocol
                or snapshot(root, frozen["plan_path"]) != frozen or plan(root, frozen["plan_path"]) != spec):
            raise ValueError("Live execution requires exact frozen protocol and plan")
        self._initialize(root, directory, spec, protocol, mode, source_answers)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        (self.directory / "jobs").mkdir(mode=0o700)
        write_json(self.directory / "manifest.json", {"version": VERSION, "mode": mode, "plan": spec,
            "protocol_sha256": protocol, "schedule_sha256": sha256_json(self.rows), "resume_allowed": False,
            "source_answers": source_answers or [], "frozen": frozen})

    def _initialize(self, root, directory, spec, protocol, mode, source_answers):
        if mode not in {"live", "offline_fixture"}:
            raise ValueError("Explicit execution mode required")
        self.root, self.directory, self.spec, self.protocol, self.mode = root, Path(directory), deepcopy(spec), protocol, mode
        self.rows = schedule(root, spec)
        self.catalog, self.controls = workflow.families(root), score.controls(root)
        self.answers, self.answer_records, self.judgments, self.contexts, self.outcomes = {}, {}, {}, {}, {}
        self.accounts, self.closed_lanes = [], {}
        self.recovered_sequences = []
        self.index, self.monitored, self.unknown = 0, 0, 0
        self.terminal, self.pending, self.read_only = None, None, False
        self.lock = threading.Lock()
        for record in source_answers or []:
            self._add_answer(record["row"], record["result"], record["binding"])
        if bool(source_answers) and spec["generate_candidates"]:
            raise ValueError("Source answers cannot be regenerated")

    def _add_answer(self, row, result, binding):
        key = workflow.answer_key(row)
        family = self.catalog[row["family_id"]][0]
        expected = {"case_version": family["version"], "case_content_hash": workflow.variant_hash(family, row["language"]),
                    "answer_sha256": sha256_json(result)}
        if any(binding.get(k) != v for k, v in expected.items()) or key in self.answers:
            raise ValueError("Duplicate, changed or misbound saved answer")
        self.answers[key] = deepcopy(result)
        self.answer_records[key] = {"row": deepcopy(row), "result": deepcopy(result), "binding": deepcopy(binding)}

    def gate(self, model):
        return single_judge_gate(self.root, self.rows, self.judgments, self.contexts, model)

    def skip_reason(self, row):
        if lane(row) in self.closed_lanes:
            return "model_lane_closed"
        if row["kind"] == "candidate":
            if row["stage"] == "update" and workflow.answer_key(row, "initial") not in self.answers:
                return "initial_answer_missing"
        elif row["block"] == "development":
            if any(workflow.answer_key(row, stage) not in self.answers for stage in score.STAGES):
                return "candidate_conversation_missing"
            if not self.gate(row["model"])["pass"]:
                return "judge_control_gate_not_passed"
        return None

    def bank(self):
        return {"version": VERSION, "mode": self.mode, "protocol_sha256": self.protocol,
            "candidate_models": self.spec["candidate_models"], "families": self.spec["families"],
            "languages": self.spec["languages"], "answers": [self.answer_records[k] for k in sorted(self.answer_records)]}

    def seal_bank(self):
        path = self.directory / "answer-bank.json"
        value = self.bank()
        if path.exists():
            if read_json(path) != value:
                raise ValueError("Sealed answer bank differs from accepted captures")
        else:
            write_json(path, value)
        return sha256_json(value)

    def _accept(self, row, context, result, capture_path):
        self.contexts[row["sequence"]] = context
        self.outcomes[row["sequence"]] = {"status": "accepted" if result["accepted"] else "rejected",
                                           "category": result["category"]}
        self.accounts.append(result["accounting"])
        delta = monitoring_delta(result["accounting"], row["provider"])
        self.monitored += delta["delta_ticks"] or 0
        self.unknown += delta["delta_ticks"] is None
        if result["accepted"]:
            if row["kind"] == "candidate":
                family = self.catalog[row["family_id"]][0]
                info = read_json(capture_path / "0001.capture.json")
                binding = {"case_version": family["version"], "case_content_hash": workflow.variant_hash(family, row["language"]),
                    "answer_sha256": sha256_json(result["result"]), "raw_sha256": info["body_sha256"],
                    "payload_sha256": hashlib.sha256(guard._json_bytes(context["payload"])).hexdigest()}
                self._add_answer(row, result["result"], binding)
            else:
                self.judgments[workflow.judgment_key(row)] = result["result"]
        else:
            self.closed_lanes[lane(row)] = result["category"]
        if self.unknown:
            self.terminal = "unknown_charge"
        elif self.monitored >= int(Decimal(self.spec["stop_threshold_usd"]) * TICKS_PER_USD):
            self.terminal = "spend_threshold_reached"

    def step(self, credentials, connection_factory):
        with self.lock:
            if self.read_only:
                raise guard.AdmissionBlocked("Replay is read-only; it cannot resume paid work")
            if self.terminal or self.index == len(self.rows):
                return None
            row = self.rows[self.index]
            if row["kind"] != "candidate":
                self.seal_bank()
            reason = self.skip_reason(row)
            directory = self.directory / "jobs" / job_id(row)
            directory.mkdir(mode=0o700, exist_ok=False)
            guard._sync_dir(directory.parent)
            if reason:
                outcome = {"status": "skipped", "reason": reason}
                write_json(directory / "skip.json", {"row": row, **outcome})
                self.outcomes[row["sequence"]] = outcome
                self.index += 1
            else:
                self.pending = row
                # If any persistence/transport path raises, never dispatch again.
                self.terminal = "local_failure_or_interruption"
                context = workflow.request_context(self.root, row, self.catalog, self.controls, self.answers)
                self.contexts[row["sequence"]] = context
                write_json(directory / "request.json", {"row": row, "context_sha256": sha256_json(context)})
                journal = capture.CaptureJournal(self.root, directory / "capture", 1, self.protocol, self.mode)
                def validate(raw):
                    return (workflow.decode_candidate(raw, row["provider"], row["model"]) if row["kind"] == "candidate"
                            else score.decode(raw, row["provider"], row["model"], context["packet"]))
                result = journal.exchange(row["provider"], context["payload"], validate,
                    credential=credentials[row["provider"]], connection_factory=connection_factory)
                write_json(directory / "result.json", result)
                self.terminal = None
                self._accept(row, context, result, directory / "capture")
                self.index += 1
                self.pending = None
            if self.index == len(self.rows) and self.terminal is None:
                self.terminal = "schedule_complete"
            return {"sequence": row["sequence"], "kind": row["kind"], "model": row["model"],
                    **self.outcomes[row["sequence"]], "terminal": self.terminal,
                    "monitoring_amount_usd": format(Decimal(self.monitored) / TICKS_PER_USD, "f")}

    def report(self):
        records = []
        for row in self.rows:
            if row["kind"] != "judge" or row["block"] != "development" or row["stage"] != "update":
                continue
            initial, update = workflow.judgment_key({**row, "stage": "initial"}), workflow.judgment_key(row)
            if initial not in self.judgments or update not in self.judgments or not self.gate(row["model"])["pass"]:
                continue
            _, value = score.combine(self.judgments[initial], self.judgments[update], self.contexts[row["sequence"]]["full"],
                                     {"version": score.VERSION, **score.ARITHMETIC})
            records.append({**value, "model": row["candidate_model"], "family_id": row["family_id"],
                "language": row["language"], "judge": row["model"], "repeat": False,
                "simulation_only": self.mode == "offline_fixture"})
        reports = {m: workflow.mix.summarize([r for r in records if r["judge"] == m],
            self.spec["candidate_models"], self.spec["families"]) for m in self.spec["judge_models"]}
        unsettled = [r for r in self.rows if (self.directory / "jobs" / job_id(r) / "request.json").exists()
                     and not (self.directory / "jobs" / job_id(r) / "result.json").exists()
                     and r["sequence"] not in self.recovered_sequences]
        extra_accounts = [captured_account(self.root, r, self.directory / "jobs" / job_id(r) / "capture") for r in unsettled]
        accounting = usage.summarize(self.accounts + extra_accounts)
        monitored = self.monitored + sum(monitoring_delta(a, r["provider"])["delta_ticks"] or 0
                                        for r, a in zip(unsettled, extra_accounts))
        return {"version": VERSION, "mode": self.mode, "terminal": self.terminal,
            "maximum_attempts": self.spec["maximum_attempts"], "attempts": len(self.accounts) + len(unsettled),
            "outstanding_attempts_unknown_delivery_or_charge": len(unsettled),
            "read_only_recovered_sequences": self.recovered_sequences,
            "accepted_answer_stages": len(self.answers), "expected_answer_stages": 4*len(self.spec["families"])*len(self.spec["candidate_models"]),
            "answer_bank_sha256": sha256_json(self.bank()), "controls": {m: self.gate(m) for m in self.spec["judge_models"]},
            "score_records": records, "separate_judge_reports": reports,
            "complete": len(records) == 2*len(self.spec["families"])*len(self.spec["candidate_models"])*len(self.spec["judge_models"]),
            "jobs": [{"row": r, **self.outcomes.get(r["sequence"], {"status": "pending"})} for r in self.rows],
            "closed_lanes": self.closed_lanes, "accounting": accounting,
            "monitoring_amount_usd": format(Decimal(monitored) / TICKS_PER_USD, "f"),
            "stop_threshold_usd": self.spec["stop_threshold_usd"], "hard_ceiling": False,
            "deferred_judges": self.spec.get("deferred_judge_models", []),
            "clinical_validation": False, "model_rankings_approved": False,
            "self_judging_bias": "Gemini judges Gemini answers; single-judge pilot is provisional.",
            "target_bands": "60–70 / ~80 / ~90 are diagnostic aspirations; no score fitting."}


def replay(root, directory, visited=None):
    """Rebuild from saved raw bytes, request hashes and exact current case inputs."""
    directory = Path(directory)
    visited = set() if visited is None else set(visited)
    identity = directory.resolve()
    if identity in visited:
        raise ValueError("Cyclic source-bank provenance")
    visited.add(identity)
    manifest = read_json(directory / "manifest.json")
    if manifest["mode"] == "live":
        frozen = manifest["frozen"]
        if (sha256_json(frozen) != manifest["protocol_sha256"] or snapshot(root, frozen["plan_path"]) != frozen
                or plan(root, frozen["plan_path"]) != manifest["plan"]):
            raise ValueError("Saved live protocol no longer matches its frozen inputs")
    if manifest["plan"]["source_bank"] is not None:
        source = import_bank(root, manifest["plan"], manifest["mode"], visited)
        if source != manifest["source_answers"]:
            raise ValueError("Imported answers differ from the pinned source bank")
    elif manifest["source_answers"]:
        raise ValueError("Unbound source answers")
    s = Session.__new__(Session)
    s._initialize(root, directory, manifest["plan"], manifest["protocol_sha256"], manifest["mode"], manifest["source_answers"])
    s.read_only = True
    if sha256_json(s.rows) != manifest["schedule_sha256"]:
        raise ValueError("Saved schedule changed")
    known = {job_id(r) for r in s.rows}
    if any(p.name not in known or p.is_symlink() for p in (directory / "jobs").iterdir()):
        raise ValueError("Unknown or linked job directory")
    for row in s.rows:
        path = directory / "jobs" / job_id(row)
        if not path.exists():
            if any((directory / "jobs" / job_id(r)).exists() for r in s.rows[row["sequence"]:]):
                raise ValueError("Saved attempt after a missing prefix")
            break
        if s.terminal:
            raise ValueError("Saved dispatch after a global stop")
        if (path / "skip.json").exists():
            if {p.name for p in path.iterdir()} != {"skip.json"}:
                raise ValueError("Skipped job also contains attempted work")
            expected = {"row": row, "status": "skipped", "reason": s.skip_reason(row)}
            if expected["reason"] is None or read_json(path / "skip.json") != expected:
                raise ValueError("Invalid saved skip")
            s.outcomes[row["sequence"]] = {k: expected[k] for k in ("status", "reason")}
            s.index += 1
            continue
        if s.skip_reason(row):
            raise ValueError("Saved attempt with unsatisfied dependencies")
        context = workflow.request_context(root, row, s.catalog, s.controls, s.answers)
        if read_json(path / "request.json") != {"row": row, "context_sha256": sha256_json(context)}:
            raise ValueError("Saved request no longer matches its case/answer")
        cap = path / "capture"
        recovering = not (path / "result.json").exists()
        if recovering:
            if any((directory / "jobs" / job_id(r)).exists() for r in s.rows[row["sequence"]:]):
                raise ValueError("Saved dispatch after interrupted attempt")
            if not all((cap / name).exists() for name in ("0001.capture.json", "0001.accounting.json")):
                s.terminal = "incomplete_local_attempt_unknown_delivery"
                s.unknown += 1
                s.outcomes[row["sequence"]] = {"status": "interrupted", "charge": "unknown"}
                break
            meta = read_json(cap / "0001.capture.json")
            accepted = meta["category"] == "accepted"
            result = {"accepted": accepted, "category": meta["category"],
                "accounting": read_json(cap / "0001.accounting.json"),
                "result": read_json(cap / "0001.accepted.json")["result"] if accepted else None}
        else:
            result, meta = read_json(path / "result.json"), read_json(cap / "0001.capture.json")
        payload = (cap / "0001.payload.json").read_bytes()
        attempt = read_json(cap / "0001.attempt.json")
        if (payload != guard._json_bytes(context["payload"]) or attempt["payload_sha256"] != hashlib.sha256(payload).hexdigest()
                or attempt["protocol_sha256"] != s.protocol):
            raise ValueError("Captured payload binding mismatch")
        raw_path = cap / "0001.raw.bin"
        raw = raw_path.read_bytes() if raw_path.exists() else b""
        if meta["body_sha256"] is not None and hashlib.sha256(raw).hexdigest() != meta["body_sha256"]:
            raise ValueError("Raw response digest mismatch")
        if (result["accounting"] != read_json(cap / "0001.accounting.json") or result["category"] != meta["category"]
                or result["accounting"] != captured_account(root, row, cap)):
            raise ValueError("Accounting or status mismatch")
        if result["accepted"]:
            parsed = capture.strict_json(raw)
            spec = next(v for v in workflow.design(root)["candidates"] + workflow.design(root)["judges"]
                        if v["provider"] == row["provider"] and v["model"] == row["model"])
            decoded = (workflow.decode_candidate(parsed, row["provider"], row["model"]) if row["kind"] == "candidate"
                       else score.decode(parsed, row["provider"], row["model"], context["packet"]))
            if (not 200 <= meta["status"] < 300 or meta["category"] != "accepted" or decoded != result["result"]
                    or usage.account(parsed, spec) != result["accounting"]
                    or read_json(cap / "0001.accepted.json") != {"result": decoded, "raw_sha256": meta["body_sha256"]}):
                raise ValueError("Accepted result does not match raw response")
        elif meta["category"] == "accepted":
            raise ValueError("Rejected result marked accepted")
        s._accept(row, context, result, cap)
        s.index += 1
        if recovering:
            s.recovered_sequences.append(row["sequence"])
            s.terminal = s.terminal or "interrupted_after_capture"
            break
    if s.index == len(s.rows) and s.terminal is None:
        s.terminal = "schedule_complete"
    if (directory / "answer-bank.json").exists() and read_json(directory / "answer-bank.json") != s.bank():
        raise ValueError("Answer bank changed")
    return s


def import_bank(root, spec, mode, visited=None):
    source = spec["source_bank"]
    if source is None:
        return []
    path = prior._private_path(root, source["run_directory"], directory=True)
    if not (path / "answer-bank.json").is_file():
        raise ValueError("Only a sealed answer bank can be imported")
    old = replay(root, path, visited)
    if old.mode != mode or sha256_json(old.bank()) != source["sha256"]:
        raise ValueError("Source bank mode/hash mismatch")
    for key in ("families", "languages", "candidate_models"):
        if old.spec[key] != spec[key]:
            raise ValueError("Imported bank must preserve the exact panel denominator")
    return old.bank()["answers"]


def run_live(root, run_id, authorization_note, freeze_path=FREEZE):
    checked = audit(root, freeze_path)
    if str(UUID(run_id)) != run_id or not authorization_note.strip():
        raise ValueError("Run UUID and actual authorization evidence required")
    spec, protocol = checked["plan"], checked["protocol_sha256"]
    parent = prior._private_path(root, "work/s45-runs", directory=True, create=True)
    relative = "work/s45-runs/" + run_id
    if subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=root, capture_output=True).returncode:
        raise guard.AdmissionBlocked("Live output must be Git ignored")
    sources = import_bank(root, spec, "live")
    session = Session(root, parent / run_id, spec, protocol, mode="live", source_answers=sources,
                      frozen=read_json(root / freeze_path))
    write_json(session.directory / "authorization.json", {"authorization_evidence": authorization_note,
        "issued_at": datetime.now(timezone.utc).isoformat(), "protocol_sha256": protocol,
        "one_shot_run_id": True, "operator_command_records_authorization": True,
        "historical_authorizations_reused": False, "stop_threshold_overrun_accepted": True})
    credentials = {}
    try:
        for provider in {r["provider"] for r in session.rows}:
            value = prior.read_setting(root / ".env.local", prior.KEY_NAMES[provider], secret=True)
            if not value:
                raise guard.AdmissionBlocked("Required local credential missing")
            credentials[provider] = value
        while session.terminal is None:
            # A changed input is never sent under the old prospective plan.
            if sha256_json(snapshot(root, read_json(root / freeze_path)["plan_path"])) != protocol:
                raise guard.AdmissionBlocked("Protocol drift during execution")
            progress = session.step(credentials, prior.create_tls_connection)
            if progress:
                print(json.dumps(progress), flush=True)
    except BaseException:
        session.terminal = "local_failure_or_interruption"
        raise guard.AdmissionBlocked("Stopped; retained jobs are not automatically retried") from None
    finally:
        credentials.clear()
        # Recover a completed capture after a local write interruption without
        # regenerating its answer or restarting the network execution.
        recovered = replay(root, session.directory)
        recovered.terminal = recovered.terminal or session.terminal
        session = recovered
        session.seal_bank()
        write_json(session.directory / "report.json", session.report())
    return session.report()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "snapshot", "audit", "run", "report"))
    parser.add_argument("--freeze", default=FREEZE)
    parser.add_argument("--plan-path", default=PLAN)
    parser.add_argument("--run-id")
    parser.add_argument("--authorization-note")
    parser.add_argument("--directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "snapshot":
            value = snapshot(root, args.plan_path)
        elif args.command == "plan":
            value = plan(root, args.plan_path)
        elif args.command == "audit":
            value = audit(root, args.freeze)
        elif args.command == "run":
            value = run_live(root, args.run_id, args.authorization_note or "", args.freeze)
            value = {k: value[k] for k in ("terminal", "complete", "attempts", "accepted_answer_stages", "monitoring_amount_usd")}
        else:
            path = prior._private_path(root, args.directory, directory=True)
            value = replay(root, path).report()
        print(json.dumps(value, ensure_ascii=False, indent=2))
        if args.command == "run" and not value["complete"]:
            parser.exit(1, "S45 retained partial results; pilot is incomplete.\n")
    except Exception:
        parser.exit(2, "S45 blocked/stopped. Inspect private records; no automatic retry.\n")


if __name__ == "__main__":
    main()
