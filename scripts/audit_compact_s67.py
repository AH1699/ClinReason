"""Read-only S66 result/evidence audit. Never calls providers or changes scores.

Optional review rows are explicit local AI/operator assessments, not automated
semantic validation or independent clinical adjudication. Public exports are
allowlisted; raw answers, rationale and approval evidence stay in the journal.
"""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from scripts import compact_live_s66 as live
from scripts import audit_standalone_s63 as previous

VERSION = "s67-compact-feasibility-readout-v1"
FILES = ("scripts/audit_compact_s67.py", "tests/test_audit_compact_s67.py")


def evidence_slots(row, packet, judgment):
    slots = []
    for field in ("criterion_assessments", "dimension_observations"):
        for value in judgment.get(field, []):
            criterion = field == "criterion_assessments"
            key = "criterion:" + str(value["requirement_index"]) if criterion else "observation:" + value["dimension"]
            quote = value["response_evidence"]
            slots.append({"id": row["id"] + "/" + key, "event_id": row["id"],
                "source": row["source"], "phase": row["phase"], "field": field,
                "case_id": packet["case_id"], "language": packet["language"], "stage": packet["scoring_stage"],
                "judgment_row_sha256": live.pilot.sha256_json(value),
                "packet_sha256": live.pilot.sha256_json(packet),
                "decision": value["status"] if criterion else value["decision"],
                "reference_null": quote == "", "reference_characters": len(quote),
                "reference_sha256": live.digest(quote.encode("utf-8"))})
    return slots


def review_readout(ledger, protocol, journal_hash, slots):
    if ledger is None:
        return {"status": "not_supplied", "reviewed_slots": 0, "expected_slots": len(slots),
                "pass": False, "independent_clinical_review": False}
    fields = {"version", "protocol_sha256", "source_journal_sha256", "reviewer", "reviewed_at",
              "independent_clinical_review", "rows"}
    if (set(ledger) != fields or ledger["version"] != VERSION
            or ledger["protocol_sha256"] != protocol or ledger["source_journal_sha256"] != journal_hash
            or ledger["independent_clinical_review"] is not False
            or ledger["reviewer"] != "assistant_local_preliminary_not_independent_clinician"
            or not isinstance(ledger["rows"], list)):
        raise ValueError("Review ledger identity/scope mismatch")
    live.stamp(ledger["reviewed_at"])
    expected = {v["id"]: v for v in slots}
    seen = set()
    for row in ledger["rows"]:
        if (set(row) != {"id", "judgment_row_sha256", "relevance", "breadth", "verdict", "note"}
                or row["id"] not in expected or row["id"] in seen
                or row["judgment_row_sha256"] != expected[row["id"]]["judgment_row_sha256"]
                or row["relevance"] not in {"supported", "qualified", "not_demonstrated", "null_permitted"}
                or row["breadth"] not in {"minimal_or_chunk_padding", "distributed_support", "avoidable_extra_context", "not_applicable"}
                or row["verdict"] not in {"no_objection", "review_hold"}
                or not isinstance(row["note"], str) or not row["note"].strip()):
            raise ValueError("Incomplete, duplicate or unbound review row")
        null = expected[row["id"]]["reference_null"]
        if null != (row["relevance"] == "null_permitted") or null != (row["breadth"] == "not_applicable"):
            raise ValueError("Null reference review mismatch")
        if row["relevance"] in {"qualified", "not_demonstrated"} and row["verdict"] != "review_hold":
            raise ValueError("Unresolved support cannot be cleared")
        if row["breadth"] == "avoidable_extra_context" and row["verdict"] != "review_hold":
            raise ValueError("Unresolved breadth cannot be cleared")
        seen.add(row["id"])
    if seen != set(expected):
        raise ValueError("Every accepted reference/null requires its own review")
    holds = [v["id"] for v in ledger["rows"] if v["verdict"] == "review_hold"]
    return {"status": "completed_local_preliminary_review", "reviewed_slots": len(seen),
            "expected_slots": len(slots), "hold_slots": holds, "hold_count": len(holds),
            "relevance_counts": dict(Counter(v["relevance"] for v in ledger["rows"])),
            "breadth_counts": dict(Counter(v["breadth"] for v in ledger["rows"])),
            "ledger_sha256": live.pilot.sha256_json(ledger), "pass": not holds,
            "independent_clinical_review": False}


def comparisons(items, judgments):
    result = []
    for item in items:
        key = item["id"]
        first, repeat = (judgments.get(phase + "__" + key) for phase in ("first", "repeat"))
        value = {"source": key, "case_id": item["packet"]["case_id"],
                 "stage": item["packet"]["scoring_stage"], "language": item["packet"]["language"],
                 "first": None if first is None else previous.judgment(first),
                 "repeat": None if repeat is None else previous.judgment(repeat),
                 "comparison": None}
        if first is not None and repeat is not None:
            a, b = value["first"], value["repeat"]
            criterion_changes = [{"requirement_index": x["requirement_index"], "first": x["status"], "repeat": y["status"]}
                for x, y in zip(a["criterion_assessments"], b["criterion_assessments"]) if x["status"] != y["status"]]
            observation_changes = [{"dimension": x["dimension"], "first": x["decision"], "repeat": y["decision"]}
                for x, y in zip(a["dimension_observations"], b["dimension_observations"]) if x["decision"] != y["decision"]]
            evidence_changes = []
            for field in ("criterion_assessments", "dimension_observations"):
                for x, y in zip(first.get(field, []), repeat.get(field, [])):
                    if x["response_evidence"] != y["response_evidence"]:
                        evidence_changes.append({"field": field, "key": x.get("requirement_index", x.get("dimension"))})
            value["comparison"] = {"criterion_changes": criterion_changes, "observation_changes": observation_changes,
                "critical_errors_match": a["critical_errors"] == b["critical_errors"],
                "changed_evidence_ranges": evidence_changes}
        result.append(value)
    return result


def audit(root, directory, ledger=None):
    root = Path(root); directory = live.old.previous.safe_directory(root, directory)
    before = previous.tree_hash(root, directory)
    verified = live.replay(root, directory)
    if (not verified["report_verified"] or verified["incomplete_tail"] is not None
            or verified["report"]["terminal"] is None):
        raise ValueError("A closed, independently replayed run is required")
    items = live.capture.strict_json(live.read(directory / "inputs.json").encode("utf-8"))
    by_id = {r["id"]: r for r in items}
    judgments, slots, events, candidates = {}, [], [], []
    for event in sorted((directory / "events").iterdir()):
        row = live.read(event / "reservation.json")["row"]
        outcome = live.read(event / "result.json")
        account = outcome["accounting"]
        usage = account.get("usage") or {}
        capture = live.read(event / "transport/0001.capture.json")
        entry = {"event": int(event.name), "id": row["id"], "provider": row["provider"], "model": row["model"],
            "status": outcome["outcome"]["status"], "category": outcome["category"],
            "raw_sha256": capture["body_sha256"], "elapsed_ms": capture["elapsed_ms"],
            "accounting_status": account["status"],
            "input_tokens": usage.get("input_tokens"),
            "reported_output_tokens": usage.get("reported_output_tokens"),
            "thought_tokens": usage.get("thought_tokens"),
            "output_tokens_for_estimate": usage.get("output_tokens_for_estimate")}
        events.append(entry)
        if row["kind"] == "candidate":
            candidates.append({**entry, "stage": row["stage"], "language": row["cell"]["language"],
                               "visible_characters": None, "output_limit": 32768, "scored": False})
        if entry["status"] != "accepted": continue
        value = live.read(event / "transport/0001.accepted.json")["result"]
        if row["kind"] == "judge":
            judgments[row["id"]] = value
            slots += evidence_slots(row, by_id[row["source"]]["packet"], value)
        else:
            candidates[-1]["visible_characters"] = len(value["text"])
    review = review_readout(ledger, verified["protocol_sha256"], before, slots)
    paired = comparisons(items, judgments)
    comparable = [v["comparison"] for v in paired if v["comparison"] is not None]
    result = {"version": VERSION, "protocol_sha256": verified["protocol_sha256"], "source_journal_sha256": before,
        "audit_files": {p: live.digest(live.pilot.public_path(root, p).read_bytes()) for p in FILES},
        "read_only": True, "source_journal_unchanged": True, "mode": verified["report"]["mode"],
        "run_report": deepcopy(verified["report"]), "events": events, "candidate_turns": candidates,
        "judge_pairs": paired, "evidence_slots": slots, "local_review": review,
        "comparison_totals": {"paired_packets": len(comparable),
            "criterion_positions_compared": sum(len(v["first"]["criterion_assessments"]) for v in paired if v["comparison"] is not None),
            "changed_criterion_positions": sum(len(v["criterion_changes"]) for v in comparable),
            "changed_observation_decisions": sum(len(v["observation_changes"]) for v in comparable),
            "changed_evidence_ranges": sum(len(v["changed_evidence_ranges"]) for v in comparable)},
        "evidence_totals": {"slots": len(slots), "nonnull": sum(not r["reference_null"] for r in slots),
                            "null": sum(r["reference_null"] for r in slots)},
        "development_feasibility_passed": (verified["report"]["mode"] == "live"
            and verified["report"]["technical_gate"]["pass"] and review["pass"]),
        "clinical_validation": False, "measured_model_scores": 0, "historical_scores_changed": 0,
        "automatic_retry_or_broader_run_authorized": False}
    if before != previous.tree_hash(root, directory):
        raise ValueError("Source changed during read-only audit")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(audit(root, args.directory, None if args.review is None else live.read(args.review)),
                     ensure_ascii=False, indent=2))
