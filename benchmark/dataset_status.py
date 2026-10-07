from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .config import load_jsonl
from .validation import validate_dataset


def summarize_dataset(
    path: str | Path,
    rubric: dict[str, Any],
    authoring: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return authoring and review progress for a case JSONL dataset."""
    authoring = authoring or {}
    cases = load_jsonl(path)
    validation = validate_dataset(path, rubric, authoring)
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    clinical_review_pending: list[str] = []
    language_review_pending: list[str] = []
    source_review_pending: list[str] = []
    release_status_pending: list[str] = []

    for case in cases:
        metadata = case.get("metadata", {})
        family_id = metadata.get("case_family_id", f"unassigned:{case.get('id')}")
        families[family_id].append(case)
        case_id = str(case.get("id"))
        if not metadata.get("clinician_validated"):
            clinical_review_pending.append(case_id)
        if metadata.get("translation_method") == "machine_translation_unreviewed":
            language_review_pending.append(case_id)
        if not metadata.get("source_refs"):
            source_review_pending.append(case_id)
        if case.get("status") not in set(
            authoring.get("required_release_statuses", ["clinician_validated", "gold"])
        ):
            release_status_pending.append(case_id)

    category_families: Counter[str] = Counter()
    complete_pairs = 0
    required_languages = set(authoring.get("required_pair_languages", ["en", "zh-Hans"]))
    for family_cases in families.values():
        if family_cases:
            category_families[family_cases[0].get("category", "unknown")] += 1
        if {case.get("language") for case in family_cases} >= required_languages:
            complete_pairs += 1

    return {
        "path": str(Path(path).resolve()),
        "case_count": len(cases),
        "family_count": len(families),
        "complete_bilingual_families": complete_pairs,
        "categories_by_family": dict(sorted(category_families.items())),
        "languages_by_case": dict(sorted(Counter(case.get("language") for case in cases).items())),
        "statuses_by_case": dict(sorted(Counter(case.get("status") for case in cases).items())),
        "benchmark_layers_by_case": dict(
            sorted(
                Counter(
                    case.get("metadata", {}).get("benchmark_layer", "missing")
                    for case in cases
                ).items()
            )
        ),
        "review_queue": {
            "clinical_review_pending": sorted(clinical_review_pending),
            "language_review_pending": sorted(language_review_pending),
            "source_review_pending": sorted(source_review_pending),
            "release_status_pending": sorted(release_status_pending),
        },
        "development_validation": {
            "valid": validation["valid"],
            "error_count": validation["error_count"],
            "warning_count": validation["warning_count"],
        },
    }
