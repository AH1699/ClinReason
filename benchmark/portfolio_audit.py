"""Read-only audit of public draft families and prospective split leakage groups.

This checks structure and declared provenance, not medical truth or real difficulty.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .config import load_json, load_jsonl
from .multiturn import merge_multiturn_datasets
from .professional import combine_professional_datasets, validate_case_adaptation_registry
from .provenance import sha256_json


RELATIONSHIPS = {
    "same_core_mechanism", "same_hazard_distinct_decision",
    "possible_construct_duplicate", "shared_test_distinct_mechanism",
}


def _alpha_urls(case: dict[str, Any]) -> set[str]:
    return {
        match.rstrip(".,;")
        for source in case["metadata"]["source_refs"]
        for match in re.findall(r"https://[^\s]+", source)
    }


def _validate_queue(queue: dict[str, Any], family_ids: set[str]) -> None:
    if (set(queue) != {"schema_version", "status", "scope", "overlaps", "source_label_review"}
        or queue["schema_version"] != "0.1.0"
        or queue["status"] != "author_triage_pending_independent_review"):
        raise ValueError("Invalid portfolio review queue")
    pairs: set[tuple[str, str]] = set()
    for entry in queue["overlaps"]:
        if (set(entry) != {"family_ids", "relationship", "reason", "split_together"}
            or not isinstance(entry["family_ids"], list)
            or len(entry["family_ids"]) != 2
            or len(set(entry["family_ids"])) != 2
            or not set(entry["family_ids"]) <= family_ids
            or entry["relationship"] not in RELATIONSHIPS
            or type(entry["split_together"]) is not bool
            or not isinstance(entry["reason"], str) or not entry["reason"].strip()):
            raise ValueError("Invalid mechanism-overlap entry")
        pair = tuple(sorted(entry["family_ids"]))
        if pair in pairs:
            raise ValueError("Repeated mechanism-overlap pair")
        pairs.add(pair)
    source_ids: set[str] = set()
    for entry in queue["source_label_review"]:
        if (set(entry) != {"family_id", "priority", "issue"}
            or entry["family_id"] not in family_ids
            or entry["family_id"] in source_ids
            or entry["priority"] not in {"high", "medium", "low"}
            or not isinstance(entry["issue"], str) or not entry["issue"].strip()):
            raise ValueError("Invalid source-to-label review entry")
        source_ids.add(entry["family_id"])


def _leakage_groups(queue: dict[str, Any]) -> list[list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for entry in queue["overlaps"]:
        if entry["split_together"]:
            left, right = entry["family_ids"]
            graph[left].add(right)
            graph[right].add(left)
    seen: set[str] = set()
    groups: list[list[str]] = []
    for start in sorted(graph):
        if start in seen:
            continue
        stack = [start]
        group: set[str] = set()
        while stack:
            node = stack.pop()
            if node in group:
                continue
            group.add(node)
            stack.extend(graph[node] - group)
        seen.update(group)
        groups.append(sorted(group))
    return groups


def audit_portfolio(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config = load_json(root / "config/benchmark.json")
    alpha_rows = load_jsonl(root / config["cases_path"])
    alpha_languages: dict[str, list[str]] = defaultdict(list)
    for row in alpha_rows:
        alpha_languages[row["metadata"]["case_family_id"]].append(row["language"])
    if any(sorted(languages) != ["en", "zh-Hans"] for languages in alpha_languages.values()):
        raise ValueError("Alpha must contain exactly one English and Chinese variant per family")
    alpha = {row["metadata"]["case_family_id"]: row for row in alpha_rows if row["language"] == "en"}
    if len(alpha_rows) != len(alpha) * 2:
        raise ValueError("Alpha must contain paired English and Chinese variants")
    multiturn = merge_multiturn_datasets([
        load_json(root / path) for path in config["multiturn_cases_paths"]
    ])
    professional = combine_professional_datasets([
        load_json(root / path) for path in config["professional_cases_paths"]
    ])
    adaptations = load_json(root / config["professional_adaptations_path"])
    adaptation_status = validate_case_adaptation_registry(adaptations, professional)
    track_ids = {
        "alpha_single_turn": set(alpha),
        "patient_multiturn": {item["family_id"] for item in multiturn["families"]},
        "professional": {item["family_id"] for item in professional["families"]},
    }
    family_ids = set().union(*track_ids.values())
    if len(family_ids) != sum(map(len, track_ids.values())):
        raise ValueError("Family IDs overlap across tracks")
    queue = load_json(root / "data/audit/overlap_and_source_review.json")
    _validate_queue(queue, family_ids)
    split_plan = load_json(root / "data/audit/prospective_split_plan.json")
    current_split = split_plan["current_public_portfolio"]
    if (split_plan["status"] != "prospective_drafts_started_no_approved_calibration_or_gold"
        or current_split != {
            "development_families": len(family_ids),
            "calibration_families": 0,
            "hidden_gold_families": 0,
        }):
        raise ValueError("Prospective split plan must match the public draft portfolio")
    draft_counts = split_plan["prospective_draft_candidates_not_approved_counts"]
    integrity = split_plan["prospective_draft_integrity"]
    calibration_path = root / integrity["calibration_path"]
    calibration = load_json(calibration_path)
    calibration_status = merge_multiturn_datasets([calibration])
    calibration_ids = {item["family_id"] for item in calibration_status["families"]}
    if (calibration_ids & family_ids
        or len(calibration_ids) != draft_counts["calibration_patient_multiturn"]
        or sha256_json(calibration) != integrity["calibration_sha256"]
        or integrity["calibration_path"] in config["multiturn_cases_paths"]):
        raise ValueError("Calibration draft is not prospectively isolated or matches neither count nor hash")
    hidden_path = root / integrity["hidden_local_path_not_in_git"]
    hidden_verified: bool | None = None
    hidden_sources: set[str] = set()
    if hidden_path.exists():
        hidden = load_json(hidden_path)
        hidden_status = merge_multiturn_datasets([hidden])
        hidden_ids = {item["family_id"] for item in hidden_status["families"]}
        calibration_sources = {url for item in calibration_status["families"] for url in item["source_refs"]}
        hidden_sources = {url for item in hidden_status["families"] for url in item["source_refs"]}
        if (hidden_ids & (family_ids | calibration_ids)
            or hidden_sources & calibration_sources
            or len(hidden_ids) != draft_counts["hidden_local_patient_multiturn"]
            or sha256_json(hidden) != integrity["hidden_local_sha256"]):
            raise ValueError("Local hidden candidate failed isolation, count or integrity check")
        hidden_verified = True

    public_sources = load_json(root / "data/evidence/public_sources.json")["sources"]
    registry_by_family: dict[str, set[str]] = defaultdict(set)
    for source in public_sources:
        for family_id in source["families"]:
            if family_id not in family_ids:
                raise ValueError(f"Source registry names unknown family: {family_id}")
            registry_by_family[family_id].add(source["url"])
    missing_alpha_registry = sorted(set(alpha) - registry_by_family.keys())
    alpha_url_mismatches = sorted(
        family_id for family_id, row in alpha.items()
        if not (_alpha_urls(row) & registry_by_family[family_id])
    )
    source_users: dict[str, set[str]] = defaultdict(set)
    for family_id, row in alpha.items():
        for url in _alpha_urls(row):
            source_users[url].add(family_id)
    for dataset in (multiturn, professional):
        for family in dataset["families"]:
            for url in family["source_refs"]:
                source_users[url].add(family["family_id"])
    calibration_sources = {url for item in calibration_status["families"] for url in item["source_refs"]}
    if calibration_sources & source_users.keys():
        raise ValueError("Calibration draft reuses a public development source URL")
    if hidden_verified and hidden_sources & source_users.keys():
        raise ValueError("Local hidden candidate reuses a public development source URL")
    shared_sources = {
        url: sorted(ids) for url, ids in source_users.items() if len(ids) > 1
    }
    critical_max: Counter[str] = Counter()
    for family_id, row in alpha.items():
        critical_max[str(max((error["severity"] for error in row["critical_errors"]), default=0))] += 1
    for dataset, label in ((multiturn, "patient_multiturn"), (professional, "professional")):
        for family in dataset["families"]:
            variants = family["variants"]["en"]
            stages = variants["turns"] if label == "patient_multiturn" else [variants]
            critical_max[str(max((error["severity"] for stage in stages for error in stage["critical_errors"]), default=0))] += 1
    return {
        "status": "development_only_not_clinically_validated",
        "family_count": len(family_ids),
        "language_variant_count": len(family_ids) * 2,
        "tracks": {track: len(ids) for track, ids in track_ids.items()},
        "published_case_adaptations": adaptation_status["adapted_family_count"],
        "alpha_families_missing_source_registry": missing_alpha_registry,
        "alpha_families_without_matching_registry_url": alpha_url_mismatches,
        "families_with_criterion_level_verified_source_mapping": 0,
        "shared_source_url_count": len(shared_sources),
        "shared_source_urls": dict(sorted(shared_sources.items())),
        "max_critical_error_severity_counts": dict(sorted(critical_max.items())),
        "selected_overlap_pair_count": len(queue["overlaps"]),
        "possible_construct_duplicate_pairs": [
            entry["family_ids"] for entry in queue["overlaps"]
            if entry["relationship"] == "possible_construct_duplicate"
        ],
        "prospective_split_leakage_groups": _leakage_groups(queue),
        "prioritized_source_label_review_count": len(queue["source_label_review"]),
        "source_label_high_priority_count": sum(
            entry["priority"] == "high" for entry in queue["source_label_review"]
        ),
        "calibration_family_count": current_split["calibration_families"],
        "hidden_gold_family_count": current_split["hidden_gold_families"],
        "prospective_calibration_draft_family_count": len(calibration_ids),
        "prospective_hidden_local_draft_family_count_declared": draft_counts["hidden_local_patient_multiturn"],
        "hidden_local_draft_integrity_verified": hidden_verified,
        "note": "This is a bounded author audit. Shared URL or mechanism is not proof of duplicate content; public draft cases cannot be made genuinely hidden retroactively.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the public development portfolio")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    print(json.dumps(audit_portfolio(args.root), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
