"""Read-only audit of a completed S41 control-prefix run ending in an HTTP error.

No credential loader, network calls, retries, output repair or file writes.
Run as: python3 -m scripts.audit_s41_control_stop <local-run-directory>
"""

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from benchmark import live_s41 as live, spending_s40 as spending, usage_s39 as usage
from benchmark import workflow_s38 as workflow
from benchmark.provenance import sha256_json


def read(path):
    return live.capture.strict_json(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(root, directory):
    protocol = live.audit(root)["protocol_sha256"]
    directory = Path(directory)
    report = read(directory/"report.json")
    count = report["attempts_reserved"]
    require(type(count) is int and 1 <= count <= 72, "Expected a control-prefix stop")
    require(report["terminal"] == "http_status" and report["complete"] is False, "Expected terminal HTTP error")
    rows, plan = workflow.schedule(root), workflow.design(root)
    specs = {(s["provider"], s["model"]): s for s in plan["judges"]}
    catalog, controls = workflow.families(root), workflow.score.controls(root)
    judgments, contexts, accounts, ledger = {}, {}, [], []
    monitoring = reported = estimated = 0
    previous = sha256_json(spending.policy(root))
    models = Counter()
    expected_stems = {f"{i:04d}" for i in range(1, count+1)}
    for folder, suffix in (("capture", ".attempt.json"), ("spending", ".admission.json"), ("spending", ".settlement.json")):
        actual = {p.name.removesuffix(suffix) for p in (directory/folder).glob("*"+suffix)}
        require(actual == expected_stems, "Noncontiguous attempts or extra dispatch after stop")
    for number in range(1, count+1):
        stem, row = f"{number:04d}", rows[number-1]
        require(row["block"] == "control" and row["kind"] == "judge", "Candidate requests outside this audit")
        context = workflow.request_context(root, row, catalog, controls, {})
        contexts[number] = context
        admission = read(directory/"spending"/(stem+".admission.json"))
        settlement = read(directory/"spending"/(stem+".settlement.json"))
        attempt = read(directory/"capture"/(stem+".attempt.json"))
        capture = read(directory/"capture"/(stem+".capture.json"))
        payload_bytes = (directory/"capture"/(stem+".payload.json")).read_bytes()
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()
        require(payload_bytes == live.guard._json_bytes(context["payload"]), "Payload differs from frozen builder")
        require((directory/"spending"/(stem+".payload.json")).read_bytes() == payload_bytes, "Payload copies differ")
        require(attempt["protocol_sha256"] == protocol and attempt["payload_sha256"] == payload_hash, "Capture binding mismatch")
        require(attempt["sequence"] == number and attempt["model"] == row["model"] and attempt["provider"] == row["provider"], "Capture identity mismatch")
        require(admission["row"] == row and admission["payload_sha256"] == payload_hash, "Schedule/admission mismatch")
        require(admission["previous_record_sha256"] == previous and admission["monitoring_before_ticks"] == monitoring, "Ledger chain mismatch")
        require(admission["policy_sha256"] == sha256_json(spending.policy(root)), "Spending policy mismatch")
        require(settlement["admission_sha256"] == sha256_json(admission), "Settlement binding mismatch")
        raw_bytes = (directory/"capture"/(stem+".raw.bin")).read_bytes()
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        require(capture["body_eof"] and capture["bytes_saved"] == len(raw_bytes) and capture["body_sha256"] == raw_hash, "Raw-body capture mismatch")
        require(capture["mode"] == "live" and capture["fixture_only"] is False and admission["fixture_only"] is False, "Fixture is not a live result")
        accepted = number < count
        if accepted:
            require(200 <= capture["status"] < 300 and capture["category"] == "accepted", "Unexpected earlier failure")
            raw = live.capture.strict_json(raw_bytes)
            account = usage.account(raw, specs[row["provider"], row["model"]])
            judgment = workflow.score.decode(raw, row["provider"], row["model"], context["packet"])
            require(read(directory/"capture"/(stem+".accepted.json")) == {"result": judgment, "raw_sha256": raw_hash}, "Saved judgment differs from replay")
            judgments[workflow.judgment_key(row)] = judgment
        else:
            require(type(capture["status"]) is int and not 200 <= capture["status"] < 300 and capture["category"] == "http_status", "Final attempt is not HTTP rejection")
            require(not (directory/"capture"/(stem+".accepted.json")).exists(), "Rejected response was accepted")
            # The frozen runner cannot establish billing/model identity for a non-2xx body.
            account = usage.account(None, specs[row["provider"], row["model"]])
        require(account == read(directory/"capture"/(stem+".accounting.json")), "Usage/accounting mismatch")
        delta = spending.monitoring_delta(account, row["provider"])
        monitoring += delta["delta_ticks"] or 0
        reported += delta["reported_ticks"] or 0
        estimated += delta["estimate_microusd"] or 0
        expected_settlement = {"sequence": number, "admission_sha256": sha256_json(admission), **delta,
            "monitoring_after_ticks": monitoring, "capture_accepted": accepted,
            "stop_reason": None if accepted else "unknown_charge",
            "threshold_reached": False, "hard_ceiling": False}
        require(monitoring < 55*spending.TICKS_PER_USD and settlement == expected_settlement, "Spending replay mismatch")
        previous = sha256_json(settlement)
        accounts.append(account); ledger.append(settlement); models[row["model"]] += 1
    require(report["capture_accounting"] == usage.summarize(accounts), "Report accounting differs from replay")
    require(report["score_records"] == [] and report["completed_exchanges"] == count, "Unexpected candidate scores")
    require(report["control_gate"] == workflow.control_gate(root, rows, judgments, contexts), "Control-gate report mismatch")
    expected_monitor = {"mode": "live", "attempts": count, "settled_attempts": count, "outstanding_attempts": 0,
        "unknown_settled_charges": 1, "stop_reason": "unknown_charge", "monitoring_amount_ticks": monitoring,
        "monitoring_amount_usd": format(Decimal(monitoring)/spending.TICKS_PER_USD, "f"),
        "provider_reported_subtotal_ticks": reported, "token_estimate_subtotal_microusd": estimated,
        "threshold_ticks": 55*spending.TICKS_PER_USD, "monitoring_overrun_ticks": 0,
        "threshold_reached": False, "invoice_total_usd": None, "hard_ceiling": False, "can_dispatch": False}
    require(report["spending"] == expected_monitor, "Monitor report mismatch")
    return {"version": "s42-s41-control-stop-audit-v1", "protocol_sha256": protocol,
        "run_report_sha256": hashlib.sha256((directory/"report.json").read_bytes()).hexdigest(),
        "offline_replay_pass": True, "attempts": count, "accepted_control_judgments": len(judgments),
        "candidate_requests": 0, "candidate_scores": 0, "attempts_by_model": dict(sorted(models.items())),
        "terminal": report["terminal"], "failed_request": {"sequence": count, "model": row["model"],
            "family_id": row["family_id"], "language": row["language"], "stage": row["stage"],
            "http_status": capture["status"], "body_sha256": raw_hash},
        "recorded_amount_usd": expected_monitor["monitoring_amount_usd"],
        "grok_reported_usd": format(Decimal(reported)/spending.TICKS_PER_USD, "f"),
        "token_estimate_usd": format(Decimal(estimated)/1_000_000, "f"),
        "unknown_charge_attempts": 1, "invoice_total_usd": None, "control_gate_complete": False,
        "calibration_complete": False, "retry_performed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(Path(__file__).resolve().parents[1], args.directory), ensure_ascii=False, indent=2))
