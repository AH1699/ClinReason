"""Descriptive coverage and complexity-proxy audit, never a difficulty score."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from .config import load_json
from .multiturn import merge_multiturn_datasets
from .portfolio_audit import audit_portfolio


def audit_development_gaps(root: Path) -> dict[str, Any]:
    """Audit the configured public portfolio without reading or scoring model answers."""
    root = root.resolve()
    portfolio = audit_portfolio(root)
    config = load_json(root / "config/benchmark.json")
    dataset = merge_multiturn_datasets([
        load_json(root / path) for path in config["multiturn_cases_paths"]
    ])
    families = dataset["families"]
    for batch_name in ("f", "g"):
        batch = load_json(root / f"data/multiturn/batch_{batch_name}_cases.json")
        provenance = load_json(root / f"data/multiturn/batch_{batch_name}_provenance.json")
        records = {entry["family_id"]: entry for entry in provenance["records"]}
        if (len(records) != len(provenance["records"])
            or set(records) != {family["family_id"] for family in batch["families"]}):
            raise ValueError(f"Batch-{batch_name.upper()} provenance does not exactly cover new families")
        for family in batch["families"]:
            record = records[family["family_id"]]
            cited = set(record["supporting_sources"])
            if record["published_case_or_series"] is not None:
                cited.add(record["published_case_or_series"])
            if (set(family["source_refs"]) != cited or not record["adaptation"].strip()
                or not record["source_to_label_limit"].strip()):
                raise ValueError(f"Batch-{batch_name.upper()} provenance source or limits mismatch")
    triage = [family for family in families if family["category"] == "triage"]
    source_uses = Counter(url for family in families for url in family["source_refs"])
    requirement_counts = [
        len(turn["critical_requirements"])
        for family in families for turn in family["variants"]["en"]["turns"]
    ]
    final_acuity = Counter(family["final_acuity"] for family in triage)
    transitions = Counter(
        family["initial_acuity"] + "→" + family["final_acuity"] for family in triage
    )
    return {
        "status": "author_descriptive_audit_not_observed_difficulty_or_clinical_validation",
        "public_development_family_count": portfolio["family_count"],
        "public_development_language_variant_count": portfolio["language_variant_count"],
        "track_counts": portfolio["tracks"],
        "approved_calibration_family_count": portfolio["calibration_family_count"],
        "hidden_gold_family_count": portfolio["hidden_gold_family_count"],
        "criterion_level_verified_source_mapping_count": portfolio[
            "families_with_criterion_level_verified_source_mapping"
        ],
        "patient_multiturn": {
            "family_count": len(families),
            "category_counts": dict(sorted(Counter(f["category"] for f in families).items())),
            "triage_transition_counts": dict(sorted(transitions.items())),
            "triage_final_acuity_counts": dict(sorted(final_acuity.items())),
            "triage_ending_below_emergency_count": sum(
                family["final_acuity"] != "emergency" for family in triage
            ),
            "distinct_public_source_url_count": len(source_uses),
            "single_source_family_count": sum(len(f["source_refs"]) == 1 for f in families),
            "source_urls_used_by_multiple_families": {
                url: count for url, count in sorted(source_uses.items()) if count > 1
            },
            "en_requirement_count_per_turn": {
                "min": min(requirement_counts), "median": median(requirement_counts),
                "max": max(requirement_counts),
            },
            "update_severity_3_error_family_count": sum(
                any(error["severity"] == 3 for error in family["variants"]["en"]["turns"][1]["critical_errors"])
                for family in families
            ),
        },
        "interpretation_limits": [
            "Author category and severity tags are unreviewed hypotheses, not observed case difficulty.",
            "A source URL count does not prove source-to-criterion support or source independence.",
            "This audit does not inspect model responses or establish clinical correctness or bilingual equivalence.",
            "Public development cases cannot later be relabeled hidden Gold.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit configured development coverage")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    print(json.dumps(audit_development_gaps(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
