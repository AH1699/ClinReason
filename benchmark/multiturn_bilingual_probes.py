"""Case-bound bilingual near-miss probes; hypotheses remain hidden from AI judges."""

from __future__ import annotations

from typing import Any

from .multiturn import build_judge_packet, validate_multiturn_dataset, variant_hash, variant_id
from .multiturn_judging import score_judgment


def validate_probe_set(dataset: dict[str, Any], probes: dict[str, Any]) -> list[dict[str, Any]]:
    validate_multiturn_dataset(dataset)
    families = {family["family_id"]: family for family in dataset["families"]}
    pairs = probes.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Bilingual probe set must contain nonempty pairs")
    seen: set[tuple[str, str]] = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("Malformed bilingual probe pair")
        family_id, language = pair.get("family_id"), pair.get("language")
        if family_id not in families or language not in ("en", "zh-Hans"):
            raise ValueError("Bilingual probe refers to unknown family or language")
        key = (family_id, language)
        if key in seen:
            raise ValueError("Duplicate bilingual probe pair")
        seen.add(key)
        if pair.get("case_content_hash") != variant_hash(families[family_id], language):
            raise ValueError(f"Bilingual probe has stale case revision: {family_id}/{language}")
        if any(not isinstance(pair.get(name), str) or not pair[name].strip()
               for name in ("baseline_initial", "challenge_initial", "update_response", "hypothesis")):
            raise ValueError("Bilingual probe response or hypothesis is missing")
        if pair["baseline_initial"] == pair["challenge_initial"]:
            raise ValueError("Bilingual probe arms must differ")
    if {language for _, language in seen} != {"en", "zh-Hans"} or any(
        (family_id, "en") not in seen or (family_id, "zh-Hans") not in seen
        for family_id, _ in seen
    ):
        raise ValueError("Bilingual probes must have both languages for every family")
    return pairs


def probe_packet(family: dict[str, Any], pair: dict[str, Any], arm: str) -> dict[str, Any]:
    if arm not in ("baseline", "challenge"):
        raise ValueError("Unknown bilingual probe arm")
    language = pair["language"]
    turns = family["variants"][language]["turns"]
    responses = [pair[f"{arm}_initial"], pair["update_response"]]
    transcript = [
        item for turn, answer in zip(turns, responses)
        for item in ({"role": "user", "content": turn["user"]},
                     {"role": "assistant", "content": answer})
    ]
    response = {
        "case_id": variant_id(family, language), "case_version": family["version"],
        "case_content_hash": pair["case_content_hash"], "transcript": transcript,
        "turn_outputs": [
            {"stage_id": turn["stage_id"], "text": answer}
            for turn, answer in zip(turns, responses)
        ],
    }
    return build_judge_packet(family, language, response)


def run_bilingual_probes(
    dataset: dict[str, Any], probes: dict[str, Any], judge: Any, rubric: dict[str, Any],
) -> dict[str, Any]:
    pairs = validate_probe_set(dataset, probes)
    families = {family["family_id"]: family for family in dataset["families"]}
    rows = []
    # Counterbalance order within pairs; each judge call receives only one arm.
    for index, pair in enumerate(pairs):
        outcomes = {}
        arms = ("baseline", "challenge") if index % 2 == 0 else ("challenge", "baseline")
        for arm in arms:
            packet = probe_packet(families[pair["family_id"]], pair, arm)
            judgment = judge.evaluate(packet)
            score = score_judgment(judgment, packet, rubric)
            outcomes[arm] = {"judgment": judgment, "score": score}
        baseline = outcomes["baseline"]["score"]
        challenge = outcomes["challenge"]["score"]
        rows.append({
            "family_id": pair["family_id"], "language": pair["language"],
            "case_id": baseline["case_id"], "case_content_hash": pair["case_content_hash"],
            "score_gap_baseline_minus_challenge": round(
                baseline["gated_score"] - challenge["gated_score"], 2),
            "initial_requirements_gap": (
                outcomes["baseline"]["judgment"]["stage_scores"][0]["requirements"]
                - outcomes["challenge"]["judgment"]["stage_scores"][0]["requirements"]),
            "initial_safety_gap": (
                outcomes["baseline"]["judgment"]["stage_scores"][0]["safety"]
                - outcomes["challenge"]["judgment"]["stage_scores"][0]["safety"]),
            "outcomes": outcomes,
        })
    by_family: dict[str, dict[str, float]] = {}
    for row in rows:
        by_family.setdefault(row["family_id"], {})[row["language"]] = row[
            "score_gap_baseline_minus_challenge"]
    return {
        "status": "provisional_synthetic_judge_consistency_not_clinical_validation",
        "judge_provider": judge.provider_name, "judge_model_id": judge.model_id,
        "judge_model_returned": judge.model_version,
        "probe_count": len(rows) * 2, "pair_count": len(rows),
        "positive_gap_count": sum(row["score_gap_baseline_minus_challenge"] > 0 for row in rows),
        "family_language_gaps": by_family,
        "results": rows,
    }
