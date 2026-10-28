"""Read-only S64 packet exercise, not rejudging or repairing S62 answers."""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from scripts import evidence_refs_s64 as refs
from scripts import audit_standalone_s63 as previous

live = previous.live


def exercise(packet):
    """Mechanical all-unclear fixture on original text; never a model judgment."""
    catalog = refs.catalog(packet)
    current = 1 if packet["scoring_stage"] == "initial" else 2
    spans = [s for s in catalog["spans"] if s["assistant_turn"] == current]
    value = {"packet_sha256": catalog["packet_sha256"], "criterion_assessments": [
        {"stage_id": packet["scoring_stage"], "requirement_index": a["requirement_index"],
         "status": "unclear", "response_evidence_ref": {"first": spans[0]["id"], "last": spans[-1]["id"]},
         "rationale": "Mechanical source-resolution fixture; no semantic judgment."}
        for a in packet["criterion_anchors"]], "critical_errors": []}
    if current == 2:
        value["dimension_observations"] = [{"dimension": d, "decision": "no_distinct_failure",
            "response_evidence_ref": None, "new_fact": "Mechanical fixture, not a conclusion.",
            "independent_consequence_or_failure": "", "overlap_note": "Mechanical fixture only."}
            for d in ("safety", "revision")]
    resolved = refs.resolve(value, packet)
    if any(r["response_evidence"] != packet["transcript"][-1]["content"] for r in resolved["criterion_assessments"]):
        raise ValueError("Source resolution changed answer text")
    invalid = deepcopy(value)
    invalid["criterion_assessments"][0]["response_evidence_ref"]["first"] = "unknown"
    try:
        refs.resolve(invalid, packet)
    except refs.score.JudgmentFailure:
        pass
    else:
        raise ValueError("Unknown reference accepted")
    return {"packet_sha256": catalog["packet_sha256"], "stage": packet["scoring_stage"],
            "language": packet["language"], "catalog_spans": len(catalog["spans"]),
            "exact_text_resolution": True, "unknown_reference_rejected": True,
            "semantic_evidence_relevance_tested": False}


def audit(root, directory):
    root, directory = Path(root), Path(directory).absolute()
    original = previous.audit(root, directory, live.read(root / live.FREEZE))
    before = original["source_journal_sha256"]
    rows, controls = [], []
    for item in original["attempts"]:
        control = item["kind"].startswith("control") and item["outcome"]["status"] == "accepted"
        rejected = item["kind"].startswith("judge") and item["outcome"]["status"] == "rejected"
        if not (control or rejected):
            continue
        event = directory / "events" / f'{item["event"]:04d}'
        payload = live.read(event / "payload.json")
        packet = json.loads(payload["input"])
        result = {"event": item["event"], **exercise(packet)}
        if rejected:
            raw = live.capture.strict_json((event / "transport/0001.raw.bin").read_bytes())
            try:
                refs.score.decode(raw, "gemini", payload["model"], packet)
            except refs.score.JudgmentFailure as exc:
                result["historical_rejection_category"] = exc.category
            else:
                raise ValueError("Historical rejected reply became valid")
            rows.append(result)
        else:
            controls.append(result)
    if previous.tree_hash(root, directory) != before:
        raise ValueError("Historical journal changed")
    return {"version": refs.VERSION, "status": "offline_mechanical_prototype_not_live_validated",
        "source_journal_sha256": before, "historical_protocol_sha256": original["protocol_sha256"],
        "historical_rejected_packets": rows, "accepted_control_packet_exercises": controls,
        "new_provider_calls": 0, "new_model_judgments": 0, "historical_scores_changed": 0,
        "historical_journal_unchanged": True, "clinically_validated": False,
        "live_failure_reduction_measured": False,
        "implementation_sha256": {p: live.digest((root / p).read_bytes()) for p in
            ("scripts/evidence_refs_s64.py", "scripts/audit_evidence_refs_s64.py")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(Path(__file__).resolve().parents[1], args.directory), ensure_ascii=False, indent=2))
