"""Offline, two-phase reviewer handoff for prospective calibration drafts.

The first packet hides author-intended answer classes, family IDs, source links,
and criterion labels. The follow-up packet exposes draft evidence and criteria
only after independent phase-A ratings are locked. Neither packet is approval.
"""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path
from typing import Any

from .calibration_drafts import validate_calibration_contrasts
from .config import load_json
from .multiturn import merge_multiturn_datasets, variant_hash
from .portfolio_audit import audit_portfolio
from .provenance import sha256_json, sha256_text


LANGUAGES = ("en", "zh-Hans")
OPTION_IDS = ("A", "B", "C")
RESPONSE_FIELDS = {
    "strong": "strong_update_response",
    "partial": "partial_update_response",
    "unsafe": "unsafe_update_response",
}


def _indented(value: str) -> str:
    return "\n".join("    " + line for line in value.splitlines())


def _render_phase_a(item: dict[str, Any]) -> str:
    lines = [
        f"# Blind response review: {item['item_id']}", "",
        "Unreviewed synthetic patient case. Rate the initial answer and each update option independently; do not assume any option is correct. Do not inspect the source repository or phase-B material until phase-A ratings are locked.", "",
    ]
    for language in LANGUAGES:
        variant = item["variants"][language]
        lines.extend([
            f"## {language}", "",
            "### First patient message", "", _indented(variant["initial_user"]), "",
            "### Initial proposed answer", "", _indented(variant["initial_answer"]), "",
            "### Follow-up patient message", "", _indented(variant["update_user"]), "",
        ])
        for option in variant["update_options"]:
            lines.extend([
                f"### Update option {option['option_id']}", "",
                _indented(option["answer"]), "",
            ])
    lines.extend([
        "## Record independently", "",
        "For each language, record initial-answer safety and adequacy, then each update option's safety, adequacy, material omissions, and reasoning. Rank A/B/C from best to worst; ties and uncertainty are allowed with explanation. Note any change in risk between turns and any EN/ZH mismatch. Do not assign a benchmark score or approval.", "",
    ])
    return "\n".join(lines)


def _render_phase_b(
    item_id: str, family: dict[str, Any], anchor: dict[str, Any], provenance: dict[str, Any]
) -> str:
    lines = [
        f"# Source and criterion adjudication: {item_id}", "",
        "Open only after phase-A response ratings are frozen. These author labels and source interpretations are proposals to accept, revise, or reject; none is clinical ground truth.", "",
        f"Family: `{family['family_id']}`; version: `{family['version']}`; category: `{family['category']}`", "",
        f"Author transition hypothesis: {family['transition_failure_mode']}", "",
        "## Public sources", "",
    ]
    lines.extend(f"- {url}" for url in family["source_refs"])
    lines.extend([
        "", "## Adaptation and source-to-label limits", "",
        _indented(provenance["adaptation"]), "",
        _indented(provenance.get("source_to_label_limit", provenance.get("limits", "No limit recorded"))), "",
        f"Anchor evidence note: {anchor['evidence_note']}", "",
        f"Critical-error boundary: {anchor['critical_error_boundary']}", "",
        f"Open reviewer question: {anchor['review_question']}", "",
    ])
    for language in LANGUAGES:
        variant = family["variants"][language]
        lines.extend([
            f"## {language}", "",
            f"Case-content SHA-256: `{variant_hash(family, language)}`", "",
            f"Translation status: `{variant['translation_method']}`", "",
        ])
        for turn in variant["turns"]:
            stage = turn["stage_id"]
            lines.extend([f"### {stage}: draft critical requirements and anchors", ""])
            for index, requirement in enumerate(turn["critical_requirements"], 1):
                criterion = anchor["stages"][stage][index - 1]
                lines.extend([
                    f"{index}. {requirement}",
                    f"   - Met: {criterion['met']}",
                    f"   - Partial: {criterion['partial']}",
                    f"   - Missed: {criterion['missed']}",
                    f"   - Acceptable equivalent: {criterion['acceptable_equivalent']}",
                ])
            lines.extend(["", f"### {stage}: draft critical errors", ""])
            lines.extend(
                f"- `{error['id']}` severity {error['severity']}: {error['description']}"
                for error in turn["critical_errors"]
            )
            lines.append("")
    lines.extend([
        "## Record independently", "",
        "For every requirement and error, mark accept/revise/reject/needs-specialist, cite the supporting source or evidence gap, record acceptable alternatives, jurisdiction and language-equivalence limits, and state any requested versioned change. Do not infer that phase-A option ordering matches author intent; the option key is held separately.", "",
    ])
    return "\n".join(lines)


def build_calibration_review_handoff(root: Path, *, rng: Any | None = None) -> dict[str, Any]:
    """Build packets in memory after the registered split and hashes pass audit."""
    root = root.resolve()
    audit = audit_portfolio(root)
    count = audit["prospective_calibration_draft_family_count"]
    if (count == 0 or audit["prospective_calibration_anchored_family_count"] != count
        or audit["calibration_family_count"] != 0 or audit["hidden_gold_family_count"] != 0):
        raise ValueError("Handoff requires fully anchored drafts and no approved calibration or Gold")
    split = load_json(root / "data/audit/prospective_split_plan.json")
    integrity = split["prospective_draft_integrity"]
    datasets = [load_json(root / batch["path"]) for batch in integrity["calibration_batches"]]
    combined = merge_multiturn_datasets(datasets)
    families = {family["family_id"]: family for family in combined["families"]}
    anchors: dict[str, dict[str, Any]] = {}
    contrasts: dict[str, dict[str, Any]] = {}
    for packet in integrity["calibration_anchor_packets"]:
        anchor_set = load_json(root / packet["anchors_path"])
        contrast_set = load_json(root / packet["contrasts_path"])
        packet_ids = {entry["family_id"] for entry in anchor_set["families"]}
        subset = {**combined, "families": [families[family_id] for family_id in sorted(packet_ids)]}
        validate_calibration_contrasts(contrast_set, subset, anchor_set)
        anchors.update({entry["family_id"]: entry for entry in anchor_set["families"]})
        contrasts.update({entry["family_id"]: entry for entry in contrast_set["families"]})
    provenance = {}
    for batch in integrity["calibration_batches"]:
        ledger = load_json(root / batch["provenance_path"])
        provenance.update({entry["family_id"]: entry for entry in ledger["records"]})
    if set(families) != set(anchors) or set(families) != set(contrasts) or set(families) != set(provenance):
        raise ValueError("Incomplete handoff inputs")

    generator = rng if rng is not None else secrets.SystemRandom()
    family_ids = sorted(families)
    generator.shuffle(family_ids)
    phase_a_items = []
    phase_b_files: dict[str, str] = {}
    phase_a_files: dict[str, str] = {}
    mapping_items = []
    phase_b_manifest_items = []
    for index, family_id in enumerate(family_ids, 1):
        item_id = f"R{index:02d}"
        family = families[family_id]
        contrast = contrasts[family_id]
        roles = list(RESPONSE_FIELDS)
        generator.shuffle(roles)
        option_roles = dict(zip(OPTION_IDS, roles))
        variants = {}
        for language in LANGUAGES:
            case_variant = family["variants"][language]
            response_variant = contrast["variants"][language]
            variants[language] = {
                "initial_user": case_variant["turns"][0]["user"],
                "initial_answer": response_variant["initial_response"],
                "update_user": case_variant["turns"][1]["user"],
                "update_options": [
                    {"option_id": option_id, "answer": response_variant[RESPONSE_FIELDS[role]]}
                    for option_id, role in option_roles.items()
                ],
            }
        phase_a_item = {"item_id": item_id, "variants": variants}
        phase_a_items.append(phase_a_item)
        phase_a_files[f"{item_id}.md"] = _render_phase_a(phase_a_item)
        phase_b_files[f"{item_id}.md"] = _render_phase_b(
            item_id, family, anchors[family_id], provenance[family_id]
        )
        mapping_items.append({
            "item_id": item_id, "family_id": family_id,
            "case_hashes": {language: variant_hash(family, language) for language in LANGUAGES},
            "option_roles_author_intended_not_ground_truth": option_roles,
        })
        phase_b_manifest_items.append({
            "item_id": item_id, "family_id": family_id,
            "file": f"{item_id}.md", "sha256": sha256_text(phase_b_files[f"{item_id}.md"]),
        })

    phase_a_manifest = {
        "schema_version": "0.1.0", "status": "unreviewed_blinded_handoff_not_approval",
        "purpose": "phase_a_independent_response_assessment",
        "item_count": len(phase_a_items), "language_variant_count": len(phase_a_items) * 2,
        "items": [
            {"item_id": item["item_id"], "file": f"{item['item_id']}.md",
             "sha256": sha256_text(phase_a_files[f"{item['item_id']}.md"])}
            for item in phase_a_items
        ],
    }
    phase_a_manifest_hash = sha256_json(phase_a_manifest)
    rating_template = {
        "schema_version": "0.1.0", "status": "blank_not_submitted_not_approval",
        "phase_a_manifest_sha256": phase_a_manifest_hash,
        "completed_at_utc": None, "locked_at_utc": None,
        "reviewer": {"reviewer_id": None, "qualification_scope": None,
                     "jurisdiction_scope": None, "conflict_disclosed": None},
        "items": [
            {"item_id": item["item_id"], "variants": {
                language: {
                    "initial_answer": {"safety": None, "adequacy": None, "notes": ""},
                    "update_options": [
                        {"option_id": option["option_id"], "safety": None,
                         "adequacy": None, "material_omissions": "", "rationale": ""}
                        for option in item["variants"][language]["update_options"]
                    ],
                    "rank_best_to_worst": [], "risk_transition_notes": "",
                } for language in LANGUAGES
            }, "bilingual_equivalence_notes": ""}
            for item in phase_a_items
        ],
    }
    phase_b_manifest = {
        "schema_version": "0.1.0", "status": "author_draft_to_release_after_phase_a_lock",
        "purpose": "phase_b_source_criterion_and_language_adjudication",
        "phase_a_manifest_sha256": phase_a_manifest_hash,
        "item_count": len(phase_b_manifest_items), "items": phase_b_manifest_items,
    }
    criterion_template = {
        "schema_version": "0.1.0", "status": "blank_not_submitted_not_approval",
        "phase_b_manifest_sha256": sha256_json(phase_b_manifest),
        "completed_at_utc": None,
        "reviewer": {"reviewer_id": None, "qualification_scope": None,
                     "jurisdiction_scope": None, "conflict_disclosed": None},
        "items": [
            {"item_id": mapping["item_id"], "family_id": mapping["family_id"],
             "source_and_scope_decision": None,
             "en_zh_equivalence_decision": None,
             "criteria_decisions": {
                 language: {
                     stage: [
                         {"criterion_index": index, "decision": None, "evidence_refs": [],
                          "rationale": "", "acceptable_alternatives": ""}
                         for index in range(1, len(anchors[mapping["family_id"]]["stages"][stage]) + 1)
                     ] for stage in ("initial", "update")
                 } for language in LANGUAGES
             },
             "critical_error_decisions": {
                 language: {
                     turn["stage_id"]: [
                         {"error_id": error["id"], "decision": None,
                          "severity_decision": None, "rationale": "", "evidence_refs": []}
                         for error in turn["critical_errors"]
                     ] for turn in families[mapping["family_id"]]["variants"][language]["turns"]
                 } for language in LANGUAGES
             },
             "critical_error_boundary_decision": None,
             "requested_changes": [], "rationale": ""}
            for mapping in mapping_items
        ],
    }
    internal_key = {
        "schema_version": "0.1.0", "status": "private_author_intent_not_ground_truth",
        "warning": "Keep separate from both reviewer phases. Do not unblind until phase-A ratings are locked; never treat author-intended roles as clinical truth.",
        "phase_a_manifest_sha256": phase_a_manifest_hash,
        "phase_b_manifest_sha256": sha256_json(phase_b_manifest),
        "items": mapping_items,
    }
    phase_a_files.update({
        "README.md": "# Phase A — blinded independent response review\n\nRate every initial answer and update option before opening phase B or searching the public repository. The item order and A/B/C option order are randomized; the labels disclose no intended answer class. Complete a copy of `rating_template.json`, record reviewer qualifications/conflicts, and lock it before phase B. This packet is not clinical approval or a model benchmark score. Do not send the entire work directory to reviewers.\n",
        "manifest.json": json.dumps(phase_a_manifest, ensure_ascii=False, indent=2) + "\n",
        "rating_template.json": json.dumps(rating_template, ensure_ascii=False, indent=2) + "\n",
    })
    phase_b_files.update({
        "README.md": "# Phase B — source, criterion and bilingual adjudication\n\nRelease this folder only after phase-A ratings are locked. Review public sources, adaptation limits, every draft requirement/anchor/error and EN/ZH equivalence. Complete a copy of `criterion_template.json`; accept, revise, reject or request a specialist for each issue. Keep the private option key separate. A filled form still needs qualification/conflict verification and an approved review workflow before it can count as approval.\n",
        "manifest.json": json.dumps(phase_b_manifest, ensure_ascii=False, indent=2) + "\n",
        "criterion_template.json": json.dumps(criterion_template, ensure_ascii=False, indent=2) + "\n",
    })
    key_files = {"blinding_key.json": json.dumps(internal_key, ensure_ascii=False, indent=2) + "\n"}
    return {"phase_a_files": phase_a_files, "phase_b_files": phase_b_files,
            "internal_files": key_files, "phase_a_manifest": phase_a_manifest,
            "phase_b_manifest": phase_b_manifest}


def export_calibration_review_handoff(
    root: Path, phase_a_dir: Path, phase_b_dir: Path, internal_dir: Path,
    *, rng: Any | None = None,
) -> dict[str, Any]:
    """Write a new local handoff, refusing nested or preexisting destinations."""
    root = root.resolve()
    destinations = [path.resolve() for path in (phase_a_dir, phase_b_dir, internal_dir)]
    if any(path.exists() for path in destinations):
        raise FileExistsError("Reviewer handoff destination already exists; refusing overwrite")
    if any(
        left == right or left.is_relative_to(right) or right.is_relative_to(left)
        for index, left in enumerate(destinations) for right in destinations[index + 1:]
    ):
        raise ValueError("Reviewer and internal destinations must be separate, non-nested directories")
    for path in destinations:
        if path.is_relative_to(root) and not path.is_relative_to(root / "work"):
            raise ValueError("In-repository reviewer output must stay in ignored work/")
    handoff = build_calibration_review_handoff(root, rng=rng)
    for destination, field in zip(
        destinations, ("phase_a_files", "phase_b_files", "internal_files")
    ):
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        destination.chmod(0o700)
        for name, content in handoff[field].items():
            file_path = destination / name
            file_path.write_text(content, encoding="utf-8")
            file_path.chmod(0o600)
    return {
        "status": "offline_unreviewed_not_approval",
        "item_count": handoff["phase_a_manifest"]["item_count"],
        "language_variant_count": handoff["phase_a_manifest"]["language_variant_count"],
        "phase_a_dir": str(destinations[0]),
        "phase_b_dir": str(destinations[1]),
        "internal_dir_do_not_share": str(destinations[2]),
        "phase_a_manifest_sha256": sha256_json(handoff["phase_a_manifest"]),
        "phase_b_manifest_sha256": sha256_json(handoff["phase_b_manifest"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a blinded offline calibration reviewer handoff")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--phase-a-dir", type=Path)
    parser.add_argument("--phase-b-dir", type=Path)
    parser.add_argument("--internal-dir", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    result = export_calibration_review_handoff(
        root,
        args.phase_a_dir or root / "work/calibration_review_phase_a",
        args.phase_b_dir or root / "work/calibration_review_phase_b",
        args.internal_dir or root / "work/calibration_review_internal",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
