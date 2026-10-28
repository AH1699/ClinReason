"""Standalone authoring checks, never clinical approval or a live-run registry."""

import json
from pathlib import Path

from benchmark.config import load_json
from benchmark.criterion_anchors import attach_anchors, validate_anchor_set
from benchmark.multiturn import validate_multiturn_dataset, variant_hash
from benchmark.multiturn_diagnostics import contrast_packet
from benchmark.provenance import sha256_json
from scripts import audit_batch_q as shared

FILES = {"cases": "data/authoring/batch_r_cases.json",
         "anchors": "config/multiturn_criterion_anchors_batch_r_v1.json",
         "controls": "data/authoring/batch_r_contrasts_v1.json",
         "provenance": "data/authoring/batch_r_provenance.json"}
FAMILIES = {"HC-MT-REASON-028", "HC-MT-MEDSAFE-022"}


def validate(data):
    cases, anchors, controls, provenance = (data[k] for k in FILES)
    validate_multiturn_dataset(cases)
    validate_anchor_set(anchors, cases)
    families = {f["family_id"]: f for f in cases["families"]}
    records = {r["family_id"]: r for r in provenance["records"]}
    if (set(families) != FAMILIES or set(records) != FAMILIES or len(provenance["records"]) != 2
            or len(anchors["families"]) != 2 or {r["family_id"] for r in anchors["families"]} != FAMILIES
            or provenance["review_complete"] is not False or provenance["split"] != shared.SPLIT
            or controls["schema_version"] != "0.1.0"
            or controls["status"] != "author_controlled_unscored_development_only"):
        raise ValueError("Incomplete or promoted batch")
    sources = {s["url"]: s for s in provenance["sources"]}
    if len(sources) != len(provenance["sources"]):
        raise ValueError("Duplicate source")
    for source in sources.values():
        if any(not isinstance(source.get(k), str) or not source[k].strip()
               for k in ("url", "publisher", "version", "read_scope", "limit")):
            raise ValueError("Missing source access or limitation")
    for fid, family in families.items():
        record = records[fid]
        hashes = {lang: variant_hash(family, lang) for lang in family["variants"]}
        if (record["case_hashes"] != hashes or record["review_complete"] is not False
                or record["supporting_sources"] != family["source_refs"]
                or record["report"]["url"] not in family["source_refs"]
                or not set(family["source_refs"]) <= set(sources)
                or not record["review_issues"] or not record["related_families"]
                or any(record["privacy_check"][k] is not False for k in
                       ("private_records_used", "source_patient_reconstructed", "images_used"))):
            raise ValueError("Case/source/privacy/review binding invalid")
        report = record["report"]
        if any(not isinstance(report.get(k), str) or not report[k].strip() for k in
               ("pmid", "pmcid", "doi", "publication_date", "license", "license_url", "license_basis",
                "correction_retraction_screen", "attribution")):
            raise ValueError("Incomplete case-report intake")
        for lang in ("en", "zh-Hans"):
            if [len(t["critical_requirements"]) for t in family["variants"][lang]["turns"]] != [3, 4]:
                raise ValueError("Stage criterion coverage changed")
        positions = [(s, i) for s, n in (("initial", 3), ("update", 4)) for i in range(1, n+1)]
        support = record["requirement_support"]
        if [(r["stage"], r["index"]) for r in support] != positions:
            raise ValueError("Missing or duplicate source-to-criterion map")
        for row in support:
            if (type(row["index"]) is not int or row["case_hashes"] != hashes
                    or row["guidance_url"] not in family["source_refs"]
                    or row["support_type"] not in {"author_clinical_inference", "source_supported_application"}
                    or any(not isinstance(row[k], str) or not row[k].strip() for k in ("source_locator", "basis"))):
                raise ValueError("Invalid source mapping")
    seen, packets = set(), {}
    for probe in controls["probes"]:
        key = probe["family_id"], probe["language"]
        if key in seen or key[0] not in families or key[1] not in ("en", "zh-Hans"):
            raise ValueError("Invalid or duplicate reference pair")
        seen.add(key)
        family = families[key[0]]
        if (probe["case_content_hash"] != variant_hash(family, key[1])
                or len(probe["safe_components"]) != 4 or len(set(probe["safe_components"])) != 4
                or any(not isinstance(t, str) or not t.strip() for t in
                       [probe["initial_response"], probe["unsafe_update_response"], *probe["safe_components"]])
                or probe["expected_unsafe_error_id"] not in
                   {e["id"] for e in family["variants"][key[1]]["turns"][1]["critical_errors"]}):
            raise ValueError("Reference/hash/error binding invalid")
        for profile in ("safe", "partial", "unsafe"):
            packet = attach_anchors(contrast_packet(family, shared.materialize(probe), profile), anchors)
            if any(k in packet for k in ("safe_components", "author_expectations", "profile",
                                        "partial_omitted_requirement_index", "expected_unsafe_error_id")):
                raise ValueError("Control metadata leaked")
            packets["__".join((*key, profile))] = sha256_json(packet)
    if len(seen) != 4 or len(set(packets.values())) != 12:
        raise ValueError("Incomplete bilingual reference coverage")
    return {"status": "structural_not_clinical_validation", "new_standalone_families": 2,
            "variants": 4, "mapped_criterion_positions": 14, "bilingual_requirement_instances": 28,
            "initial_references": 4, "update_references": 12, "packet_hashes": packets,
            "live_calls": 0, "numeric_scores": 0, "default_portfolio_additions": 0,
            "artifact_hashes": {k: sha256_json(v) for k, v in data.items()}}


def audit(root):
    root = Path(root)
    data = {name: load_json(root / path) for name, path in FILES.items()}
    result = validate(data)
    # Legacy helper deliberately excludes Q; add it and other new authoring files.
    existing = list(shared.existing_cases(root))
    for path in [root / shared.FILES["cases"], *sorted((root / "data/authoring").glob("*cases.json"))]:
        if path == root / FILES["cases"]:
            continue
        existing.extend((path, f["family_id"], f["source_refs"]) for f in load_json(path)["families"])
    matches = set()
    for path, fid, refs in existing:
        if fid in FAMILIES:
            raise ValueError("Family identity overlaps public/reserved inputs")
        keys = {shared.source_key(url) for url in refs}
        for record in data["provenance"]["records"]:
            if keys & shared.source_keys(record["report"]):
                raise ValueError("Report overlaps existing source; grouping decision required")
            for url in record["supporting_sources"]:
                if shared.source_key(url) in keys:
                    matches.add((record["family_id"], fid, str(path.relative_to(root)), url))
    registry = load_json(root / "config/benchmark.json")
    if FILES["cases"] in registry["multiturn_cases_paths"]:
        raise ValueError("Standalone batch entered default test registry")
    result["overlap_check"] = {"existing_family_file_pairs_checked": len(existing),
        "report_identity_overlaps": 0, "shared_guidance": [list(x) for x in sorted(matches)],
        "limit": "Visible normalized URL/DOI/PMID/PMCID only; no semantic independence claim. Related-family grouping is explicit in provenance."}
    return result


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
