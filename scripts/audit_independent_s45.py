"""Read-only, secret-free summary of the frozen S45 workflow pilot."""

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts import independent_eval_s45 as runner


def audit(root, relative):
    checked = runner.audit(root)
    directory = runner.prior._private_path(root, relative, directory=True)
    session = runner.replay(root, directory)
    if session.mode != "live" or session.protocol != checked["protocol_sha256"]:
        raise ValueError("Expected the frozen live S45 pilot")
    result = session.report()
    saved = runner.read_json(directory / "report.json")
    if saved != result:
        raise ValueError("Final report differs from raw-capture replay")
    attempted = [r for r in session.rows if session.outcomes.get(r["sequence"], {}).get("status") in {"accepted", "rejected"}]
    candidate_counts = {m: {"attempts": sum(r["kind"] == "candidate" and r["model"] == m for r in attempted),
                           "accepted_answer_stages": sum(k[2] == m for k in session.answers)}
                        for m in session.spec["candidate_models"]}
    failures = []
    for row in attempted:
        outcome = session.outcomes[row["sequence"]]
        if outcome["status"] != "rejected":
            continue
        meta = runner.read_json(directory / "jobs" / runner.job_id(row) / "capture" / "0001.capture.json")
        failures.append({"sequence": row["sequence"], "kind": row["kind"], "block": row["block"],
            "model": row["model"], "family_id": row["family_id"], "language": row["language"],
            "stage": row["stage"], "category": outcome["category"], "http_status": meta["status"]})
    return {"version": runner.VERSION, "protocol_sha256": session.protocol,
        "terminal": result["terminal"], "complete": result["complete"],
        "families": session.spec["families"], "languages": session.spec["languages"],
        "candidate_models": session.spec["candidate_models"], "judge_models": session.spec["judge_models"],
        "deferred_judge_models": session.spec["deferred_judge_models"],
        "maximum_attempts": result["maximum_attempts"], "attempts": result["attempts"],
        "attempts_by_kind": dict(Counter(r["kind"] for r in attempted)),
        "candidate_counts": candidate_counts, "accepted_answer_stages": result["accepted_answer_stages"],
        "answer_bank_sha256": result["answer_bank_sha256"], "controls": result["controls"],
        "score_records": result["score_records"], "separate_judge_reports": result["separate_judge_reports"],
        "failures": failures, "job_states": dict(Counter(j["status"] for j in result["jobs"])),
        "accounting": result["accounting"], "monitoring_amount_usd": result["monitoring_amount_usd"],
        "stop_threshold_usd": result["stop_threshold_usd"], "hard_ceiling": False,
        "outstanding_attempts_unknown_delivery_or_charge": result["outstanding_attempts_unknown_delivery_or_charge"],
        "read_only_recovered_sequences": result["read_only_recovered_sequences"],
        "clinical_validation": False, "model_rankings_approved": False,
        "interpretation": "One bilingual family and four candidates, single Gemini judge. Self-judging bias and unreviewed labels; not completed calibration or a representative roster mean. No score-band fitting.",
        "raw_data_published": False, "xi_an_or_purchased_records_sent": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    args = parser.parse_args()
    print(json.dumps(audit(Path(__file__).resolve().parents[1], args.directory), ensure_ascii=False, indent=2))
