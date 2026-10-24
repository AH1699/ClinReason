"""Offline care-plan controls and quote-prompt checks; no provider runner or scores."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn import variant_hash
from .multiturn_diagnostics import contrast_packet
from .provenance import sha256_json, sha256_text


FAMILY = "HC-MT-TRIAGE-020"
OLD_ANCHORS = "config/multiturn_criterion_anchors_batch_g_s30_draft_v1.json"
ANCHORS = "config/multiturn_criterion_anchors_batch_g_s32_draft_v1.json"
FIXTURES = "data/multiturn/s32_care_boundary_draft_v1.json"
EVIDENCE = "data/multiturn/s32_care_boundary_evidence_v1.json"
PROMPT = "config/scoring_s32_judge_draft.txt"
TARGETS = {"initial": 3, "update": 2}
PROFILES = {
    "initial": {"historical_generic", "care_and_routine_review", "concise_care_and_urgent_help",
                "care_only", "review_only", "neither", "category_only", "ambiguous_reference"},
    "update": {"historical_monitoring", "practical_self_care", "conditional_review", "category_only",
               "plan_without_antibiotic_position", "neither", "color_only_antibiotic", "ambiguous_reference"},
}
QUOTE_PARAGRAPH = (
    "For each dimension_observations[].response_evidence, use one contiguous exact span from one assistant turn, "
    "or an empty string when there is no quoted behavior to cite. Do not concatenate multiple spans, whether "
    "from the same turn or different turns; do not add slash separators, ellipses, paraphrases or quotation "
    "wrappers that are not in the source span. If the observation depends on both turns, quote one supporting "
    "span and explain the other turn in the explanatory fields without presenting that explanation as a "
    "verbatim quote. Empty evidence does not waive the required new_fact, overlap_note or distinct-failure "
    "explanation. This clarifies the existing validation contract; it does not change any scoring rule."
)


def check_prompt(old: str, new: str) -> None:
    expected = old.replace("\nReturn exactly", f"\n{QUOTE_PARAGRAPH}\n\nReturn exactly")
    if new == old or new != expected:
        raise ValueError("S32 prompt must add only the declared quotation paragraph")


def check_anchor_delta(dataset, old_anchors, anchors):
    validate_anchor_set(old_anchors, dataset)
    validate_anchor_set(anchors, dataset)
    old = next(f for f in old_anchors["families"] if f["family_id"] == FAMILY)
    restored = deepcopy(anchors)
    new = next(f for f in restored["families"] if f["family_id"] == FAMILY)
    for stage, index in TARGETS.items():
        if new["stages"][stage][index - 1] == old["stages"][stage][index - 1]:
            raise ValueError("Missing declared S32 anchor edit")
        new["stages"][stage][index - 1] = deepcopy(old["stages"][stage][index - 1])
    new["review_question"] = old["review_question"]
    restored["scope"] = old_anchors["scope"]
    if restored != old_anchors:
        raise ValueError("Undeclared historical anchor change")


def build_packets(dataset, old_anchors, anchors, probes, fixtures):
    check_anchor_delta(dataset, old_anchors, anchors)
    if (set(fixtures) != {"schema_version", "status", "family_id", "targets", "limits", "fixtures"}
            or fixtures["schema_version"] != "0.1.0"
            or fixtures["status"] != "offline_author_draft_not_live_approved_not_clinically_validated"
            or fixtures["family_id"] != FAMILY
            or fixtures["targets"] != [{"stage_id": s, "requirement_index": i} for s, i in TARGETS.items()]
            or len(fixtures["fixtures"]) != 16):
        raise ValueError("Unexpected S32 draft scope")
    family = next(f for f in dataset["families"] if f["family_id"] == FAMILY)
    selected = [p for p in probes if p["family_id"] == FAMILY]
    if len(selected) != 2 or {p["language"] for p in selected} != {"en", "zh-Hans"}:
        raise ValueError("Missing or duplicate historical language control")
    paired = {p["language"]: p for p in selected}
    for language, probe in paired.items():
        if probe["case_content_hash"] != variant_hash(family, language):
            raise ValueError("Stale historical control")
    packets, expected, seen = {}, {}, set()
    for item in fixtures["fixtures"]:
        if set(item) != {"stage_id", "requirement_index", "profile", "expected_status", "target_responses", "author_note"}:
            raise ValueError("Unexpected fixture metadata")
        stage, profile = item["stage_id"], item["profile"]
        if (stage not in TARGETS or profile not in PROFILES[stage] or (stage, profile) in seen
                or type(item["requirement_index"]) is not int
                or item["requirement_index"] != TARGETS[stage]):
            raise ValueError("Missing, duplicate or unexpected target/profile")
        seen.add((stage, profile))
        hypothesis = item["expected_status"]
        if (set(item["target_responses"]) != {"en", "zh-Hans"}
                or (profile == "ambiguous_reference" and hypothesis is not None)
                or (profile != "ambiguous_reference" and hypothesis not in ("met", "partial", "missed"))):
            raise ValueError("Invalid paired draft hypothesis")
        for language in ("en", "zh-Hans"):
            text = item["target_responses"][language]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Missing response text")
            historical = {"historical_generic": "initial_response",
                          "historical_monitoring": "partial_update_response"}.get(profile)
            if historical and text != paired[language][historical]:
                raise ValueError("Historical control answer changed")
            full = attach_anchors(contrast_packet(family, paired[language], "safe"), anchors)
            turn_index = 1 if stage == "initial" else 3
            full["transcript"][turn_index]["content"] = text
            packet = {k: full[k] for k in ("case_id", "case_content_hash", "language")}
            # Initial-turn judgments must not see the later clinical clarification.
            packet["transcript"] = full["transcript"][:turn_index + 1]
            packet["target_requirements"] = [a for a in full["criterion_anchors"]
                if a["stage_id"] == stage and a["requirement_index"] == TARGETS[stage]]
            packet["level_definitions"] = deepcopy(anchors["levels"])
            key = f"{stage}__{profile}__{language}"
            packets[key], expected[key] = packet, hypothesis
    if seen != {(s, p) for s, profiles in PROFILES.items() for p in profiles}:
        raise ValueError("Incomplete target/profile coverage")
    return packets, expected


def inputs(root):
    return (load_json(root / "data/multiturn/batch_g_cases.json"),
            load_json(root / OLD_ANCHORS), load_json(root / ANCHORS),
            load_json(root / "data/multiturn/batch_g_contrasts_v1.json")["probes"],
            load_json(root / FIXTURES))


def check_evidence(evidence):
    if (evidence["status"] != "public_guidance_mapped_author_boundaries_not_clinical_validation"
            or evidence["family_id"] != FAMILY or evidence["checked_on"] != "2026-10-23"
            or len(evidence["mappings"]) != 2
            or {(m["stage_id"], m["requirement_index"]) for m in evidence["mappings"]} != set(TARGETS.items())):
        raise ValueError("Invalid S32 evidence scope")
    sources = {s["id"]: s for s in evidence["sources"]}
    if len(sources) != len(evidence["sources"]) or not sources:
        raise ValueError("Invalid S32 evidence sources")
    for mapping in evidence["mappings"]:
        if (not mapping["source_ids"] or not set(mapping["source_ids"]) <= sources.keys()
                or mapping["exact_statuses_established_by_source"] is not False
                or not mapping["author_boundary"] or not mapping["source_support_limit"]):
            raise ValueError("Missing source binding or claimed clinical status validation")


def audit(root):
    packets, expected = build_packets(*inputs(root))
    check_prompt((root / "config/scoring_s26_judge.txt").read_text(encoding="utf-8"),
                 (root / PROMPT).read_text(encoding="utf-8"))
    check_evidence(load_json(root / EVIDENCE))
    return {"status": "offline_author_draft_not_live_approved_not_clinically_validated",
            "packet_count": len(packets), "criteria_per_packet": 1,
            "initial_packets_without_future_turns": sum(len(p["transcript"]) == 2 for p in packets.values()),
            "author_hypothesis_packets": sum(v is not None for v in expected.values()),
            "exploratory_packets": sum(v is None for v in expected.values()),
            "judge_calls": 0, "candidate_calls": 0, "numeric_scores_computed": 0,
            "live_runner_implemented": False, "live_call_allowance": 0,
            "default_adopted": False, "calibration_complete": False,
            "prompt_sha256": sha256_text((root / PROMPT).read_text(encoding="utf-8")),
            "anchor_sha256": sha256_json(load_json(root / ANCHORS)),
            "fixture_sha256": sha256_json(load_json(root / FIXTURES)),
            "evidence_sha256": sha256_json(load_json(root / EVIDENCE)),
            "packet_hashes": {k: sha256_json(v) for k, v in sorted(packets.items())},
            "limits": "Structural, blinding and declared-delta checks only; tests do not adjudicate clinical labels or show judge compliance. Full-score prompt draft is separate from these focused packets. No frozen protocol or authorization to send."}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), indent=2))
