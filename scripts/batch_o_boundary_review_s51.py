"""Bind the developer wording review to all twelve Batch O criterion positions.

This validates coverage and staleness, not clinical/source correctness. It does
not edit cases, anchors or controls and has no network path.
"""

import json
from pathlib import Path

from scripts import audit_batch_o as batch

DATA = "data/audit/batch_o_boundary_review_s51.json"
VERSION = "s51-batch-o-boundary-review-v1"


def bindings(root):
    data = {k: batch.load_json(root / path) for k, path in batch.FILES.items()}
    catalog = {f["family_id"]: f for f in data["cases"]["families"]}
    anchors = {f["family_id"]: f for f in data["anchors"]["families"]}
    result = {}
    for fid, family in catalog.items():
        for stage in ("initial", "update"):
            for index in range(1, 4):
                requirements = {lang: next(t for t in variant["turns"] if t["stage_id"] == stage)
                                ["critical_requirements"][index-1] for lang, variant in family["variants"].items()}
                result[(fid, stage, index)] = {
                    "requirements_sha256": batch.sha256_json(requirements),
                    "anchor_sha256": batch.sha256_json(anchors[fid]["stages"][stage][index-1])}
    return result


def validate(root, value):
    source = batch.audit(root)
    if (value["version"] != VERSION or value["status"] != "developer_wording_review_not_clinical_approval"
            or value["artifact_hashes"] != source["artifact_hashes"]
            or value["case_changes"] != 0 or value["new_case_families"] != 0
            or value["live_calls"] != 0 or value["numeric_scores"] is not False
            or value["clinical_validation"] is not False):
        raise ValueError("Changed review scope or stale Batch O artifacts")
    expected, seen = bindings(root), set()
    for row in value["criteria"]:
        key = row["family_id"], row["stage"], row["requirement_index"]
        if (key not in expected or key in seen or row["binding"] != expected[key]
                or row["disposition"] not in {"boundary_decision_needed", "component_contrast_needed", "alternative_contrast_needed"}
                or not all(isinstance(row[k], str) and row[k].strip() for k in ("question_en", "question_zh", "next_control"))
                or row["resolved"] is not False):
            raise ValueError("Duplicate, stale, incomplete or prematurely closed criterion review")
        seen.add(key)
    if seen != set(expected):
        raise ValueError("Review must cover all twelve criterion positions")
    return {"version": VERSION, "reviewed_criterion_positions": len(seen),
        "bilingual_requirement_positions": len(seen)*2,
        "boundary_decisions": sum(r["disposition"] == "boundary_decision_needed" for r in value["criteria"]),
        "review_sha256": batch.sha256_json(value), "case_changes": 0,
        "new_case_families": 0, "live_calls": 0, "clinical_validation": False}


def audit(root):
    return validate(root, batch.load_json(root / DATA))


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
