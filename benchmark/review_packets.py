from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .reviews import case_content_hash


FAMILY_ID_PATTERN = re.compile(r"^[A-Z0-9_-]+$")


def _block(value: str) -> str:
    """Keep case text readable without treating its Markdown as packet markup."""
    return "\n".join(f"    {line}" for line in value.splitlines())


def render_family_packet(family_id: str, cases: list[dict[str, Any]]) -> str:
    """Render one bilingual Alpha family for independent expert review."""
    languages = {case["language"] for case in cases}
    if languages != {"en", "zh-Hans"} or len(cases) != 2:
        raise ValueError(f"Family {family_id} must contain exactly one en and one zh-Hans case")
    ordered = sorted(cases, key=lambda case: (case["language"] != "en", case["language"]))
    first = ordered[0]
    lines = [
        f"# Reviewer packet: {family_id}",
        "",
        "Development draft. Review the source guidance, case wording, expected behavior, and critical error policy independently. A packet is an assignment aid, not a completed review.",
        "",
        f"- Category: `{first['category']}`",
        f"- Subcategory: `{first.get('subcategory', '')}`",
        f"- Difficulty: `{first.get('difficulty', '')}`",
        f"- Benchmark layer: `{first['metadata'].get('benchmark_layer', '')}`",
        f"- Jurisdiction: `{first['metadata'].get('jurisdiction', '')}`",
        "- Assigned clinical reviewer(s): _unassigned_",
        "- Assigned language reviewer: _unassigned_",
        "",
    ]
    for case in ordered:
        metadata = case["metadata"]
        lines.extend(
            [
                f"## {case['language']}: {case['id']}",
                "",
                f"- Case version: `{case['version']}`",
                f"- Reviewable content SHA-256: `{case_content_hash(case)}`",
                f"- Case author ID: `{metadata.get('author_id', 'unspecified')}`",
                f"- Translation method: `{metadata.get('translation_method', 'unspecified')}`",
                f"- Effective date: `{metadata.get('effective_date', 'unspecified')}`",
                "",
                "### Prompt",
                "",
                _block(case["prompt"]),
                "",
                "### Expected behavior for reviewer",
                "",
                _block(case["reference_answer"]),
                "",
                "### Observable requirements",
                "",
            ]
        )
        lines.extend(f"{index}. {item}" for index, item in enumerate(case["critical_requirements"], 1))
        lines.extend(["", "### Critical errors", ""])
        lines.extend(
            f"- `{error['id']}` (severity {error['severity']}): {error['description']}"
            for error in case["critical_errors"]
        )
        lines.extend(["", "### Source references", ""])
        lines.extend(f"- {source}" for source in metadata.get("source_refs", []))
        lines.append("")
    lines.extend(
        [
            "## Review instructions",
            "",
            "- Clinical reviewers: assess both variants within your qualifications; record a separate clinical review for each case ID.",
            "- Language reviewer: assess the translated `zh-Hans` variant against the English original, including facts, risk level, terminology, and scoring equivalence.",
            "- Record required changes precisely. A changed prompt, reference, requirement, critical error, source interpretation, or language meaning needs a new case version and renewed affected reviews.",
            "- Generate each review with `python -m benchmark.cli --config config/benchmark.json review-template CASE_ID` and the required reviewer arguments. Store completed records in `data/reviews/development/`.",
            "- If clinical or language judgments conflict, leave the gate open and request adjudication.",
            "",
        ]
    )
    return "\n".join(lines)


def export_review_packets(cases: list[dict[str, Any]], output_dir: str | Path) -> dict[str, Any]:
    """Write one packet per family and a manifest without replacing prior work."""
    if any(case.get("status") == "gold" for case in cases):
        raise ValueError("Gold cases cannot be exported by the Alpha reviewer packet command")
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        family_id = case.get("metadata", {}).get("case_family_id")
        if not isinstance(family_id, str) or not FAMILY_ID_PATTERN.fullmatch(family_id):
            raise ValueError(f"Unsafe or missing case_family_id for case {case.get('id')}")
        families[family_id].append(case)

    packets = {
        family_id: render_family_packet(family_id, family_cases)
        for family_id, family_cases in sorted(families.items())
    }
    destination = Path(output_dir)
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Output path is not a directory: {destination}")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing to replace files in nonempty directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": "0.1.0",
        "purpose": "alpha_reviewer_assignment",
        "family_count": len(packets),
        "case_count": len(cases),
        "families": [
            {
                "case_family_id": family_id,
                "packet": f"{family_id}.md",
                "clinical_reviewer_ids": [],
                "language_reviewer_ids": [],
                "cases": [
                    {
                        "case_id": case["id"],
                        "case_version": case["version"],
                        "language": case["language"],
                        "author_id": case["metadata"].get("author_id"),
                        "case_content_hash": case_content_hash(case),
                        "required_review_types": ["clinical"]
                        + (["language_equivalence"] if case["metadata"].get("translation_method") != "original" else []),
                    }
                    for case in sorted(families[family_id], key=lambda item: item["language"])
                ],
            }
            for family_id in sorted(packets)
        ],
    }
    for family_id, packet in packets.items():
        (destination / f"{family_id}.md").write_text(packet, encoding="utf-8")
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"output_dir": str(destination.resolve()), **manifest}
