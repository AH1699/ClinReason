"""Exact-revision checks for authored batch-G bilingual judge probes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import load_json
from .frozen_batch_g import load_batch_g_dataset
from .criterion_anchors import validate_anchor_set
from .multiturn import merge_multiturn_datasets, variant_hash, variant_id
from .provenance import sha256_json


PROBE_FIELDS = {
    "family_id", "language", "case_content_hash", "expected_unsafe_error_id",
    "initial_response", "safe_update_response", "partial_update_response",
    "unsafe_update_response",
}
ANSWER_FIELDS = (
    "initial_response", "safe_update_response", "partial_update_response",
    "unsafe_update_response",
)


def validate_contrast_set(probes: dict[str, Any], dataset: dict[str, Any],
                          anchors: dict[str, Any]) -> dict[str, Any]:
    validate_anchor_set(anchors, dataset)
    if (not isinstance(probes, dict) or set(probes) != {"schema_version", "status", "scope", "probes"}
        or probes["schema_version"] != "0.1.0"
        or probes["status"] != "synthetic_unreviewed_development_probes_not_clinical_truth"
        or not isinstance(probes["scope"], str) or not probes["scope"].strip()
        or not isinstance(probes["probes"], list)):
        raise ValueError("Invalid batch-G contrast set")
    families = {family["family_id"]: family for family in dataset["families"]}
    expected = {(item["family_id"], language)
                for item in anchors["families"] for language in ("en", "zh-Hans")}
    seen = set()
    for probe in probes["probes"]:
        if not isinstance(probe, dict) or set(probe) != PROBE_FIELDS:
            raise ValueError("Malformed batch-G contrast")
        key = probe["family_id"], probe["language"]
        if key in seen or key not in expected:
            raise ValueError("Duplicate or unanchored batch-G contrast")
        seen.add(key)
        family = families[key[0]]
        if probe["case_content_hash"] != variant_hash(family, key[1]):
            raise ValueError(f"Stale batch-G contrast: {variant_id(family, key[1])}")
        update_errors = {error["id"] for error in family["variants"][key[1]]["turns"][1]["critical_errors"]}
        if probe["expected_unsafe_error_id"] not in update_errors:
            raise ValueError("Contrast unsafe error is not configured on the update turn")
        answers = [probe[field] for field in ANSWER_FIELDS]
        if any(not isinstance(answer, str) or not answer.strip() for answer in answers) or len(set(answers)) != 4:
            raise ValueError("Contrast answers must be distinct nonempty text")
        # Fixture language sanity only: not a proficiency or equivalence assessment.
        if key[1] == "zh-Hans" and any(sum('\u3400' <= char <= '\u9fff' for char in answer) < 3 for answer in answers):
            raise ValueError("Chinese contrast lacks Chinese-script text")
        if key[1] == "en" and any(sum('\u3400' <= char <= '\u9fff' for char in answer) >= 3 for answer in answers):
            raise ValueError("English contrast contains substantial Chinese-script text")
    if seen != expected:
        raise ValueError("Batch-G contrast set must cover each anchored EN/ZH variant exactly once")
    return {"status": probes["status"], "probe_count": len(seen),
            "contrast_sha256": sha256_json(probes), "anchors_sha256": sha256_json(anchors),
            "note": "Structural checks only; ordering and clinical validity remain untested."}


def select_contrast(probes: dict[str, Any], case_id: str, dataset: dict[str, Any],
                    anchors: dict[str, Any]) -> dict[str, Any]:
    validate_contrast_set(probes, dataset, anchors)
    for probe in probes["probes"]:
        family = next(item for item in dataset["families"] if item["family_id"] == probe["family_id"])
        if variant_id(family, probe["language"]) == case_id:
            return {"schema_version": "0.1.0", "status": "synthetic_unreviewed_development_probe", **probe}
    raise ValueError("Selected case is not in batch-G contrast set")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate authored batch-G contrast bindings offline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    root = args.root
    dataset = load_batch_g_dataset(root)
    anchors = load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json")
    probes = load_json(root / "data/multiturn/batch_g_contrasts_v1.json")
    print(json.dumps(validate_contrast_set(probes, dataset, anchors), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
