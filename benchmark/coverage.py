"""Machine-readable coverage audit for draft family-level planning."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


TRIAGE_TARGETS = ("emergency", "timely_nonemergency", "routine", "self_care")
AUDIENCE_TARGETS = ("patient", "clinician")
INTERACTION_TARGETS = ("single_turn", "multi_turn")


def audit_coverage(
    cases: list[dict[str, Any]], tags: dict[str, Any], splits: dict[str, Any],
    labels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        families[case["metadata"]["case_family_id"]].append(case)
    family_ids = set(families)
    annotations = tags["families"]
    if set(annotations) != family_ids:
        raise ValueError("Coverage tags must contain exactly the configured case families")
    split_lists = splits["splits"]
    if set(split_lists) != {"development", "calibration", "hidden_gold"}:
        raise ValueError("Family splits must define development, calibration, and hidden_gold")
    assigned = [family_id for members in split_lists.values() for family_id in members]
    if len(assigned) != len(set(assigned)) or set(assigned) != family_ids:
        raise ValueError("Every configured family must belong to exactly one split")

    by_category = Counter()
    by_audience = Counter()
    by_interaction = Counter()
    triage_acuity = Counter()
    for family_id, pair in families.items():
        if {case["language"] for case in pair} != {"en", "zh-Hans"} or len(pair) != 2:
            raise ValueError(f"Incomplete bilingual family: {family_id}")
        categories = {case["category"] for case in pair}
        if len(categories) != 1:
            raise ValueError(f"Mixed categories in family: {family_id}")
        category = next(iter(categories))
        annotation = annotations[family_id]
        if set(annotation) != {"audience", "interaction", "acuity"}:
            raise ValueError(f"Incomplete coverage tags: {family_id}")
        audience, interaction, acuity = (
            annotation["audience"], annotation["interaction"], annotation["acuity"]
        )
        if audience not in AUDIENCE_TARGETS or interaction not in INTERACTION_TARGETS:
            raise ValueError(f"Invalid audience or interaction: {family_id}")
        if (category == "triage" and acuity not in TRIAGE_TARGETS) or (
            category != "triage" and acuity != "not_applicable"
        ):
            raise ValueError(f"Invalid acuity for {family_id}")
        by_category[category] += 1
        by_audience[audience] += 1
        by_interaction[interaction] += 1
        if category == "triage":
            triage_acuity[acuity] += 1

    result = {
        "family_count": len(families),
        "prompt_count": len(cases),
        "by_category": dict(sorted(by_category.items())),
        "by_audience": dict(sorted(by_audience.items())),
        "by_interaction": dict(sorted(by_interaction.items())),
        "triage_acuity": dict(sorted(triage_acuity.items())),
        "split_counts": {name: len(members) for name, members in split_lists.items()},
        "missing_audiences": [item for item in AUDIENCE_TARGETS if not by_audience[item]],
        "missing_interactions": [item for item in INTERACTION_TARGETS if not by_interaction[item]],
        "missing_triage_acuity": [item for item in TRIAGE_TARGETS if not triage_acuity[item]],
        "note": "Coverage tags are author hypotheses; they do not establish case quality or observed difficulty.",
    }
    if labels is not None:
        if set(labels["families"]) != family_ids:
            raise ValueError("Analytic labels must contain exactly the configured case families")
        operations = Counter()
        complexities = Counter()
        for family_id in family_ids:
            for operation in set(labels["families"][family_id]["reasoning_operation"]):
                operations[operation] += 1
            for complexity in set(labels["families"][family_id]["complexity"]):
                complexities[complexity] += 1
        result["by_reasoning_operation"] = dict(sorted(operations.items()))
        result["by_complexity_tag"] = dict(sorted(complexities.items()))
        result["complexity_caution"] = (
            "Author tags count intended probes, not demonstrated reasoning difficulty; "
            "longitudinal descriptions in one prompt are not multi-turn evaluation."
        )
    return result
