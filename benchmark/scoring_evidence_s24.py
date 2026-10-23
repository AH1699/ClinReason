"""Non-enforced S24 evidence-record consistency checks; no score computation."""

from __future__ import annotations

import json
from pathlib import Path


DECISIONS = {"none_established", "review_required", "proposed_deduction"}


def validate_record(record: dict) -> None:
    if not record.get("family_id") or not record.get("answer_ref") or not record.get("observed_answer"):
        raise ValueError("S24 evidence must identify the exact family and answer")
    criterion = record["criterion"]
    if (criterion["stage"] not in {"initial", "update"} or not criterion["indexes"]
            or not criterion["finding"] or not criterion["status"]):
        raise ValueError("S24 criterion evidence is incomplete")
    for dimension in ("safety", "revision"):
        item = record[dimension]
        if (item["decision"] not in DECISIONS or not item["overlap"] or
                item["overlap_status"] not in {"same", "separate", "uncertain"}):
            raise ValueError(f"S24 {dimension} decision or overlap note is invalid")
        evidence_key = "independent_consequence" if dimension == "safety" else "independent_failure"
        if item["decision"] == "proposed_deduction" and not item[evidence_key]:
            raise ValueError(f"S24 {dimension} deduction lacks separate evidence")
        if item["decision"] == "proposed_deduction" and item["overlap_status"] != "separate":
            raise ValueError(f"S24 {dimension} deduction duplicates or may duplicate criterion finding")
        if item["decision"] == "none_established" and item[evidence_key] is not None:
            raise ValueError(f"S24 {dimension} cannot call evidence absent and present")
    if not record["revision"]["new_fact"] or not record["revision"]["answer_use"]:
        raise ValueError("S24 revision needs the new fact and observed answer use")
    if not all(record["applicability"].get(key) for key in ("population", "jurisdiction", "source_review")):
        raise ValueError("S24 source applicability is incomplete")
    if set(record["review_gates"]) != {"clinical", "bilingual", "methods"}:
        raise ValueError("S24 qualified review gates must remain explicit")


def validate_contract(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("version") != "s24-v1" or
            data.get("status") != "non_enforced_author_evidence_contract_not_adjudication"):
        raise ValueError("Unknown or enforced S24 evidence version")
    families = set()
    for record in data["fixtures"]:
        validate_record(record)
        if record["family_id"] in families:
            raise ValueError("Duplicate S24 family fixture")
        families.add(record["family_id"])
    return {"version": data["version"], "fixtures": len(families),
            "proposed_deductions": sum(
                item[dimension]["decision"] == "proposed_deduction"
                for item in data["fixtures"] for dimension in ("safety", "revision")),
            "historical_scores_changed": 0}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(validate_contract(root / "config/scoring_evidence_s24_v1.json"), indent=2))
