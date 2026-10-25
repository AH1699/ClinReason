"""Fresh 52-call judge-only experiment with a verified S46 answer-bank import.

Only S47's explanation clarification changes the original judging prompts.
Scoring, control gate, saved answers and historical experiments stay unchanged.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
from uuid import UUID

from scripts import judge_observation_s47 as prior

previous, old, workflow, score = prior.previous, prior.old, prior.workflow, prior.score
capture, guard, draft = prior.capture, prior.guard, prior.draft
read_json, write_json, sha256_json = prior.read_json, prior.write_json, prior.sha256_json
VERSION = "s48-saved-bank-judge-only-v1"
PLAN = "config/judge_saved_bank_s48_v1.json"
FREEZE = "config/judge_saved_bank_s48_frozen_v1.json"
MODEL, SOURCE = prior.MODEL, prior.SOURCE
MAXIMUM, THRESHOLD = 52, 20_000_000_000


def plan(root):
    value = read_json(root / PLAN)
    expected = {"version": VERSION, "families": ["HC-MT-MEDSAFE-013"],
        "languages": ["en", "zh-Hans"], "candidate_models": old.plan(root)["candidate_models"],
        "judge_models": [MODEL], "generate_candidates": False, "maximum_attempts": MAXIMUM,
        "stop_threshold_usd": "2.00", "hard_ceiling": False, "automatic_retries": 0,
        "controls_per_judge": 36, "control_gate": old.GATE, "score_version": score.VERSION}
    if any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()):
        raise ValueError("Saved-answer experiment scope changed")
    if value["source_bank"]["run_directory"] != SOURCE:
        raise ValueError("Different answer bank")
    return value


def source(root):
    checked, prefix = previous.audit(root), previous.recover_prefix(root)
    previous.verify_prefix(prefix, checked["plan"])
    directory = old.prior._private_path(root, SOURCE, directory=True)
    state = previous.replay(root, directory, prefix, checked["protocol_sha256"])
    if (state.mode != "live" or state.report() != read_json(directory / "report.json")
            or state.bank() != read_json(directory / "answer-bank.json")):
        raise ValueError("Source does not match its saved raw responses")
    hashes = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Linked source capture")
        if path.is_file():
            hashes[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"mode": state.mode, "source_sha256": sha256_json(hashes),
        "source_protocol_sha256": state.protocol, "bank_sha256": sha256_json(state.bank()), "bank": state.bank()}


def verify_source(value, spec, mode):
    if value["mode"] != mode or value["bank"]["mode"] != mode or sha256_json(value["bank"]) != value["bank_sha256"]:
        raise ValueError("Source mode or contents changed")
    if mode == "live" and (value["bank_sha256"] != spec["source_bank"]["sha256"]
            or value["source_sha256"] != spec["source_sha256"]
            or value["source_protocol_sha256"] != spec["source_protocol_sha256"]):
        raise ValueError("Source differs from prospective pins")
    for key in ("candidate_models", "families"):
        if value["bank"][key] != spec[key]:
            raise ValueError("Source panel changed")


def jobs(root, value, mode):
    spec = plan(root); verify_source(value, spec, mode)
    state = old.Session.__new__(old.Session)
    state._initialize(root, Path("unused"), spec, "CONTEXT-ONLY", mode, value["bank"]["answers"])
    expected = {workflow.answer_key(r) for r in workflow.schedule(root) if r["kind"] == "candidate"
                and r["family_id"] in spec["families"] and r["model"] in spec["candidate_models"]}
    if set(state.answers) != expected or len(state.answers) != 16:
        raise ValueError("Exactly all 16 saved stages are required")
    selected = []
    for row in state.rows:
        if row["kind"] != "judge" or row["model"] != MODEL or row["provider"] != "gemini":
            raise ValueError("Only the declared judge may be called")
        context = workflow.request_context(root, row, state.catalog, state.controls, state.answers)
        payload = deepcopy(context["payload"])
        payload["system_instruction"] = draft.instruction(root, context["packet"])
        payload["response_format"]["schema"] = draft.schema(context["packet"])
        selected.append({"row": row, "context": {**context, "payload": payload}})
    return selected


def snapshot(root):
    paths = (PLAN, "scripts/judge_saved_bank_s48.py", "tests/test_judge_saved_bank_s48.py")
    return {"version": VERSION, "s47_protocol_sha256": prior.audit(root)["protocol_sha256"],
        "files": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
        "schedule_sha256": sha256_json(old.schedule(root, plan(root)))}


def audit(root):
    current = snapshot(root)
    if current != read_json(root / FREEZE):
        raise ValueError("Saved-bank experiment differs from freeze")
    return {"protocol_sha256": sha256_json(current), "plan": plan(root), "live_calls": 0}


def manifest(value, protocol, mode):
    if mode not in {"live", "offline_fixture"}:
        raise ValueError("Explicit execution mode required")
    return {"version": VERSION, "protocol_sha256": protocol, "mode": mode,
        "source_sha256": value["source_sha256"], "bank_sha256": value["bank_sha256"],
        "maximum_attempts": MAXIMUM, "stop_threshold_usd": "2.00", "resume_allowed": False}


def gate(root, selected, judgments):
    return old.single_judge_gate(root, [j["row"] for j in selected], judgments,
        {j["row"]["sequence"]: j["context"] for j in selected}, MODEL)


def records(root, selected, judgments, mode):
    controls, candidates = [], []
    passed = gate(root, selected, judgments)["pass"]
    for job in selected:
        row, context = job["row"], job["context"]
        if row["stage"] != "update":
            continue
        initial_row = {**row, "stage": "initial"}
        if row["block"] == "control":
            initial_row["profile"] = None
        initial, update = workflow.judgment_key(initial_row), workflow.judgment_key(row)
        if initial not in judgments or update not in judgments:
            continue
        _, combined = score.combine(judgments[initial], judgments[update], context["full"],
                                    {"version": score.VERSION, **score.ARITHMETIC})
        result = {**combined, "family_id": row["family_id"], "language": row["language"],
            "judge": MODEL, "repeat": row["repeat"], "simulation_only": mode == "offline_fixture"}
        if row["block"] == "control":
            controls.append({**result, "profile": row["profile"]})
        elif passed:
            candidates.append({**result, "model": row["candidate_model"]})
    return controls, candidates


def replay(root, directory, value, protocol, *, threshold=THRESHOLD):
    directory = Path(directory); saved = read_json(directory / "manifest.json")
    if saved != manifest(value, protocol, saved["mode"]):
        raise ValueError("Manifest or source binding changed")
    if saved["mode"] == "live" and (threshold != THRESHOLD or audit(root)["protocol_sha256"] != protocol):
        raise ValueError("Live protocol changed")
    selected = jobs(root, value, saved["mode"]); cap = directory / "capture"
    expected_run = {"mode": saved["mode"], "automatic_retries": 0, "max_attempts": MAXIMUM,
        "protocol_sha256": protocol, "resume_allowed": False, "costs_are_simulated": saved["mode"] == "offline_fixture"}
    if read_json(cap / "run.json") != expected_run:
        raise ValueError("Capture scope changed")
    allowed = re.compile(r"(00(?:0[1-9]|[1-4][0-9]|5[0-2]))\.(attempt\.json|payload\.json|raw\.bin|capture\.json|accounting\.json|accepted\.json|rejected\.json)")
    if any(p.is_symlink() or not p.is_file() or p.name != "run.json" and not allowed.fullmatch(p.name) for p in cap.iterdir()):
        raise ValueError("Unexpected capture file")
    attempts = sorted(int(p.name[:4]) for p in cap.glob("*.attempt.json"))
    if attempts != list(range(1, len(attempts) + 1)):
        raise ValueError("Missing attempt prefix")
    if any(p.name != "run.json" and int(p.name[:4]) not in attempts for p in cap.iterdir()):
        raise ValueError("Orphan capture without attempt")
    accounts, judgments, failures, stage_records = [], {}, [], []
    monitored, terminal = 0, None
    spec = next(v for v in workflow.design(root)["judges"] if v["model"] == MODEL)
    for i in attempts:
        if terminal:
            raise ValueError("Dispatch after stop")
        job = selected[i-1]; row, context = job["row"], job["context"]; stem = f"{i:04d}"
        if row["block"] == "development" and not gate(root, selected, judgments)["pass"]:
            raise ValueError("Candidate judgment before control gate passed")
        attempt = read_json(cap / (stem + ".attempt.json"))
        expected_attempt = {"sequence": i, "provider": "gemini", "model": MODEL, "protocol_sha256": protocol,
            "payload_sha256": hashlib.sha256(guard._json_bytes(context["payload"])).hexdigest(),
            "delivery": "reserved_before_connection", "prospective_cost_bound": None,
            "automatic_retries": 0, "fixture_only": saved["mode"] == "offline_fixture"}
        if (attempt != expected_attempt or read_json(directory / "contexts" / (stem + ".json")) !=
                {"row": row, "context_sha256": sha256_json(context)}):
            raise ValueError("Request binding changed")
        if not (cap / (stem + ".payload.json")).exists():
            accounts.append(previous.account(None, spec))
            terminal = "interrupted_unknown_delivery_or_charge"
            failures.append({"sequence": i, "category": terminal})
            continue
        payload = (cap / (stem + ".payload.json")).read_bytes()
        if payload != guard._json_bytes(context["payload"]):
            raise ValueError("Request body changed")
        if not all((cap / (stem + ext)).exists() for ext in (".capture.json", ".accounting.json")):
            accounts.append(previous.account(None, spec))
            terminal = "interrupted_unknown_delivery_or_charge"
            failures.append({"sequence": i, "category": terminal})
            continue
        meta = read_json(cap / (stem + ".capture.json")); raw_path = cap / (stem + ".raw.bin")
        raw_bytes = raw_path.read_bytes() if raw_path.exists() else b""
        if (meta["mode"] != saved["mode"] or meta["fixture_only"] != (saved["mode"] == "offline_fixture")
                or meta["bytes_saved"] != len(raw_bytes)):
            raise ValueError("Capture mode or byte count changed")
        if meta["body_sha256"] is not None and meta["body_sha256"] != hashlib.sha256(raw_bytes).hexdigest():
            raise ValueError("Captured response changed")
        account, raw = previous.account(None, spec), None
        if (type(meta["status"]) is int and 200 <= meta["status"] < 300 and meta["body_eof"]
                and meta["category"] in {"accepted", "response_validation", "model_identity", "usage_accounting"}):
            raw = capture.strict_json(raw_bytes)
            account = previous.account(raw, spec, context["payload"])
        if read_json(cap / (stem + ".accounting.json")) != account:
            raise ValueError("Accounting differs from raw usage")
        accounts.append(account)
        delta = old.monitoring_delta(account, "gemini")["delta_ticks"]
        monitored += delta or 0
        if meta["category"] == "accepted":
            judgment = score.decode(raw, "gemini", MODEL, context["packet"])
            if (read_json(cap / (stem + ".accepted.json")) != {"result": judgment, "raw_sha256": meta["body_sha256"]}
                    or (cap / (stem + ".rejected.json")).exists()):
                raise ValueError("Accepted judgment binding changed")
            judgments[workflow.judgment_key(row)] = judgment
            stage_records.append({"row": row, "statuses": [a["status"] for a in judgment["criterion_assessments"]],
                "critical_error_ids": [e["error_id"] for e in judgment["critical_errors"]],
                "observations": [o["decision"] for o in judgment.get("dimension_observations", [])]})
        else:
            if read_json(cap / (stem + ".rejected.json"))["category"] != meta["category"]:
                raise ValueError("Rejection binding changed")
            failure = {"sequence": i, "category": meta["category"], "http_status": meta["status"]}
            if raw is not None and meta["category"] == "response_validation":
                try:
                    parsed = score.base.parse_response(raw, "gemini")
                    failure["missing_observation_fields"] = draft.missing_observation_fields(parsed, context["packet"])
                except (ValueError, KeyError, TypeError, AttributeError):
                    failure["parseable"] = False
            failures.append(failure)
        if delta is None:
            terminal = "unknown_charge"
        elif meta["category"] != "accepted":
            terminal = meta["category"]
        elif monitored >= threshold:
            terminal = "spend_threshold_reached"
        elif i == 36 and not gate(root, selected, judgments)["pass"]:
            terminal = "control_gate_failed"
    controls, candidates = records(root, selected, judgments, saved["mode"])
    spec = plan(root)
    return {"version": VERSION, "protocol_sha256": protocol, "source_sha256": value["source_sha256"],
        "bank_sha256": value["bank_sha256"], "mode": saved["mode"],
        "terminal": terminal or ("schedule_complete" if len(judgments) == MAXIMUM else "incomplete_no_resume"),
        "complete": len(candidates) == 8 and len(judgments) == MAXIMUM,
        "attempts": len(attempts), "maximum_attempts": MAXIMUM, "candidate_calls": 0,
        "saved_answer_stages": 16, "accepted_judgments": len(judgments),
        "expected_candidate_conversations": 8, "candidate_score_records": candidates,
        "candidate_summary": workflow.mix.summarize(candidates, spec["candidate_models"], spec["families"]),
        "control_records": controls, "gate": gate(root, selected, judgments), "stage_records": stage_records,
        "monitoring_amount_usd": format(Decimal(monitored) / old.TICKS_PER_USD, "f"),
        "accounting": old.usage.summarize(accounts), "stop_threshold_usd": "2.00", "hard_ceiling": False,
        "automatic_retries": 0, "failures": failures, "old_run_resumed": False,
        "clinical_validation": False, "model_rankings_approved": False, "raw_data_published": False,
        "interpretation": "One bilingual family, four saved candidate models, one Gemini judge. Gemini self-judging, unreviewed labels and no candidate repeats limit interpretation. No score-band fitting."}


def execute(root, directory, value, protocol, credential, connection_factory, mode, *, threshold=THRESHOLD):
    directory = Path(directory)
    if mode == "live" and (threshold != THRESHOLD or audit(root)["protocol_sha256"] != protocol):
        raise ValueError("Live scope changed")
    selected = jobs(root, value, mode)
    write_json(directory / "manifest.json", manifest(value, protocol, mode))
    (directory / "contexts").mkdir(mode=0o700)
    journal = capture.CaptureJournal(root, directory / "capture", MAXIMUM, protocol, mode)
    monitored, judgments = 0, {}
    try:
        for job in selected:
            row, context = job["row"], job["context"]; i = row["sequence"]
            if row["block"] == "development" and not gate(root, selected, judgments)["pass"]:
                break
            if mode == "live" and audit(root)["protocol_sha256"] != protocol:
                raise ValueError("Frozen inputs changed")
            write_json(directory / "contexts" / f"{i:04d}.json", {"row": row, "context_sha256": sha256_json(context)})
            result = journal.exchange("gemini", context["payload"],
                lambda raw: score.decode(raw, "gemini", MODEL, context["packet"]),
                credential=credential, connection_factory=connection_factory)
            delta = old.monitoring_delta(result["accounting"], "gemini")["delta_ticks"]
            monitored += delta or 0
            if result["accepted"]:
                judgments[workflow.judgment_key(row)] = result["result"]
            if mode == "live":
                print(json.dumps({"sequence": i, "block": row["block"], "stage": row["stage"],
                    "accepted": result["accepted"], "category": result["category"],
                    "monitoring_usd": format(Decimal(monitored) / old.TICKS_PER_USD, "f")}), flush=True)
            if not result["accepted"] or delta is None or monitored >= threshold:
                break
    finally:
        credential = ""
        report = replay(root, directory, value, protocol, threshold=threshold)
        write_json(directory / "report.json", report)
    return report


def consume(root, protocol, run_id):
    directory = old.prior._private_path(root, "work/s48-consumed-protocols", directory=True, create=True)
    write_json(directory / (protocol + ".json"), {"protocol_sha256": protocol, "run_id": run_id, "maximum_attempts": MAXIMUM})


def run_live(root, run_id, note):
    checked, value = audit(root), source(root)
    verify_source(value, checked["plan"], "live")
    if not isinstance(note, str) or not note.strip() or str(UUID(run_id)) != run_id:
        raise ValueError("Actual approval and fresh UUID required")
    relative = "work/s48-runs/" + run_id
    if subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=root, capture_output=True).returncode:
        raise ValueError("Output must be ignored")
    parent = old.prior._private_path(root, "work/s48-runs", directory=True, create=True)
    if (parent / run_id).exists():
        raise ValueError("No run reuse")
    consume(root, checked["protocol_sha256"], run_id)
    directory = parent / run_id; directory.mkdir(mode=0o700)
    write_json(directory / "authorization.json", {"authorization_evidence": note,
        "issued_at": datetime.now(timezone.utc).isoformat(), "protocol_sha256": checked["protocol_sha256"],
        "maximum_attempts": MAXIMUM, "stop_threshold_usd": "2.00", "last_request_overrun_accepted": True,
        "candidate_calls": 0, "no_old_allowance_reused": True})
    key = ""
    try:
        key = old.prior.read_setting(root / ".env.local", "GEMINI_API_KEY", secret=True)
        return execute(root, directory, value, checked["protocol_sha256"], key, old.prior.create_tls_connection, "live")
    finally:
        key = ""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("source", "snapshot", "audit", "run", "report"))
    p.add_argument("--run-id"); p.add_argument("--authorization-note", default=""); p.add_argument("--directory")
    args = p.parse_args(); root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "source":
            result = {k: v for k, v in source(root).items() if k != "bank"}
        elif args.command == "snapshot":
            result = snapshot(root)
        elif args.command == "audit":
            result = audit(root)
        elif args.command == "run":
            result = run_live(root, args.run_id, args.authorization_note)
        else:
            checked, value = audit(root), source(root); verify_source(value, checked["plan"], "live")
            directory = old.prior._private_path(root, args.directory, directory=True)
            result = replay(root, directory, value, checked["protocol_sha256"])
            if result != read_json(directory / "report.json"):
                raise ValueError("Saved final report differs from replay")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "run" and not result["complete"]:
            p.exit(1, "S48 stopped incomplete; no retry or automatic expansion.\n")
    except Exception:
        p.exit(2, "S48 blocked/stopped. Captures stay private; no automatic retry.\n")


if __name__ == "__main__":
    main()
