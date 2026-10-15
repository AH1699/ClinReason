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


def combine_professional_datasets(datasets: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate separate authoring batches before presenting one professional track."""
    if not datasets:
        raise ValueError("Professional dataset list cannot be empty")
    families: list[dict[str, Any]] = []
    seen: set[str] = set()
    for dataset in datasets:
        validate_professional_dataset(dataset)
        for family in dataset["families"]:
            family_id = family["family_id"]
            if family_id in seen:
                raise ValueError(f"Duplicate professional family across batches: {family_id}")
            seen.add(family_id)
            families.append(family)
    combined = {
        "schema_version": "0.1.0",
        "track": "clinician_facing_professional",
        "status": "draft_development_only",
        "scope": "Combined authoring batches; public evidence only; clinical and bilingual review pending.",
        "families": families,
    }
    validate_professional_dataset(combined)
    return combined


def validate_case_adaptation_registry(registry: Any, dataset: dict[str, Any]) -> dict[str, int]:
    """Bind source-derived drafts to explicit article attribution and reuse status."""
    validate_professional_dataset(dataset)
    if (not isinstance(registry, dict) or set(registry) != {
        "schema_version", "status", "policy", "records",
    } or registry["schema_version"] != "0.1.0"
        or registry["status"] != "development_provenance_not_clinical_validation"
        or not isinstance(registry["policy"], str) or not registry["policy"].strip()
        or not isinstance(registry["records"], list) or not registry["records"]):
        raise ValueError("Invalid case-adaptation registry")
    families = {item["family_id"]: item for item in dataset["families"]}
    seen: set[str] = set()
    for record in registry["records"]:
        if not isinstance(record, dict) or set(record) != {
            "family_id", "source_type", "source_title", "source_url", "attribution",
            "license", "license_url", "verified_on", "case_text_mode", "changes", "limitations",
        }:
            raise ValueError("Invalid case-adaptation record")
        family_id = record["family_id"]
        if family_id in seen or family_id not in families:
            raise ValueError(f"Duplicate or unknown adaptation family: {family_id}")
        seen.add(family_id)
        if (record["source_type"] != "published_case_report"
            or record["case_text_mode"] != "synthetic_adaptation"
            or record["license"] not in {"CC BY", "CC BY 4.0"}
            or record["license_url"] != "https://creativecommons.org/licenses/by/4.0/"
            or record["source_url"] not in families[family_id]["source_refs"]
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", record["verified_on"])
            or any(not isinstance(record[key], str) or not record[key].strip()
                   for key in ("source_title", "attribution", "changes", "limitations"))):
            raise ValueError(f"Unverified adaptation provenance: {family_id}")
    article_sourced = {
        family_id for family_id, family in families.items()
        if any(source.startswith("https://pmc.ncbi.nlm.nih.gov/articles/PMC")
               for source in family["source_refs"])
    }
    if seen != article_sourced:
        raise ValueError("Published-case families and adaptation records must match")
    return {"adapted_family_count": len(seen), "adapted_variant_count": len(seen) * 2}


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
