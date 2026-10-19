"""Version-bound provisional requirement anchors for development-only judge audits."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .multiturn import variant_hash
from .provenance import sha256_json


def validate_anchor_set(anchors: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    if (not isinstance(anchors, dict) or set(anchors) != {"schema_version", "status", "scope", "levels", "families"}
        or anchors["schema_version"] != "0.1.0"
        or anchors["status"] != "provisional_development_only_not_clinically_or_linguistically_reviewed"
        or set(anchors["levels"]) != {"met", "partial", "missed", "unclear"}):
        raise ValueError("Invalid provisional criterion anchor set")
    families = {family["family_id"]: family for family in dataset["families"]}
    seen = set()
    for item in anchors["families"]:
        family_id = item.get("family_id")
        if family_id in seen or family_id not in families or set(item) != {
            "family_id", "case_hashes", "evidence_url", "evidence_note", "stages",
            "critical_error_boundary", "review_question",
        }:
            raise ValueError("Unknown, duplicate, or malformed criterion family")
        seen.add(family_id)
        family = families[family_id]
        if (set(item["case_hashes"]) != {"en", "zh-Hans"}
            or not item["evidence_url"].startswith("https://")
            or item["evidence_url"] not in family["source_refs"]
            or set(item["stages"]) != {"initial", "update"}):
            raise ValueError("Criterion evidence or language binding is invalid")
        for language in ("en", "zh-Hans"):
            if item["case_hashes"][language] != variant_hash(family, language):
                raise ValueError(f"Stale criterion anchor case hash: {family_id}/{language}")
            for turn in family["variants"][language]["turns"]:
                criteria = item["stages"][turn["stage_id"]]
                if len(criteria) != len(turn["critical_requirements"]):
                    raise ValueError("Criterion count does not match case requirements")
                for criterion in criteria:
                    if set(criterion) != {"met", "partial", "missed", "acceptable_equivalent"} or any(
                        not isinstance(value, str) or not value.strip() for value in criterion.values()
                    ):
                        raise ValueError("Criterion anchor is incomplete")
    if not seen:
        raise ValueError("Empty criterion anchor set")
    return {"family_count": len(seen), "variant_count": 2 * len(seen),
            "anchor_sha256": sha256_json(anchors), "status": anchors["status"]}


def attach_anchors(packet: dict[str, Any], anchors: dict[str, Any]) -> dict[str, Any]:
    language = packet["language"]
    suffix = "-EN" if language == "en" else "-ZH-HANS"
    if not packet["case_id"].endswith(suffix):
        raise ValueError("Criterion anchor language does not match case ID")
    family_id = packet["case_id"][:-len(suffix)]
    item = next((entry for entry in anchors["families"] if entry["family_id"] == family_id), None)
    if item is None or item["case_hashes"].get(language) != packet["case_content_hash"]:
        raise ValueError("No matching criterion anchors for this exact case revision")
    result = deepcopy(packet)
    result["criterion_anchor_version"] = anchors["schema_version"]
    result["criterion_anchor_sha256"] = sha256_json(anchors)
    result["criterion_anchors"] = [
        {"stage_id": turn["stage_id"], "requirement_index": index,
         "requirement": requirement, **item["stages"][turn["stage_id"]][index - 1]}
        for turn in packet["turn_labels"]
        for index, requirement in enumerate(turn["critical_requirements"], 1)
    ]
    result["anchor_evidence_url"] = item["evidence_url"]
    result["anchor_review_question"] = item["review_question"]
    return result
