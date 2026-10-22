"""Freeze one-edit S13 scoring-coherence probes offline; no provider calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn import build_judge_packet, merge_multiturn_datasets, variant_hash, variant_id
from .provenance import sha256_json, sha256_text


VARIANTS = ("baseline", "plan_omission", "safety_net_omission", "revision_failure")
EXPECTED_HYPOTHESES = {
    "baseline": ["met", "met", "met"],
    "plan_omission": ["met", "partial", "met"],
    "safety_net_omission": ["met", "met", "partial"],
    "revision_failure": ["partial", "met", "met"],
}


def render_update(item: dict[str, Any], variant: str) -> str:
    if variant not in VARIANTS:
        raise ValueError("Unknown scoring-probe variant")
    segments = item["base_update_segments"].copy()
    if variant == "plan_omission":
        del segments[2]
    elif variant == "safety_net_omission":
        del segments[3]
    elif variant == "revision_failure":
        segments[0] = item["revision_replacement"]
    return item["separator"].join(segments)


def build_probe_packet(
    family: dict[str, Any], item: dict[str, Any], variant: str,
    anchors: dict[str, Any],
) -> dict[str, Any]:
    """Build the exact judge packet shared by preregistration and later runs."""
    language = item["language"]
    response = render_update(item, variant)
    transcript = []
    for turn, answer in zip(family["variants"][language]["turns"],
                            (item["initial_response"], response)):
        transcript.extend([{"role": "user", "content": turn["user"]},
                           {"role": "assistant", "content": answer}])
    candidate_response = {
        "case_id": variant_id(family, language), "case_version": family["version"],
        "case_content_hash": item["case_content_hash"], "transcript": transcript,
        "turn_outputs": [{"stage_id": "initial", "text": item["initial_response"]},
                         {"stage_id": "update", "text": response}],
    }
    return attach_anchors(build_judge_packet(family, language, candidate_response), anchors)


def validate_prereg(
    prereg: dict[str, Any], dataset: dict[str, Any], anchors: dict[str, Any],
    rubric: dict[str, Any], roster: dict[str, Any], judge_instruction: str,
    base_contrasts: dict[str, Any],
) -> dict[str, Any]:
    """Return a reproducible packet manifest, not clinical judgments or scores."""
    validate_anchor_set(anchors, dataset)
    if (not isinstance(prereg, dict)
        or set(prereg) != {"schema_version", "status", "family_id", "criterion_anchors_sha256",
                           "rubric_sha256", "judge_instruction_sha256", "roster_sha256",
                           "base_contrasts_sha256",
                           "planned_candidate_calls", "planned_judge_calls", "variant_order",
                           "author_hypotheses_not_gold", "languages"}
        or prereg["schema_version"] != "0.1.0"
        or prereg["status"] != "synthetic_unreviewed_scoring_probe_prereg_not_clinical_truth"
        or prereg["family_id"] != "HC-MT-TRIAGE-020"
        or prereg["criterion_anchors_sha256"] != sha256_json(anchors)
        or prereg["rubric_sha256"] != sha256_json(rubric)
        or prereg["roster_sha256"] != sha256_json(roster)
        or prereg["base_contrasts_sha256"] != sha256_json(base_contrasts)
        or prereg["judge_instruction_sha256"] != sha256_text(judge_instruction)
        or prereg["planned_candidate_calls"] != 0
        or prereg["planned_judge_calls"] != 16
        or prereg["variant_order"] != list(VARIANTS)
        or prereg["author_hypotheses_not_gold"] != EXPECTED_HYPOTHESES
        or len(roster.get("judges", [])) != 2
        or {judge["provider"] for judge in roster["judges"]} != {"gemini", "grok"}
        or not isinstance(prereg["languages"], list) or len(prereg["languages"]) != 2):
        raise ValueError("S13 scoring probe has changed its frozen protocol")
    family = next((family for family in dataset["families"]
                   if family["family_id"] == prereg["family_id"]), None)
    if family is None:
        raise ValueError("S13 family is absent from configured dataset")
    base = {(probe["family_id"], probe["language"]): probe
            for probe in base_contrasts["probes"]}
    expected_languages = {"en", "zh-Hans"}
    if {item.get("language") for item in prereg["languages"] if isinstance(item, dict)} != expected_languages:
        raise ValueError("S13 requires one exact EN and one exact ZH probe")
    packets = []
    for item in prereg["languages"]:
        language = item["language"]
        if (set(item) != {"language", "case_content_hash", "initial_response", "separator",
                         "base_update_segments", "revision_replacement"}
            or item["case_content_hash"] != variant_hash(family, language)
            or item["initial_response"] != base[(prereg["family_id"], language)]["initial_response"]
            or item["separator"] != (" " if language == "en" else "")
            or not isinstance(item["base_update_segments"], list)
            or len(item["base_update_segments"]) != 4
            or any(not isinstance(text, str) or not text.strip()
                   for text in [*item["base_update_segments"], item["revision_replacement"]])
            or item["base_update_segments"][0] == item["revision_replacement"]):
            raise ValueError("S13 probe answer is malformed or no longer case-bound")
        rendered = [render_update(item, variant) for variant in VARIANTS]
        if len(set(rendered)) != 4:
            raise ValueError("S13 variants must have distinct update answers")
        if language == "zh-Hans" and any(sum('\u3400' <= char <= '\u9fff' for char in text) < 12
                                          for text in [item["initial_response"], *rendered]):
            raise ValueError("S13 Chinese-script sanity check failed")
        if language == "en" and any(sum('\u3400' <= char <= '\u9fff' for char in text) >= 3
                                     for text in [item["initial_response"], *rendered]):
            raise ValueError("S13 English-script sanity check failed")
        for variant, response in zip(VARIANTS, rendered):
            packet = build_probe_packet(family, item, variant, anchors)
            packets.append({"case_id": packet["case_id"], "variant": variant,
                            "packet_sha256": sha256_json(packet),
                            "update_response_sha256": sha256_text(response)})
    return {
        "status": "frozen_synthetic_prereg_no_model_calls_or_scores",
        "prereg_sha256": sha256_json(prereg), "family_id": prereg["family_id"],
        "case_count": 2, "answer_variant_count": len(packets),
        "planned_candidate_calls": 0, "planned_judge_calls": 16,
        "packet_hashes": packets,
        "limits": "Author hypotheses are not clinical or bilingual truth. No dimension score or pass result is asserted.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate S13 one-edit scoring probes offline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    root = args.root
    config = load_json(root / "config/benchmark.json")
    dataset = merge_multiturn_datasets([load_json(root / path) for path in config["multiturn_cases_paths"]])
    result = validate_prereg(
        load_json(root / "data/multiturn/scoring_coherence_probes_s13_v1.json"), dataset,
        load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json"),
        load_json(root / "config/multiturn_rubric.json"),
        load_json(root / "config/model_matrix.json"),
        (root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip(),
        load_json(root / "data/multiturn/batch_g_contrasts_v1.json"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
