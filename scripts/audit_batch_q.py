"""Read-only Batch Q structural, source-binding and overlap checks; no API calls."""

from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from benchmark.config import load_json, load_jsonl
from benchmark.criterion_anchors import attach_anchors, validate_anchor_set
from benchmark.multiturn import validate_multiturn_dataset, variant_hash
from benchmark.multiturn_diagnostics import contrast_packet
from benchmark.provenance import sha256_json

FILES = {
    "cases": "data/multiturn/batch_q_cases.json",
    "anchors": "config/multiturn_criterion_anchors_batch_q_v1.json",
    "controls": "data/multiturn/batch_q_contrasts_v1.json",
    "provenance": "data/multiturn/batch_q_provenance.json",
}
FAMILIES = {"HC-MT-MEDSAFE-021", "HC-MT-REASON-026", "HC-MT-REASON-027", "HC-MT-TRIAGE-025"}
SPLIT = "standalone_public_authoring_draft_not_default_development_calibration_or_gold"
PUBLIC_DIRS = ("data/alpha", "data/multiturn", "data/professional", "data/calibration", "data/confirmation")


def materialize(probe):
    """Delete exactly one numbered update component; never manufacture a score."""
    value = deepcopy(probe)
    components = value["safe_components"]
    index = value["partial_omitted_requirement_index"]
    if type(index) is not int or not 1 <= index <= len(components):
        raise ValueError("Invalid omitted component")
    separator = " " if value["language"] == "en" else ""
    value["safe_update_response"] = separator.join(components)
    value["partial_update_response"] = separator.join(t for i, t in enumerate(components, 1) if i != index)
    return value


def source_key(url):
    """Normalize URL aliases with visible DOI/PMID/PMCID; no online resolution."""
    value = unquote(url).lower()
    doi = re.search(r"10\.\d{4,9}/[^?#\s]+", value)
    if doi:
        return "doi:" + doi.group().removesuffix("/full").rstrip("/")
    pmc = re.search(r"\bpmc\d+\b", value)
    if pmc:
        return pmc.group()
    parts = urlsplit(value)
    if parts.hostname == "pubmed.ncbi.nlm.nih.gov" and parts.path.strip("/").isdigit():
        return "pmid:" + parts.path.strip("/")
    return (parts.hostname or "") + parts.path.rstrip("/")


def source_keys(report):
    result = {source_key(report["url"])}
    for field, prefix in (("doi", "doi:"), ("pmid", "pmid:"), ("pmcid", "")):
        if report.get(field):
            result.add(prefix + report[field].lower())
    return result


def validate(data):
    dataset, anchors, controls, provenance = (data[k] for k in FILES)
    summary = validate_multiturn_dataset(dataset)
    validate_anchor_set(anchors, dataset)
    families = {f["family_id"]: f for f in dataset["families"]}
    records = {r["family_id"]: r for r in provenance["records"]}
    if (set(families) != FAMILIES or set(records) != FAMILIES
            or len(provenance["records"]) != 4
            or {a["family_id"] for a in anchors["families"]} != FAMILIES
            or len(anchors["families"]) != 4
            or provenance["split"] != SPLIT or provenance["review_complete"] is not False
            or controls["schema_version"] != "0.1.0"
            or controls["status"] != "author_controlled_unscored_development_only"):
        raise ValueError("Incomplete standalone coverage or promoted status")
    sources = {s["url"]: s for s in provenance["sources"]}
    if len(sources) != len(provenance["sources"]):
        raise ValueError("Duplicate source inventory")
    for source in sources.values():
        if any(not isinstance(source.get(k), str) or not source[k].strip()
               for k in ("url", "publisher", "version", "read_scope", "limit")):
            raise ValueError("Incomplete source access/version record")
    mapped, report_ids = 0, set()
    for fid, family in families.items():
        record = records[fid]
        expected = {lang: variant_hash(family, lang) for lang in family["variants"]}
        privacy = record["privacy_check"]
        if (record["case_hashes"] != expected or record["review_complete"] is not False
                or record["supporting_sources"] != family["source_refs"]
                or record["report"]["url"] not in family["source_refs"]
                or any(privacy[k] is not False for k in
                       ("private_records_used", "source_patient_reconstructed", "images_used"))
                or not record["review_issues"]):
            raise ValueError("Source/version/privacy/review binding changed")
        if report_ids & source_keys(record["report"]):
            raise ValueError("Report reused across supposedly distinct new families")
        report_ids.update(source_keys(record["report"]))
        for lang in ("en", "zh-Hans"):
            if [len(t["critical_requirements"]) for t in family["variants"][lang]["turns"]] != [3, 4]:
                raise ValueError("Batch Q stage coverage changed")
        positions = [(t["stage_id"], i) for t in family["variants"]["en"]["turns"]
                     for i in range(1, len(t["critical_requirements"]) + 1)]
        if [(r["stage"], r["index"]) for r in record["requirement_support"]] != positions:
            raise ValueError("Incomplete ordered source mapping")
        for item in record["requirement_support"]:
            if (type(item["index"]) is not int or item["case_hashes"] != expected
                    or item["guidance_url"] not in family["source_refs"]
                    or item["guidance_url"] not in sources
                    or item["support_type"] not in {"source_supported_application", "author_clinical_inference"}
                    or any(not isinstance(item[k], str) or not item[k].strip()
                           for k in ("source_locator", "basis"))):
                raise ValueError("Missing support, inference scope or current hash")
        mapped += len(positions)
    seen, packets = set(), {}
    for probe in controls["probes"]:
        key = probe["family_id"], probe["language"]
        if key in seen or key[0] not in families or key[1] not in ("en", "zh-Hans"):
            raise ValueError("Missing/duplicate reference language")
        seen.add(key)
        family = families[key[0]]
        components = probe["safe_components"]
        if (probe["case_content_hash"] != variant_hash(family, key[1])
                or len(components) != 4 or len(set(components)) != 4
                or any(not isinstance(t, str) or not t.strip() for t in
                       [probe["initial_response"], probe["unsafe_update_response"], *components])
                or probe["expected_unsafe_error_id"] not in {
                    e["id"] for e in family["variants"][key[1]]["turns"][1]["critical_errors"]}):
            raise ValueError("Invalid reference/contrast binding")
        materialized = materialize(probe)
        for profile in ("safe", "partial", "unsafe"):
            packet = attach_anchors(contrast_packet(family, materialized, profile), anchors)
            if any(k in packet for k in ("safe_components", "author_expectations", "profile",
                                        "partial_omitted_requirement_index", "expected_unsafe_error_id")):
                raise ValueError("Author control metadata leaked into judge packet")
            packets["__".join((*key, profile))] = sha256_json(packet)
    if seen != {(f, lang) for f in FAMILIES for lang in ("en", "zh-Hans")} or len(set(packets.values())) != 24:
        raise ValueError("Incomplete or duplicate blinded contrasts")
    return {"status": "structural_not_clinical_validation", "new_standalone_families": 4,
            "variants": 8, "mapped_criterion_positions": mapped, "bilingual_requirement_instances": mapped * 2,
            "initial_references": 8, "update_references": 24, "default_portfolio_additions": 0,
            "triage_transitions": summary["triage_transitions"], "packet_hashes": packets,
            "live_calls": 0, "numeric_scores": 0,
            "artifact_hashes": {k: sha256_json(v) for k, v in data.items()}}


def existing_cases(root):
    """Inspect public case containers, including reserved sets and Alpha JSONL."""
    for folder in PUBLIC_DIRS:
        for path in sorted((root / folder).glob("*.json*")):
            if path == root / FILES["cases"] or path.suffix not in {".json", ".jsonl"}:
                continue
            if path.suffix == ".jsonl":
                for row in load_jsonl(path):
                    metadata = row.get("metadata", {})
                    if metadata.get("case_family_id"):
                        yield path, metadata["case_family_id"], metadata.get("source_refs", [])
            else:
                value = load_json(path)
                for family in value.get("families", []) if isinstance(value, dict) else []:
                    if isinstance(family, dict) and family.get("variants"):
                        yield path, family["family_id"], family.get("source_refs", [])


def overlap_check(data, existing):
    records = data["provenance"]["records"]
    matches, scanned = set(), set()
    for path, fid, refs in existing:
        scanned.add((str(path), fid))
        if fid in FAMILIES:
            raise ValueError("New identity overlaps development/reserved cases")
        keys = {source_key(url) for url in refs}
        for record in records:
            if keys & source_keys(record["report"]):
                raise ValueError("New report overlaps an existing/reserved source; explicit grouping required")
            for url in record["supporting_sources"]:
                if source_key(url) in keys:
                    matches.add((record["family_id"], fid, str(path), url))
    return {"existing_family_file_pairs_checked": len(scanned),
            "report_identity_overlaps": 0,
            "shared_guidance": [dict(zip(("new_family", "existing_family", "path", "url"), row))
                                for row in sorted(matches)],
            "limit": "Visible DOI/PMID/PMCID and normalized URLs only, not all bibliographic aliases. Shared guidance does not prove case duplication. Manual related-family notes govern future grouping; semantic independence is unvalidated."}


def audit(root):
    root = Path(root)
    data = {name: load_json(root / path) for name, path in FILES.items()}
    result = validate(data)
    existing = [(p.relative_to(root), fid, refs) for p, fid, refs in existing_cases(root)]
    result["overlap_check"] = overlap_check(data, existing)
    registry = load_json(root / "config/benchmark.json")
    if FILES["cases"] in registry["multiturn_cases_paths"]:
        raise ValueError("Standalone batch entered default registry")
    return result


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
