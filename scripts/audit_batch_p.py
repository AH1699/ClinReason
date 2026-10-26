"""Standalone Batch P structural/source/reference audit. No model or network calls."""

from copy import deepcopy
import json
from pathlib import Path

from benchmark.config import load_json
from benchmark.criterion_anchors import attach_anchors, validate_anchor_set
from benchmark.multiturn import validate_multiturn_dataset, variant_hash
from benchmark.multiturn_diagnostics import contrast_packet
from benchmark.provenance import sha256_json

FILES = {"cases": "data/multiturn/batch_p_cases.json",
         "anchors": "config/multiturn_criterion_anchors_batch_p_v1.json",
         "controls": "data/multiturn/batch_p_contrasts_v1.json",
         "provenance": "data/multiturn/batch_p_provenance.json"}
FAMILIES = {"HC-MT-REASON-025", "HC-MT-TRIAGE-024"}


def materialize(probe):
    value = deepcopy(probe)
    separator = " " if value["language"] == "en" else ""
    value["safe_update_response"] = separator.join(value["safe_components"])
    value["partial_update_response"] = separator.join(value["safe_components"][:2])
    return value


def validate(data):
    dataset, anchors, controls, provenance = (data[k] for k in ("cases", "anchors", "controls", "provenance"))
    summary = validate_multiturn_dataset(dataset)
    validate_anchor_set(anchors, dataset)
    families = {f["family_id"]: f for f in dataset["families"]}
    records = {r["family_id"]: r for r in provenance["records"]}
    if (set(families) != FAMILIES or set(records) != FAMILIES or len(provenance["records"]) != 2
            or {a["family_id"] for a in anchors["families"]} != FAMILIES
            or len(anchors["families"]) != 2
            or controls["status"] != "author_controlled_unscored_development_only"
            or provenance["split"] != "standalone_public_authoring_draft_not_default_development_calibration_or_gold"):
        raise ValueError("Wrong standalone coverage/status")
    for fid, family in families.items():
        record = records[fid]
        expected = {lang: variant_hash(family, lang) for lang in family["variants"]}
        if (record["case_hashes"] != expected or record["review_complete"] is not False
                or record["supporting_sources"] != family["source_refs"]
                or record["report"]["url"] not in family["source_refs"]
                or record["privacy_check"]["private_records_used"] is not False
                or record["privacy_check"]["source_patient_reconstructed"] is not False):
            raise ValueError("Source/version/privacy binding changed")
        positions = [(stage, i) for stage in ("initial", "update") for i in range(1,4)]
        if [(r["stage"], r["index"]) for r in record["requirement_support"]] != positions:
            raise ValueError("Incomplete ordered source mapping")
        for item in record["requirement_support"]:
            if (item["case_hashes"] != expected or item["guidance_url"] not in family["source_refs"]
                    or not item["source_locator"].strip() or not item["basis"].strip()):
                raise ValueError("Missing support or stale source mapping")
    seen, packets = set(), {}
    for probe in controls["probes"]:
        key = probe["family_id"], probe["language"]
        if key in seen or key[0] not in families or key[1] not in ("en", "zh-Hans"):
            raise ValueError("Missing/duplicate reference language")
        seen.add(key)
        family = families[key[0]]
        if (probe["case_content_hash"] != variant_hash(family, key[1])
                or type(probe["partial_omitted_requirement_index"]) is not int
                or probe["partial_omitted_requirement_index"] != 3
                or len(probe["safe_components"]) != 3
                or any(not isinstance(t, str) or not t.strip() for t in
                       [probe["initial_response"], probe["unsafe_update_response"], *probe["safe_components"]])
                or probe["expected_unsafe_error_id"] not in {
                    e["id"] for e in family["variants"][key[1]]["turns"][1]["critical_errors"]}):
            raise ValueError("Invalid reference/contrast binding")
        for profile in ("safe", "partial", "unsafe"):
            packet = attach_anchors(contrast_packet(family, materialize(probe), profile), anchors)
            if any(k in packet for k in ("safe_components", "author_expectations", "profile", "expected_unsafe_error_id")):
                raise ValueError("Author metadata leaked to judge")
            packets["__".join((*key, profile))] = sha256_json(packet)
    if len(seen) != 4 or len(set(packets.values())) != 12:
        raise ValueError("Incomplete/duplicated blinded contrasts")
    return {"status": "structural_not_clinical_validation", "new_standalone_families": 2,
        "variants": 4, "mapped_criterion_positions": 12, "initial_references": 4,
        "update_references": 12, "default_portfolio_additions": 0,
        "triage_transitions": summary["triage_transitions"], "packet_hashes": packets,
        "live_calls": 0, "numeric_scores": 0,
        "artifact_hashes": {k: sha256_json(v) for k,v in data.items()}}


def audit(root):
    data = {name: load_json(root / path) for name,path in FILES.items()}
    for folder in ("data/alpha", "data/multiturn", "data/professional", "data/confirmation", "data/calibration"):
        for path in (root / folder).glob("*.json"):
            if path == root / FILES["cases"]: continue
            value = load_json(path)
            if isinstance(value, dict) and any(f.get("family_id") in FAMILIES for f in value.get("families", []) if isinstance(f, dict)):
                raise ValueError("New case identity overlaps another dataset/reservation")
    return validate(data)


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
