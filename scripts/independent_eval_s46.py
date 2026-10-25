"""Prospective S45 compatibility amendment: reuse seven replies, no repeated jobs.

Preserves the stopped S45 run. The current pilot's combined allowance remains
68 attempts/$5 stop threshold: seven historical attempts, at most 61 new ones.
"""

import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import UUID

from scripts import independent_eval_s45 as old, transport_s46 as capture
from scripts.minimax_accounting_s46 import account

VERSION = "s46-m3-tier-compatibility-v1"
PLAN = "config/independent_s46_amendment_v1.json"
FREEZE = "config/independent_s46_frozen_v1.json"
SOURCE = "work/s45-runs/79978a7f-6246-4d3b-a8f2-6e6f076b2bc4"
guard, workflow, score = old.guard, old.workflow, old.score
sha256_json, read_json, write_json = old.sha256_json, old.read_json, old.write_json


def recover_prefix(root, relative=SOURCE):
    directory = old.prior._private_path(root, relative, directory=True)
    s = old.replay(root, directory)
    if (s.mode != "live" or s.protocol != old.audit(root)["protocol_sha256"] or s.index != 7
            or s.terminal != "unknown_charge" or len(s.answers) != 6 or len(s.accounts) != 7):
        raise ValueError("Expected exact stopped seven-attempt S45 prefix")
    row = s.rows[6]
    path = directory / "jobs" / old.job_id(row) / "capture"
    meta = read_json(path / "0001.capture.json")
    raw_bytes = (path / "0001.raw.bin").read_bytes()
    raw, payload = capture.strict_json(raw_bytes), read_json(path / "0001.payload.json")
    if (row["model"] != "MiniMax-M3" or row["stage"] != "initial" or row["language"] != "en"
            or meta["status"] != 200 or not meta["body_eof"] or meta["category"] != "usage_accounting"
            or meta["body_sha256"] != hashlib.sha256(raw_bytes).hexdigest()
            or raw.get("service_tier") != "default" or payload.get("service_tier") != "standard"):
        raise ValueError("Unexpected recovery response; no broad salvage")
    spec = next(r for r in workflow.design(root)["candidates"] if r["model"] == row["model"])
    estimated = account(raw, spec, payload)
    if estimated.get("monitoring_policy") != "higher_published_short_context_priority_rates_no_cache_discount":
        raise ValueError("Cannot conservatively estimate this response")
    result = workflow.decode_candidate(raw, row["provider"], row["model"])
    family = s.catalog[row["family_id"]][0]
    recovered = {"row": row, "result": result, "binding": {
        "case_version": family["version"], "case_content_hash": workflow.variant_hash(family, row["language"]),
        "answer_sha256": sha256_json(result), "raw_sha256": meta["body_sha256"],
        "payload_sha256": hashlib.sha256(guard._json_bytes(payload)).hexdigest()}}
    hashes = {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(directory.rglob("*")) if p.is_file()}
    accounts = deepcopy(s.accounts[:6]) + [estimated]
    return {"source_sha256": sha256_json(hashes), "source_protocol_sha256": s.protocol,
        "source_bank_sha256": sha256_json(s.bank()), "answers": s.bank()["answers"] + [recovered],
        "accounts": accounts, "attempts": 7,
        "monitoring_ticks": sum(old.monitoring_delta(a, r["provider"])["delta_ticks"]
                                for a, r in zip(accounts, s.rows[:7])),
        "historical_s45_unknown_unchanged": True, "new_tier_estimate": estimated}


def snapshot(root):
    paths = (PLAN, "scripts/independent_eval_s46.py", "scripts/transport_s46.py",
             "scripts/minimax_accounting_s46.py", "tests/test_independent_eval_s46.py")
    return {"version": VERSION, "s45_protocol_sha256": sha256_json(old.snapshot(root)),
            "files": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}


def audit(root):
    old.audit(root)
    if snapshot(root) != read_json(root / FREEZE):
        raise ValueError("Amendment differs from frozen inputs")
    spec = read_json(root / PLAN)
    if (spec["version"] != VERSION or spec["overall_maximum_attempts"] != 68
            or spec["maximum_new_attempts"] != 61 or spec["stop_threshold_usd"] != "5.00"
            or spec["source_directory"] != SOURCE or spec["source_attempts"] != 7
            or spec["automatic_retries"] != 0 or spec["source_monitoring_microusd"] != 32628):
        raise ValueError("Pilot scope changed")
    return {"protocol_sha256": sha256_json(snapshot(root)), "plan": spec, "live_calls": 0}


def verify_prefix(prefix, spec):
    if (prefix["source_sha256"] != spec["source_sha256"]
            or prefix["monitoring_ticks"] != spec["source_monitoring_microusd"] * 10000
            or prefix["attempts"] != spec["source_attempts"]):
        raise ValueError("Source capture or carry-forward budget changed")


class Session(old.Session):
    def initialize(self, root, directory, prefix, protocol, mode):
        self._initialize(root, directory, old.plan(root), protocol, mode, None)
        self.prefix = deepcopy(prefix)
        self.rows = self.rows[7:]  # Original row IDs 8..68; no repeat of row seven.
        self.spec["maximum_attempts"] = 61
        self.monitored = prefix["monitoring_ticks"]
        for item in prefix["answers"]:
            self._add_answer(item["row"], item["result"], item["binding"])

    def __init__(self, root, directory, prefix, protocol, mode):
        self.initialize(root, directory, prefix, protocol, mode)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        (self.directory / "jobs").mkdir(mode=0o700)
        write_json(self.directory / "manifest.json", {"version": VERSION, "protocol_sha256": protocol,
            "mode": mode, "source_sha256": prefix["source_sha256"], "source_attempts": 7,
            "source_monitoring_ticks": prefix["monitoring_ticks"], "resume_allowed": False,
            "schedule_sha256": sha256_json(self.rows)})

    def bank(self):
        return {**super().bank(), "version": VERSION, "source_sha256": self.prefix["source_sha256"]}

    def step(self, credentials, connection_factory):
        with self.lock:
            if self.read_only:
                raise guard.AdmissionBlocked("Replay cannot resume execution")
            if self.terminal or self.index == len(self.rows):
                return None
            row = self.rows[self.index]
            if row["kind"] != "candidate":
                self.seal_bank()
            reason = self.skip_reason(row)
            directory = self.directory / "jobs" / old.job_id(row)
            directory.mkdir(mode=0o700, exist_ok=False)
            guard._sync_dir(directory.parent)
            if reason:
                outcome = {"status": "skipped", "reason": reason}
                write_json(directory / "skip.json", {"row": row, **outcome})
                self.outcomes[row["sequence"]] = outcome
                self.index += 1
            else:
                self.pending, self.terminal = row, "local_failure_or_interruption"
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
            return {"original_sequence": row["sequence"], "kind": row["kind"], "model": row["model"],
                    **self.outcomes[row["sequence"]], "terminal": self.terminal,
                    "cumulative_monitoring_usd": format(Decimal(self.monitored) / old.TICKS_PER_USD, "f")}

    def report(self):
        report = super().report()
        accounts = self.prefix["accounts"] + self.accounts
        unsettled = [r for r in self.rows if (self.directory / "jobs" / old.job_id(r) / "request.json").exists()
            and not (self.directory / "jobs" / old.job_id(r) / "result.json").exists()
            and r["sequence"] not in self.recovered_sequences]
        extra = [captured_account(self.root, r, self.directory / "jobs" / old.job_id(r) / "capture") for r in unsettled]
        monitored = self.monitored + sum(old.monitoring_delta(a, r["provider"])["delta_ticks"] or 0 for a, r in zip(extra, unsettled))
        return {**report, "version": VERSION, "maximum_attempts": 68,
            "maximum_new_attempts": 61, "new_attempts": report["attempts"], "attempts": 7 + report["attempts"],
            "source_attempts": 7, "source_monitoring_microusd": self.prefix["monitoring_ticks"] // 10000,
            "historical_s45_unknown_unchanged": True, "new_tier_estimate": self.prefix["new_tier_estimate"],
            "accounting": old.usage.summarize(accounts + extra),
            "monitoring_amount_usd": format(Decimal(monitored) / old.TICKS_PER_USD, "f")}


def captured_account(root, row, path):
    spec = next(v for v in workflow.design(root)["candidates"] + workflow.design(root)["judges"]
                if v["provider"] == row["provider"] and v["model"] == row["model"])
    if not (path / "0001.capture.json").exists():
        return account(None, spec)
    meta = read_json(path / "0001.capture.json")
    if (meta["category"] not in {"accepted", "response_validation", "model_identity", "usage_accounting"}
            or type(meta["status"]) is not int or not 200 <= meta["status"] < 300 or not meta["body_eof"]):
        return account(None, spec)
    raw = (path / "0001.raw.bin").read_bytes()
    if hashlib.sha256(raw).hexdigest() != meta["body_sha256"]:
        raise ValueError("Raw usage evidence changed")
    return account(capture.strict_json(raw), spec, read_json(path / "0001.payload.json"))


def replay(root, directory, prefix, protocol):
    manifest = read_json(Path(directory) / "manifest.json")
    s = Session.__new__(Session)
    s.initialize(root, directory, prefix, protocol, manifest["mode"])
    s.read_only = True
    expected = {"version": VERSION, "protocol_sha256": protocol, "mode": s.mode,
        "source_sha256": prefix["source_sha256"], "source_attempts": 7,
        "source_monitoring_ticks": prefix["monitoring_ticks"], "resume_allowed": False,
        "schedule_sha256": sha256_json(s.rows)}
    if manifest != expected:
        raise ValueError("Continuation manifest/provenance changed")
    known = {old.job_id(r) for r in s.rows}
    if any(p.name not in known or p.is_symlink() for p in (s.directory / "jobs").iterdir()):
        raise ValueError("Unknown or linked job")
    for i, row in enumerate(s.rows):
        path = s.directory / "jobs" / old.job_id(row)
        later = any((s.directory / "jobs" / old.job_id(r)).exists() for r in s.rows[i+1:])
        if not path.exists():
            if later:
                raise ValueError("Missing prefix before recorded calls")
            break
        if s.terminal:
            raise ValueError("Dispatch after global stop")
        if (path / "skip.json").exists():
            value = {"row": row, "status": "skipped", "reason": s.skip_reason(row)}
            if value["reason"] is None or read_json(path / "skip.json") != value or {p.name for p in path.iterdir()} != {"skip.json"}:
                raise ValueError("Invalid skipped job")
            s.outcomes[row["sequence"]] = {k: value[k] for k in ("status", "reason")}
            s.index += 1
            continue
        if s.skip_reason(row):
            raise ValueError("Unsatisfied dependency")
        context = workflow.request_context(root, row, s.catalog, s.controls, s.answers)
        if read_json(path / "request.json") != {"row": row, "context_sha256": sha256_json(context)}:
            raise ValueError("Changed request context")
        cap = path / "capture"
        recovering = not (path / "result.json").exists()
        if recovering and later:
            raise ValueError("Dispatch after interruption")
        if recovering and not all((cap / p).exists() for p in ("0001.capture.json", "0001.accounting.json")):
            s.terminal = "incomplete_local_attempt_unknown_delivery"
            s.outcomes[row["sequence"]] = {"status": "interrupted", "charge": "unknown"}
            break
        meta = read_json(cap / "0001.capture.json")
        if recovering:
            accepted = meta["category"] == "accepted"
            result = {"accepted": accepted, "category": meta["category"], "accounting": read_json(cap / "0001.accounting.json"),
                      "result": read_json(cap / "0001.accepted.json")["result"] if accepted else None}
        else:
            result = read_json(path / "result.json")
        payload = (cap / "0001.payload.json").read_bytes()
        attempt = read_json(cap / "0001.attempt.json")
        raw_path = cap / "0001.raw.bin"
        raw_bytes = raw_path.read_bytes() if raw_path.exists() else b""
        if (payload != guard._json_bytes(context["payload"]) or attempt["payload_sha256"] != hashlib.sha256(payload).hexdigest()
                or attempt["protocol_sha256"] != protocol or result["category"] != meta["category"]
                or result["accounting"] != read_json(cap / "0001.accounting.json")
                or result["accounting"] != captured_account(root, row, cap)
                or meta["body_sha256"] is not None and hashlib.sha256(raw_bytes).hexdigest() != meta["body_sha256"]):
            raise ValueError("Saved response/accounting binding failed")
        if result["accepted"]:
            raw = capture.strict_json(raw_bytes)
            decoded = (workflow.decode_candidate(raw, row["provider"], row["model"]) if row["kind"] == "candidate"
                       else score.decode(raw, row["provider"], row["model"], context["packet"]))
            if (type(meta["status"]) is not int or not 200 <= meta["status"] < 300 or meta["category"] != "accepted"
                    or result["result"] != decoded or read_json(cap / "0001.accepted.json") != {"result": decoded, "raw_sha256": meta["body_sha256"]}):
                raise ValueError("Accepted response differs from raw")
        elif meta["category"] == "accepted":
            raise ValueError("Contradictory acceptance")
        s._accept(row, context, result, cap)
        s.index += 1
        if recovering:
            s.recovered_sequences.append(row["sequence"])
            s.terminal = s.terminal or "interrupted_after_capture"
            break
    if s.index == len(s.rows) and s.terminal is None:
        s.terminal = "schedule_complete"
    if (s.directory / "answer-bank.json").exists() and read_json(s.directory / "answer-bank.json") != s.bank():
        raise ValueError("Changed answer bank")
    return s


def run_live(root, run_id, authorization_note):
    checked = audit(root)
    if str(UUID(run_id)) != run_id or not authorization_note.strip():
        raise ValueError("Run identity and actual authorization evidence required")
    prefix = recover_prefix(root)
    verify_prefix(prefix, checked["plan"])
    parent = old.prior._private_path(root, "work/s46-runs", directory=True, create=True)
    relative = "work/s46-runs/" + run_id
    if subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=root, capture_output=True).returncode:
        raise ValueError("Private output must be ignored")
    if (parent / run_id).exists():
        raise ValueError("Run directory exists")
    consumed = old.prior._private_path(root, "work/s46-consumed-sources", directory=True, create=True)
    # One continuation allowance per source prefix, even with another UUID.
    write_json(consumed / (prefix["source_sha256"] + ".json"), {
        "source_sha256": prefix["source_sha256"], "run_id": run_id,
        "protocol_sha256": checked["protocol_sha256"], "maximum_new_attempts": 61})
    s = Session(root, parent / run_id, prefix, checked["protocol_sha256"], "live")
    write_json(s.directory / "authorization.json", {"authorization_evidence": authorization_note,
        "scope": "Only 61 unattempted jobs; total pilot remains68/$5; no repeated requests or budget reset"})
    keys = {}
    try:
        for provider in {r["provider"] for r in s.rows}:
            keys[provider] = old.prior.read_setting(root / ".env.local", old.prior.KEY_NAMES[provider], secret=True)
        while s.terminal is None:
            if sha256_json(snapshot(root)) != checked["protocol_sha256"]:
                raise ValueError("Amendment changed during execution")
            progress = s.step(keys, old.prior.create_tls_connection)
            if progress:
                print(json.dumps(progress), flush=True)
    except BaseException:
        s.terminal = "local_failure_or_interruption"
        raise guard.AdmissionBlocked("Amendment stopped; retained jobs must not be retried") from None
    finally:
        keys.clear()
        saved = replay(root, s.directory, prefix, checked["protocol_sha256"])
        saved.terminal = saved.terminal or s.terminal
        s = saved
        s.seal_bank()
        write_json(s.directory / "report.json", s.report())
    return s.report()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prefix", "snapshot", "audit", "run", "report"))
    parser.add_argument("--run-id")
    parser.add_argument("--authorization-note", default="")
    parser.add_argument("--directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "prefix":
            prefix = recover_prefix(root)
            result = {k: prefix[k] for k in ("source_sha256", "source_protocol_sha256", "source_bank_sha256", "monitoring_ticks", "new_tier_estimate")}
        elif args.command == "snapshot":
            result = snapshot(root)
        elif args.command == "audit":
            result = audit(root)
        elif args.command == "run":
            result = run_live(root, args.run_id, args.authorization_note)
            result = {k: result[k] for k in ("terminal", "complete", "attempts", "new_attempts", "accepted_answer_stages", "monitoring_amount_usd")}
        else:
            checked, prefix = audit(root), recover_prefix(root)
            verify_prefix(prefix, checked["plan"])
            directory = old.prior._private_path(root, args.directory, directory=True)
            result = replay(root, directory, prefix, checked["protocol_sha256"]).report()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "run" and not result["complete"]:
            parser.exit(1, "S46 preserved partial results; no automatic retry.\n")
    except Exception:
        parser.exit(2, "S46 blocked/stopped. Inspect local captures; no automatic retry.\n")


if __name__ == "__main__":
    main()
