"""Offline source-to-answer and privacy-metadata boundary for batch H; not clinical approval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_json
from .multiturn import validate_multiturn_dataset
from .provenance import sha256_json


def audit_derived_cases(cases: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    structure = validate_multiturn_dataset(cases)
    root = Path(__file__).resolve().parents[1]
    intake = load_json(root / "data/evidence/pubmed_case_intake_s16_v1.json")
    source_groups = {row["intake_id"]: row for row in intake["records"]
                     if row["status"].startswith("candidate_")}
    if (ledger.get("schema_version") != "0.1.0"
        or ledger.get("status") != "author_draft_pending_independent_clinical_language_rights_and_privacy_review"
        or ledger.get("split") != "public_development_not_calibration_or_gold"
        or not isinstance(ledger.get("records"), list)):
        raise ValueError("Unknown derived-case provenance ledger")
    by_id = {family["family_id"]: family for family in cases["families"]}
    record_ids = [row.get("family_id") for row in ledger["records"]]
    if len(record_ids) != len(set(record_ids)) or set(record_ids) != set(by_id):
        raise ValueError("Every derived family needs exactly one provenance record")
    for row in ledger["records"]:
        family = by_id[row["family_id"]]
        report = row.get("published_case_or_series")
        guidance = row.get("supporting_sources")
        source = source_groups.get(row.get("source_group"))
        if (source is None
            or row.get("source_identity") != {key: source[key] for key in ("pmid", "pmcid", "doi")}
            or report != f"https://pubmed.ncbi.nlm.nih.gov/{source['pmid']}/"
            or source["license"] != "CC BY 4.0"
            or not source["publication_consent_reported"].startswith("written_")):
            raise ValueError("Derived case does not match eligible frozen PubMed intake identity")
        if (not isinstance(report, str) or not report.startswith("https://pubmed.ncbi.nlm.nih.gov/")
            or not isinstance(guidance, list) or not guidance
            or report in guidance or set(family["source_refs"]) != {report, *guidance}
            or not row.get("source_group") or not row.get("source_identity")):
            raise ValueError("Published report must be linked and separated from answer guidance")
        candidate_text = " ".join(
            turn["user"] for variant in family["variants"].values() for turn in variant["turns"]
        ).casefold()
        prohibited = {
            "PM-S16-EYE-001": ("tramadol", "hysterectomy", "曲马多", "子宫切除", "45 mmhg", "39 mmhg"),
            "PM-S16-PE-002": ("mycoplasma", "支原体", "63-year-old", "63 岁", "d-dimer", "d－二聚体"),
        }
        if any(fragment in candidate_text for fragment in prohibited.get(row["source_group"], ())):
            raise ValueError("Candidate prompt contains a distinctive published-case detail")
        for field in ("license_and_consent", "correction_retraction_status", "mechanism_only",
                      "privacy_and_leakage_check", "critical_error_basis", "review_questions"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Missing provenance gate: {field}")
        expected = {(stage, index) for stage in ("initial", "update")
                    for index in range(1, len(family["variants"]["en"]["turns"][0 if stage == "initial" else 1]["critical_requirements"]) + 1)}
        if any(len(family["variants"]["en"]["turns"][turn_index]["critical_requirements"])
               != len(family["variants"]["zh-Hans"]["turns"][turn_index]["critical_requirements"])
               for turn_index in (0, 1)):
            raise ValueError("Bilingual requirement counts differ")
        mapped: set[tuple[str, int]] = set()
        for entry in row.get("requirement_support", []):
            if (set(entry) != {"stage", "index", "guidance_url", "basis"}
                or entry["guidance_url"] not in guidance
                or not isinstance(entry["basis"], str) or not entry["basis"].strip()):
                raise ValueError("Answer requirement must map to independent guidance")
            key = (entry["stage"], entry["index"])
            if key in mapped:
                raise ValueError("Duplicate requirement support")
            mapped.add(key)
        if mapped != expected:
            raise ValueError("Incomplete exact-requirement source mapping")
    return {
        "status": "author_source_to_exact_requirement_mapping_not_clinical_or_privacy_approval",
        "case_sha256": sha256_json(cases),
        "ledger_sha256": sha256_json(ledger),
        "families": structure["family_count"],
        "mapped_requirements": sum(len(row["requirement_support"]) for row in ledger["records"]),
        "limit": "Structure and documented source separation only; no independent source appraisal, re-identification proof, licensed-rights opinion, clinical validity or bilingual approval.",
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = audit_derived_cases(
        load_json(root / "data/multiturn/batch_h_cases.json"),
        load_json(root / "data/multiturn/batch_h_provenance.json"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
