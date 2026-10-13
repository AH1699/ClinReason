"""Separate, unreviewed clinician-facing development track."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .provenance import sha256_json


LANGUAGES = ("en", "zh-Hans")
WORKFLOWS = {"clinical_consult", "medication_reconciliation_handoff", "evidence_appraisal"}


def validate_professional_rubric(rubric: Any) -> None:
    if (not isinstance(rubric, dict) or rubric.get("id") != "clinreason-professional-rubric"
        or rubric.get("status") != "authoring_only_not_clinically_calibrated"
        or rubric.get("scale_min") != 0 or rubric.get("scale_max") != 4
        or not isinstance(rubric.get("dimensions"), list) or not rubric["dimensions"]):
        raise ValueError("Professional rubric must remain an authoring-only 0–4 draft")
    ids = set()
    weight_sum = 0.0
    for dimension in rubric["dimensions"]:
        if (not isinstance(dimension, dict) or set(dimension) != {
            "id", "weight", "label_en", "label_zh", "anchors",
        } or not isinstance(dimension["id"], str) or not dimension["id"].strip()
            or dimension["id"] in ids or type(dimension["weight"]) not in (int, float)
            or not 0 < dimension["weight"] <= 1
            or any(not isinstance(dimension[label], str) or not dimension[label].strip()
                   for label in ("label_en", "label_zh"))
            or not isinstance(dimension["anchors"], dict)
            or set(dimension["anchors"]) != {"0", "1", "2", "3", "4"}
            or any(not isinstance(value, str) or not value.strip()
                   for value in dimension["anchors"].values())):
            raise ValueError("Invalid professional rubric dimension")
        ids.add(dimension["id"])
        weight_sum += dimension["weight"]
    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError("Professional rubric weights must sum to 1")


def validate_professional_dataset(dataset: Any) -> dict[str, Any]:
    if not isinstance(dataset, dict) or set(dataset) != {"schema_version", "track", "status", "scope", "families"}:
        raise ValueError("Invalid professional dataset fields")
    if (dataset["schema_version"] != "0.1.0" or dataset["track"] != "clinician_facing_professional"
        or dataset["status"] != "draft_development_only"
        or not isinstance(dataset["scope"], str) or not dataset["scope"].strip()):
        raise ValueError("Professional dataset must be a scoped development draft")
    families = dataset["families"]
    if not isinstance(families, list) or not families:
        raise ValueError("Professional dataset needs families")
    seen: set[str] = set()
    workflows: Counter[str] = Counter()
    for family in families:
        if not isinstance(family, dict) or set(family) != {
            "family_id", "version", "workflow", "specialty", "jurisdiction",
            "failure_mode", "source_refs", "variants",
        }:
            raise ValueError("Invalid professional family fields")
        family_id = family["family_id"]
        if (not isinstance(family_id, str) or not re.fullmatch(r"HC-PRO-[A-Z]+-\d{3}", family_id)
            or family_id in seen):
            raise ValueError(f"Invalid or duplicate professional family: {family_id}")
        seen.add(family_id)
        if not isinstance(family["version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+", family["version"]):
            raise ValueError(f"Invalid professional version: {family_id}")
        if family["workflow"] not in WORKFLOWS or family["jurisdiction"] != "global_core":
            raise ValueError(f"Unsupported workflow or jurisdiction: {family_id}")
        for field in ("specialty", "failure_mode"):
            if not isinstance(family[field], str) or not family[field].strip():
                raise ValueError(f"Missing {field}: {family_id}")
        sources = family["source_refs"]
        if (not isinstance(sources, list) or not sources
            or any(not isinstance(source, str) or not source.startswith("https://") for source in sources)
            or len(sources) != len(set(sources))):
            raise ValueError(f"Missing public source refs: {family_id}")
        variants = family["variants"]
        if not isinstance(variants, dict) or set(variants) != set(LANGUAGES):
            raise ValueError(f"Professional family needs exactly two language variants: {family_id}")
        error_signature: list[tuple[str, int]] | None = None
        for language in LANGUAGES:
            variant = variants[language]
            if not isinstance(variant, dict) or set(variant) != {
                "translation_method", "prompt", "reference_elements", "critical_errors",
            }:
                raise ValueError(f"Invalid professional variant: {family_id}/{language}")
            method = "original" if language == "en" else "machine_translation_unreviewed"
            if variant["translation_method"] != method:
                raise ValueError(f"Unreviewed language status changed: {family_id}/{language}")
            if not isinstance(variant["prompt"], str) or not variant["prompt"].strip():
                raise ValueError(f"Empty professional prompt: {family_id}/{language}")
            elements = variant["reference_elements"]
            if (not isinstance(elements, list) or not elements
                or any(not isinstance(element, str) or not element.strip() for element in elements)):
                raise ValueError(f"Missing professional reference elements: {family_id}/{language}")
            errors = variant["critical_errors"]
            if not isinstance(errors, list):
                raise ValueError(f"Invalid professional critical errors: {family_id}/{language}")
            signature: list[tuple[str, int]] = []
            for error in errors:
                if (not isinstance(error, dict) or set(error) != {"id", "severity", "description"}
                    or not isinstance(error["id"], str)
                    or not error["id"].startswith(f"CE-PRO-{family_id.removeprefix('HC-PRO-')}-")
                    or type(error["severity"]) is not int or not 1 <= error["severity"] <= 3
                    or not isinstance(error["description"], str) or not error["description"].strip()):
                    raise ValueError(f"Invalid professional critical error: {family_id}/{language}")
                signature.append((error["id"], error["severity"]))
            if len(signature) != len(set(signature)):
                raise ValueError(f"Duplicate professional critical error: {family_id}/{language}")
            if error_signature is None:
                error_signature = signature
            elif signature != error_signature:
                raise ValueError(f"Bilingual professional critical-error mismatch: {family_id}")
        workflows[family["workflow"]] += 1
    return {
        "status": "draft_development_only",
        "track": "clinician_facing_professional",
        "family_count": len(families),
        "variant_count": len(families) * len(LANGUAGES),
        "workflow_counts": dict(sorted(workflows.items())),
        "clinical_review_complete": False,
        "language_review_complete": False,
        "scoring_enabled": False,
    }


def professional_candidate_rows(
    dataset: dict[str, Any], *, instruction: str, prompt_template_version: str,
) -> list[dict[str, Any]]:
    validate_professional_dataset(dataset)
    if not instruction.strip() or not prompt_template_version.strip():
        raise ValueError("Professional candidate instruction and version are required")
    rows = []
    for family in sorted(dataset["families"], key=lambda item: item["family_id"]):
        for language in LANGUAGES:
            variant = family["variants"][language]
            rows.append({
                "exchange_version": "0.1.0",
                "track": dataset["track"],
                "case_id": f"{family['family_id']}-{'EN' if language == 'en' else 'ZH-HANS'}",
                "case_version": family["version"],
                "case_content_hash": sha256_json({
                    "family_id": family["family_id"], "version": family["version"],
                    "workflow": family["workflow"], "specialty": family["specialty"],
                    "jurisdiction": family["jurisdiction"], "source_refs": family["source_refs"],
                    "variant": variant,
                }),
                "language": language,
                "prompt_template_version": prompt_template_version,
                "instruction": instruction,
                "prompt": variant["prompt"],
            })
    return rows


def export_professional_prompts(rows: list[dict[str, Any]], output_path: str | Path) -> int:
    if not rows or any(row.get("track") != "clinician_facing_professional" for row in rows):
        raise ValueError("Expected professional candidate rows")
    target = Path(output_path)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite professional prompt export: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)
