"""Structural audit of citation-only PubMed case-report intake; not rights approval."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .config import load_json
from .provenance import sha256_json


RECORD_KEYS = {
    "intake_id", "status", "pmid", "pmcid", "doi", "article_url",
    "publication_date", "publication_type", "license", "license_url",
    "license_evidence_url", "publication_consent_reported",
    "correction_retraction_check", "mechanism_for_possible_synthetic_case",
    "source_to_answer_evidence", "privacy_and_leakage", "derived_case_ids",
}
COMMERCIAL_CANDIDATE_LICENSES = {"CC BY 4.0", "CC0 1.0"}
ANSWER_MAP_PATH = Path(__file__).resolve().parents[1] / "data/evidence/pubmed_source_to_answer_s17_v1.json"


def audit_intake(data: dict[str, Any]) -> dict[str, Any]:
    if (data.get("schema_version") != "0.1.0"
        or data.get("status") != "source_intake_only_no_benchmark_cases_or_answer_labels"
        or not isinstance(data.get("records"), list) or not data["records"]):
        raise ValueError("Unknown PubMed intake packet")
    seen_ids, seen_pmids, seen_pmcids, seen_dois = set(), set(), set(), set()
    statuses = Counter()
    for row in data["records"]:
        if not isinstance(row, dict) or set(row) != RECORD_KEYS:
            raise ValueError("Malformed PubMed intake record")
        if (not re.fullmatch(r"PM-S16-[A-Z]+-\d{3}", row["intake_id"])
            or not re.fullmatch(r"[1-9]\d*", row["pmid"])
            or not re.fullmatch(r"PMC[1-9]\d*", row["pmcid"])
            or not isinstance(row["doi"], str) or not row["doi"].startswith("10.")
            or row["article_url"] != f"https://pmc.ncbi.nlm.nih.gov/articles/{row['pmcid']}/"
            or row["license_evidence_url"] != row["article_url"]
            or row["publication_type"] != "case_report"
            or not isinstance(row["derived_case_ids"], list) or row["derived_case_ids"]):
            raise ValueError("PubMed intake identity or no-case boundary invalid")
        for value, seen in ((row["intake_id"], seen_ids), (row["pmid"], seen_pmids),
                            (row["pmcid"], seen_pmcids), (row["doi"], seen_dois)):
            if value in seen:
                raise ValueError("Duplicate PubMed intake identity")
            seen.add(value)
        if (row["license"] == "CC BY 4.0"
            and row["license_url"] != "https://creativecommons.org/licenses/by/4.0/"):
            raise ValueError("CC BY license URL mismatch")
        if row["status"].startswith("candidate_"):
            if (row["license"] not in COMMERCIAL_CANDIDATE_LICENSES
                or row["source_to_answer_evidence"] != "not_yet_selected"
                or row["correction_retraction_check"] != "pending_before_adaptation"):
                raise ValueError("Candidate has unsuitable license or premature answer evidence")
        elif row["status"] == "excluded_rights_not_for_case_adaptation":
            if row["license"] in COMMERCIAL_CANDIDATE_LICENSES or row["source_to_answer_evidence"] != "not_applicable":
                raise ValueError("Rights-excluded record is inconsistent")
        else:
            raise ValueError("Unknown PubMed intake status")
        for key in ("mechanism_for_possible_synthetic_case", "privacy_and_leakage"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError("Missing intake rationale")
        statuses[row["status"]] += 1
    return {
        "status": "citation_metadata_only_not_case_or_license_approval",
        "packet_sha256": sha256_json(data), "record_count": len(data["records"]),
        "status_counts": dict(sorted(statuses.items())), "derived_case_count": 0,
        "limits": "Structural checks cannot verify article rights, consent, corrections, privacy, clinical labels or language equivalence; recheck each source before adaptation.",
    }


def audit_source_to_answer(intake: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Check citation/evidence separation, never clinical truth or patient privacy."""
    audit_intake(intake)
    candidates = {row["intake_id"]: row for row in intake["records"]
                  if row["status"].startswith("candidate_")}
    if (evidence.get("schema_version") != "0.1.0"
        or evidence.get("status") != "candidate_behavior_evidence_only_no_answer_labels_or_cases"
        or evidence.get("privacy_action") != "citation_only_no_patient_details_no_case_prompts_or_reference_answers"
        or not isinstance(evidence.get("records"), list)
        or len(evidence["records"]) != len(candidates)):
        raise ValueError("Unknown source-to-answer evidence map")
    seen_records, seen_behaviors = set(), set()
    for row in evidence["records"]:
        if (set(row) != {"intake_id", "candidate_behaviors", "unsupported_case_report_inference",
                         "remaining_gate", "derived_case_ids"}
            or row["intake_id"] not in candidates or row["intake_id"] in seen_records
            or row["derived_case_ids"] != []
            or not isinstance(row["candidate_behaviors"], list)
            or not row["candidate_behaviors"]):
            raise ValueError("Source-to-answer record is invalid or contains a derived case")
        seen_records.add(row["intake_id"])
        for behavior in row["candidate_behaviors"]:
            if (set(behavior) != {"id", "proposed_behavior", "independent_source_url",
                                 "source_scope", "support_status"}
                or behavior["id"] in seen_behaviors
                or behavior["support_status"] != "broad_behavior_supported_exact_label_pending"
                or not behavior["independent_source_url"].startswith("https://")
                or "pubmed.ncbi.nlm.nih.gov" in behavior["independent_source_url"]
                or "pmc.ncbi.nlm.nih.gov/articles/" in behavior["independent_source_url"]
                or behavior["independent_source_url"] == candidates[row["intake_id"]]["article_url"]
                or any(not isinstance(behavior[key], str) or not behavior[key].strip()
                       for key in ("proposed_behavior", "source_scope"))):
                raise ValueError("Source-to-answer behavior lacks distinct guidance or remains malformed")
            seen_behaviors.add(behavior["id"])
        if any(not isinstance(row[key], str) or not row[key].strip()
               for key in ("unsupported_case_report_inference", "remaining_gate")):
            raise ValueError("Missing explicit evidence limit or remaining gate")
    if seen_records != set(candidates):
        raise ValueError("Not every candidate source has an evidence map")
    return {
        "status": "broad_behavior_source_map_not_answer_label_or_privacy_approval",
        "intake_sha256": sha256_json(intake), "evidence_sha256": sha256_json(evidence),
        "candidate_sources": len(seen_records), "proposed_behaviors": len(seen_behaviors),
        "derived_case_count": 0,
        "limits": "Structure only; clinical applicability, source currency, rights and privacy still need independent review before cases are written.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit citation-only PubMed intake metadata")
    parser.add_argument("--path", type=Path, default=Path(__file__).resolve().parents[1]
                        / "data/evidence/pubmed_case_intake_s16_v1.json")
    parser.add_argument("--answer-map", type=Path, default=None,
                        help="Optional independent candidate-behavior evidence map")
    args = parser.parse_args(argv)
    intake = load_json(args.path)
    result = (audit_source_to_answer(intake, load_json(args.answer_map))
              if args.answer_map else audit_intake(intake))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
