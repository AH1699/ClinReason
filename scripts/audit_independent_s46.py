"""Read-only public summary; no keys, candidate prose or raw provider reasoning."""

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts import independent_eval_s46 as runner
from scripts.judge_observation_draft import missing_observation_fields


def summarize(session):
    report = session.report()
    details = []
    for row in session.rows:
        if row["kind"] != "judge" or row["stage"] != "update":
            continue
        update = runner.workflow.judgment_key(row)
        initial_row = {**row, "stage": "initial"}
        if row["block"] == "control":
            initial_row["profile"] = None
        initial = runner.workflow.judgment_key(initial_row)
        if initial not in session.judgments or update not in session.judgments:
            continue
        first, second = session.judgments[initial], session.judgments[update]
        _, combined = runner.score.combine(first, second, session.contexts[row["sequence"]]["full"],
            {"version": runner.score.VERSION, **runner.score.ARITHMETIC})
        details.append({"block": row["block"], "family_id": row["family_id"], "language": row["language"],
            "judge": row["model"], "candidate_model": row.get("candidate_model"),
            "authored_profile": row.get("profile"), "repeat": row["repeat"],
            "score": combined, "criterion_statuses": {
                "initial": [v["status"] for v in first["criterion_assessments"]],
                "update": [v["status"] for v in second["criterion_assessments"]]},
            "critical_errors": [{k: v[k] for k in ("stage_id", "error_id", "severity")}
                                for v in first["critical_errors"] + second["critical_errors"]]})
    failures = []
    for row in session.rows:
        outcome = session.outcomes.get(row["sequence"], {})
        if outcome.get("status") != "rejected":
            continue
        meta = runner.read_json(session.directory / "jobs" / runner.old.job_id(row) / "capture" / "0001.capture.json")
        failures.append({"original_sequence": row["sequence"], "kind": row["kind"], "block": row["block"],
            "model": row["model"], "family_id": row["family_id"], "language": row["language"],
            "stage": row["stage"], "category": outcome["category"], "http_status": meta["status"]})
        if outcome["category"] == "response_validation":
            raw = runner.read_json(session.directory / "jobs" / runner.old.job_id(row) / "capture" / "0001.raw.bin")
            try:
                judgment = runner.score.base.parse_response(raw, row["provider"])
                failures[-1]["missing_mandatory_observation_fields"] = missing_observation_fields(
                    judgment, session.contexts[row["sequence"]]["packet"])
            except (ValueError, KeyError, TypeError, AttributeError):
                failures[-1]["parsed_observation_diagnostic_available"] = False
    return {**{k: v for k, v in report.items() if k != "jobs"},
        "protocol_sha256": session.protocol, "source_sha256": session.prefix["source_sha256"],
        "candidate_models": session.spec["candidate_models"], "families": session.spec["families"],
        "languages": session.spec["languages"], "judge_models": session.spec["judge_models"],
        "job_states_in_continuation": dict(Counter(j["status"] for j in report["jobs"])),
        "failures": failures, "answer_stage_counts": dict(Counter(k[2] for k in session.answers)),
        "numeric_judgment_details": details,
        "control_scores_are_author_hypothesis_diagnostics_not_model_scores": True,
        "raw_data_published": False, "xi_an_or_purchased_records_sent": False}


def audit(root, relative):
    checked, prefix = runner.audit(root), runner.recover_prefix(root)
    runner.verify_prefix(prefix, checked["plan"])
    directory = runner.old.prior._private_path(root, relative, directory=True)
    session = runner.replay(root, directory, prefix, checked["protocol_sha256"])
    if session.mode != "live" or session.report() != runner.read_json(directory / "report.json"):
        raise ValueError("Expected final live report matching raw-capture replay")
    return summarize(session)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    args = parser.parse_args()
    print(json.dumps(audit(Path(__file__).resolve().parents[1], args.directory), ensure_ascii=False, indent=2))
