"""Read-only standalone case/anchor/source/control checks; no credentials or network."""

from copy import deepcopy
import json
from pathlib import Path

from benchmark.config import load_json
from benchmark.criterion_anchors import attach_anchors, validate_anchor_set
from benchmark.multiturn import validate_multiturn_dataset, variant_hash
from benchmark.multiturn_diagnostics import contrast_packet
from benchmark.provenance import sha256_json


FILES = {
    "cases": "data/multiturn/batch_o_cases.json",
    "anchors": "config/multiturn_criterion_anchors_batch_o_v1.json",
    "controls": "data/multiturn/batch_o_contrasts_v1.json",
    "provenance": "data/multiturn/batch_o_provenance.json",
}
EXPECTED = {"HC-MT-REASON-024": 3, "HC-MT-MEDSAFE-020": 2}


def materialize_probe(probe):
    """Compose references without placing author expectations in a judge packet."""
    result = deepcopy(probe)
    edit = result["construction"]
    parts, separator = edit["safe_components"], edit["component_separator"]
    omitted = edit["partial_omitted_requirement_index"]
    result["safe_update_response"] = separator.join(parts)
    result["partial_update_response"] = separator.join(
        value for index, value in enumerate(parts, 1) if index != omitted)
    result["unsafe_update_response"] = separator.join(
        edit["unsafe_replacements"][str(index)] for index in range(1, 4))
    return result


def validate(dataset, anchors, controls, provenance):
    validate_multiturn_dataset(dataset)
    validate_anchor_set(anchors, dataset)
    families = {family["family_id"]: family for family in dataset["families"]}
    records = {record["family_id"]: record for record in provenance["records"]}
    if (set(families) != set(EXPECTED) or set(records) != set(EXPECTED)
            or len(dataset["families"]) != 2 or len(provenance["records"]) != 2
            or len(anchors["families"]) != 2
            or {row["family_id"] for row in anchors["families"]} != set(EXPECTED)):
        raise ValueError("Standalone Batch O family coverage differs")
    if provenance["split"] != "standalone_public_authoring_draft_not_default_development_calibration_or_gold":
        raise ValueError("Batch O is not an approved/default scoring split")
    if controls["status"] != "author_controlled_unscored_development_only":
        raise ValueError("Unexpected control status")
    for family_id, family in families.items():
        record = records[family_id]
        positions = [(turn["stage_id"], index) for turn in family["variants"]["en"]["turns"]
                     for index in range(1, len(turn["critical_requirements"]) + 1)]
        if (len(positions) != 6
                or [(row["stage"], row["index"]) for row in record["requirement_support"]] != positions
                or set(record["supporting_sources"]) != set(family["source_refs"])
                or record["report"]["license"] != "CC BY 4.0"):
            raise ValueError("Incomplete case/source mapping")
        if any(row["guidance_url"] not in family["source_refs"]
               or not row["source_locator"].strip() or not row["basis"].strip()
               for row in record["requirement_support"]):
            raise ValueError("Missing exact source location or author interpretation")
    seen, packet_hashes = set(), {}
    for probe in controls["probes"]:
        key = (probe["family_id"], probe["language"])
        if (key in seen or key[0] not in families or key[1] not in ("en", "zh-Hans")):
            raise ValueError("Unexpected or duplicate control variant")
        seen.add(key)
        family = families[key[0]]
        if probe["case_content_hash"] != variant_hash(family, key[1]):
            raise ValueError("Stale control/case binding")
        update = family["variants"][key[1]]["turns"][1]
        if probe["expected_unsafe_error_id"] not in {row["id"] for row in update["critical_errors"]}:
            raise ValueError("Unknown unsafe error")
        edit = probe["construction"]
        if (edit["component_separator"] != (" " if key[1] == "en" else "")
                or len(edit["safe_components"]) != 3
                or any(not isinstance(value, str) or not value.strip() for value in edit["safe_components"])
                or type(edit["partial_omitted_requirement_index"]) is not int
                or edit["partial_omitted_requirement_index"] != EXPECTED[key[0]]
                or set(edit["unsafe_replacements"]) != {"1", "2", "3"}
                or any(not isinstance(value, str) or not value.strip()
                       or value == edit["safe_components"][int(index) - 1]
                       for index, value in edit["unsafe_replacements"].items())
                or not isinstance(probe["initial_response"], str) or not probe["initial_response"].strip()):
            raise ValueError("Invalid authored component contrast")
        materialized = materialize_probe(probe)
        for profile in ("safe", "partial", "unsafe"):
            packet = attach_anchors(contrast_packet(family, materialized, profile), anchors)
            if any(field in packet for field in ("construction", "profile", "expected_unsafe_error_id")):
                raise ValueError("Author metadata entered judge packet")
            packet_hashes["__".join(key + (profile,))] = sha256_json(packet)
    if (seen != {(family_id, lang) for family_id in families for lang in ("en", "zh-Hans")}
            or len(set(packet_hashes.values())) != 12):
        raise ValueError("Missing or duplicated bilingual reference controls")
    return {"status": "standalone_structural_check_not_clinical_validation",
            "standalone_families": 2, "language_variants": 4, "criterion_positions": 12,
            "bilingual_criterion_positions": 24, "initial_reference_answers": 4,
            "update_reference_examples": 12, "mapped_case_reports": 2,
            "default_portfolio_additions": 0, "api_calls": 0, "numeric_scores": 0,
            "packet_hashes": packet_hashes}


def audit(root):
    data = {name: load_json(root / path) for name, path in FILES.items()}
    result = validate(data["cases"], data["anchors"], data["controls"], data["provenance"])
    # New IDs must not reuse default or separately reserved case identities.
    known_ids = set()
    for folder in ("data/alpha", "data/multiturn", "data/professional", "data/confirmation", "data/calibration"):
        for path in (root / folder).glob("*.json"):
            if path == root / FILES["cases"]:
                continue
            obj = load_json(path)
            if isinstance(obj, dict):
                known_ids.update(row.get("family_id") for row in obj.get("families", [])
                                 if isinstance(row, dict))
    if known_ids.intersection(EXPECTED):
        raise ValueError("New case ID overlaps another case/anchor/control reservation")
    result["artifact_hashes"] = {name: sha256_json(value) for name, value in data.items()}
    result["limits"] = "Draft authoring only. Counts do not measure difficulty or approve labels; no frozen registry, score, clinical gate or confirmation case changed."
    return result


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2, sort_keys=True))
