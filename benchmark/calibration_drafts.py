"""Structural checks for unreviewed prospective calibration material.

These checks bind artifacts to exact case revisions. They cannot establish medical
correctness, bilingual equivalence, or that a judge will rank the answers well.
"""

from __future__ import annotations

from typing import Any

from .criterion_anchors import validate_anchor_set
from .multiturn import variant_hash
from .provenance import sha256_json


def validate_calibration_contrasts(
    contrasts: dict[str, Any], dataset: dict[str, Any], anchors: dict[str, Any]
) -> dict[str, Any]:
    anchor_status = validate_anchor_set(anchors, dataset)
    if (not isinstance(contrasts, dict)
        or set(contrasts) != {"schema_version", "status", "scope", "families"}
        or contrasts["schema_version"] != "0.1.0"
        or contrasts["status"] != "synthetic_unreviewed_calibration_probe_not_ground_truth"
        or not isinstance(contrasts["scope"], str) or not contrasts["scope"].strip()
        or not isinstance(contrasts["families"], list)):
        raise ValueError("Invalid calibration contrast collection")
    families = {family["family_id"]: family for family in dataset["families"]}
    anchor_ids = {family["family_id"] for family in anchors["families"]}
    seen: set[str] = set()
    response_fields = {
        "case_content_hash", "initial_response", "strong_update_response",
        "partial_update_response", "unsafe_update_response",
        "partial_target_requirement_index", "unsafe_error_id",
    }
    for entry in contrasts["families"]:
        if (not isinstance(entry, dict) or set(entry) != {"family_id", "variants"}
            or entry["family_id"] not in families or entry["family_id"] in seen
            or not isinstance(entry["variants"], dict)
            or set(entry["variants"]) != {"en", "zh-Hans"}):
            raise ValueError("Invalid calibration contrast family or language pair")
        family_id = entry["family_id"]
        seen.add(family_id)
        case = families[family_id]
        target_indexes: set[int] = set()
        unsafe_ids: set[str] = set()
        for language, variant in entry["variants"].items():
            if not isinstance(variant, dict) or set(variant) != response_fields:
                raise ValueError("Invalid calibration contrast fields")
            if variant["case_content_hash"] != variant_hash(case, language):
                raise ValueError("Stale calibration contrast case hash")
            response_texts = [variant[field] for field in (
                "initial_response", "strong_update_response", "partial_update_response",
                "unsafe_update_response",
            )]
            if any(not isinstance(text, str) or not text.strip() for text in response_texts) or len(set(response_texts)) != 4:
                raise ValueError("Calibration contrast responses must be nonempty and distinct")
            update = case["variants"][language]["turns"][1]
            index = variant["partial_target_requirement_index"]
            if type(index) is not int or not 1 <= index <= len(update["critical_requirements"]):
                raise ValueError("Invalid calibration partial-target index")
            target_indexes.add(index)
            error_ids = {error["id"] for error in update["critical_errors"]}
            if variant["unsafe_error_id"] not in error_ids:
                raise ValueError("Unknown calibration update critical-error ID")
            unsafe_ids.add(variant["unsafe_error_id"])
        if len(target_indexes) != 1 or len(unsafe_ids) != 1:
            raise ValueError("Calibration contrast targets differ across languages")
    if seen != set(families) or seen != anchor_ids:
        raise ValueError("Calibration anchors, contrasts and cases do not cover the same families")
    return {
        "status": contrasts["status"],
        "family_count": len(seen),
        "variant_count": len(seen) * 2,
        "update_response_example_count": len(seen) * 2 * 3,
        "anchor_sha256": anchor_status["anchor_sha256"],
        "contrast_sha256": sha256_json(contrasts),
        "clinical_review_complete": False,
        "language_review_complete": False,
    }
