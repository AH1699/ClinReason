"""Offline S30 draft packets: two clarified criteria, no provider calls or scores."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn_diagnostics import contrast_packet
from .provenance import sha256_json


FAMILY = "HC-MT-TRIAGE-020"
ANCHORS = "config/multiturn_criterion_anchors_batch_g_s30_draft_v1.json"
FIXTURES = "data/multiturn/s30_sinus_boundary_draft_v1.json"
PROFILES = {"complete", "observed_partial", "unlinked_generic", "contradictory", "ambiguous_reference"}


def build_packets(dataset, old_anchors, anchors, probes, fixtures):
    validate_anchor_set(old_anchors, dataset)
    validate_anchor_set(anchors, dataset)
    # Reverting only these declared edits must reproduce the historical anchors.
    old = next(f for f in old_anchors["families"] if f["family_id"] == FAMILY)
    restored = deepcopy(anchors)
    new = next(f for f in restored["families"] if f["family_id"] == FAMILY)
    for index in (0, 2):
        if new["stages"]["update"][index] == old["stages"]["update"][index]:
            raise ValueError("Missing declared boundary edit")
        new["stages"]["update"][index] = deepcopy(old["stages"]["update"][index])
    new["review_question"] = old["review_question"]
    restored["scope"] = old_anchors["scope"]
    if restored != old_anchors:
        raise ValueError("Undeclared historical anchor change")
    if (fixtures["schema_version"] != "0.1.0"
            or fixtures["status"] != "offline_author_draft_not_live_approved_not_clinically_validated"
            or fixtures["family_id"] != FAMILY or fixtures["stage_id"] != "update"
            or fixtures["requirement_indexes"] != [1, 3]
            or fixtures["repeat_profiles"] != ["observed_partial"]
            or fixtures["prospective_call_count"] != 24
            or len(fixtures["fixtures"]) != 5
            or {f["profile"] for f in fixtures["fixtures"]} != PROFILES):
        raise ValueError("Unexpected S30 draft scope")
    family = next(f for f in dataset["families"] if f["family_id"] == FAMILY)
    paired = {p["language"]: p for p in probes if p["family_id"] == FAMILY}
    packets, expected, repeats = {}, {}, set()
    for item in fixtures["fixtures"]:
        hypothesis = item["expected_statuses"]
        if (set(item["update_responses"]) != {"en", "zh-Hans"}
                or (item["profile"] == "ambiguous_reference" and hypothesis is not None)
                or (item["profile"] != "ambiguous_reference" and (
                    not isinstance(hypothesis, list) or len(hypothesis) != 2
                    or any(s not in ("met", "partial", "missed") for s in hypothesis)))):
            raise ValueError("Invalid paired draft hypothesis")
        for language in ("en", "zh-Hans"):
            text = item["update_responses"][language]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Missing response text")
            kind = {"complete": "safe", "observed_partial": "partial"}.get(item["profile"])
            if kind and text != paired[language][f"{kind}_update_response"]:
                raise ValueError("Historical control answer changed")
            full = attach_anchors(contrast_packet(family, paired[language], "safe"), anchors)
            full["transcript"][3]["content"] = text
            # Only this allowlist reaches a future judge. Author expectations,
            # profile names, old judge outcomes and numeric aspirations do not.
            packet = {k: full[k] for k in ("case_id", "case_content_hash", "language", "transcript")}
            packet["target_requirements"] = [a for a in full["criterion_anchors"]
                if a["stage_id"] == "update" and a["requirement_index"] in (1, 3)]
            packet["level_definitions"] = deepcopy(anchors["levels"])
            key = f"{item['profile']}__{language}"
            packets[key], expected[key] = packet, deepcopy(hypothesis)
            if item["profile"] in fixtures["repeat_profiles"]:
                repeats.add(key)
    return packets, expected, repeats


def inputs(root):
    return (load_json(root / "data/multiturn/batch_g_cases.json"),
            load_json(root / "config/multiturn_criterion_anchors_batch_g_s27_v1.json"),
            load_json(root / ANCHORS),
            load_json(root / "data/multiturn/batch_g_contrasts_v1.json")["probes"],
            load_json(root / FIXTURES))


def audit(root):
    packets, expected, repeats = build_packets(*inputs(root))
    return {"status": "offline_draft_not_live_approved_not_clinical_validation",
            "packet_count": len(packets), "criteria_per_packet": 2,
            "author_hypothesis_packets": sum(v is not None for v in expected.values()),
            "exploratory_packets": sum(v is None for v in expected.values()),
            "prospective_first_calls": 2 * len(packets),
            "prospective_repeat_calls": 2 * len(repeats),
            "candidate_calls": 0, "judge_calls": 0, "live_runner_implemented": False,
            "packet_hashes": {k: sha256_json(v) for k, v in sorted(packets.items())},
            "limits": "Structural/blinding checks only. No numerical scoring, default adoption, clinical approval or permission to send packets."}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), indent=2))
