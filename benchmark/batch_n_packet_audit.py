"""Offline exact-case/source/answer construction checks for batch N, not scoring."""

import json
from pathlib import Path

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn import validate_multiturn_dataset, variant_hash
from .multiturn_diagnostics import contrast_packet
from .provenance import sha256_json

FAMILY = "HC-MT-MEDSAFE-019"


def validate_packet(dataset, anchors, contrasts, provenance):
    validate_multiturn_dataset(dataset)
    validate_anchor_set(anchors, dataset)
    if ([f["family_id"] for f in dataset["families"]] != [FAMILY]
            or [f["family_id"] for f in anchors["families"]] != [FAMILY]
            or [r["family_id"] for r in provenance["records"]] != [FAMILY]):
        raise ValueError("Batch N family/source/anchor coverage mismatch")
    family, record = dataset["families"][0], provenance["records"][0]
    positions = [(t["stage_id"], i) for t in family["variants"]["en"]["turns"]
                 for i in range(1, len(t["critical_requirements"]) + 1)]
    if (len(positions) != 7 or [(r["stage"], r["index"]) for r in record["requirement_support"]] != positions
            or set(record["supporting_sources"]) != set(family["source_refs"])
            or any(r["guidance_url"] not in family["source_refs"] or not r["basis"].strip()
                   for r in record["requirement_support"])):
        raise ValueError("Incomplete batch N source mapping")
    if (contrasts["schema_version"] != "0.1.0"
            or contrasts["status"] != "author_controlled_unscored_development_only"):
        raise ValueError("Unexpected batch N control status")
    seen, hashes = set(), {}
    for probe in contrasts["probes"]:
        language = probe["language"]
        if probe["family_id"] != FAMILY or language not in ("en", "zh-Hans") or language in seen:
            raise ValueError("Unknown or duplicate control variant")
        seen.add(language)
        if probe["case_content_hash"] != variant_hash(family, language):
            raise ValueError("Stale control case hash")
        turn = family["variants"][language]["turns"][1]
        if (probe["expected_unsafe_error_id"] != "CE-MT-MEDSAFE-019-DISCHARGE"
                or probe["expected_unsafe_error_id"] not in {e["id"] for e in turn["critical_errors"]}):
            raise ValueError("Invented critical error")
        edit = probe["construction"]
        parts, replacements = edit["safe_components"], edit["unsafe_replacements"]
        sep = edit["component_separator"]
        if (not isinstance(parts, list) or len(parts) != 4
                or any(not isinstance(s, str) or not s.strip() for s in parts)
                or type(edit["partial_omitted_requirement_index"]) is not int
                or edit["partial_omitted_requirement_index"] != 3
                or not isinstance(replacements, dict) or set(replacements) != {"1", "2", "3", "4"}
                or any(not isinstance(v, str) or not v.strip() or v == parts[int(k) - 1]
                       for k, v in replacements.items())
                or sep != (" " if language == "en" else "")):
            raise ValueError("Invalid paired answer edits")
        expected = {"safe": sep.join(parts), "partial": sep.join(s for i, s in enumerate(parts, 1) if i != 3),
                    "unsafe": sep.join(replacements[str(i)] for i in range(1, 5))}
        if not isinstance(probe["initial_response"], str) or not probe["initial_response"].strip():
            raise ValueError("Missing initial response")
        for profile, response in expected.items():
            if probe[f"{profile}_update_response"] != response:
                raise ValueError("Response differs from declared edits")
            packet = attach_anchors(contrast_packet(family, probe, profile), anchors)
            if any(field in packet for field in ("construction", "profile", "expected_unsafe_error_id")):
                raise ValueError("Author metadata leaked into judge packet")
            hashes[f"{FAMILY}__{language}__{profile}"] = sha256_json(packet)
    if seen != {"en", "zh-Hans"}:
        raise ValueError("Missing paired language")
    if len(set(hashes.values())) != 6:
        raise ValueError("Controls must produce six distinct packets")
    return {"status": "offline_structural_check_not_clinical_or_score_validation",
            "family_count": 1, "variant_count": 2, "criterion_positions": 7,
            "bilingual_criterion_positions": 14, "shared_initial_answers": 2, "update_answer_examples": 6,
            "packet_hashes": hashes, "candidate_calls": 0, "judge_calls": 0,
            "limits": "Partial deletes the specialist/removal component; unsafe replaces four linked components. No single-criterion causal claim, numeric score, clinical approval or default-judge integration."}


def audit(root):
    return validate_packet(load_json(root / "data/multiturn/batch_n_cases.json"),
        load_json(root / "config/multiturn_criterion_anchors_batch_n_v1.json"),
        load_json(root / "data/multiturn/batch_n_contrasts_v1.json"),
        load_json(root / "data/multiturn/batch_n_provenance.json"))


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), indent=2))
