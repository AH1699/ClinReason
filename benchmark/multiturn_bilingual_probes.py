"""Case-bound bilingual near-miss probes; hypotheses remain hidden from AI judges."""

from __future__ import annotations

from typing import Any

from .multiturn import build_judge_packet, validate_multiturn_dataset, variant_hash, variant_id
from .multiturn_judging import score_judgment
from .provenance import sha256_json


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


def compare_bilingual_probe_reports(
    dataset: dict[str, Any], probes: dict[str, Any], first: dict[str, Any],
    second_parts: list[dict[str, Any]], rubric: dict[str, Any],
    instruction_sha256: str,
) -> dict[str, Any]:
    """Compare complete, independently scored probe sets after replaying their scores."""
    pairs = validate_probe_set(dataset, probes)
    families = {family["family_id"]: family for family in dataset["families"]}
    expected_keys = {(pair["family_id"], pair["language"]) for pair in pairs}
    expected_rubric = sha256_json(rubric)

    def checked_rows(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
        rows = report.get("results")
        if (report.get("status") != "provisional_synthetic_judge_consistency_not_clinical_validation"
            or not isinstance(rows, list) or not rows
            or report.get("rubric_sha256") != expected_rubric
            or report.get("judge_instruction_sha256") != instruction_sha256
            or report.get("actual_request_parameters") != {"store": False, "response_format": "json_schema"}
            or not isinstance(report.get("judge_model_returned"), str)
            or not report["judge_model_returned"].strip()):
            raise ValueError("Bilingual probe report has incompatible provenance")
        mapped = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Malformed bilingual probe result")
            key = (row.get("family_id"), row.get("language"))
            if key not in expected_keys or key in mapped:
                raise ValueError("Unknown or duplicate bilingual probe result")
            pair = next(pair for pair in pairs if (pair["family_id"], pair["language"]) == key)
            if (row.get("case_id") != variant_id(families[key[0]], key[1])
                or row.get("case_content_hash") != pair["case_content_hash"]):
                raise ValueError("Bilingual probe result is bound to a different case")
            outcomes = row.get("outcomes")
            if not isinstance(outcomes, dict) or set(outcomes) != {"baseline", "challenge"}:
                raise ValueError("Bilingual probe result lacks both arms")
            for arm in ("baseline", "challenge"):
                packet = probe_packet(families[key[0]], pair, arm)
                if score_judgment(outcomes[arm]["judgment"], packet, rubric) != outcomes[arm]["score"]:
                    raise ValueError("Stored bilingual probe score does not recompute")
            baseline = outcomes["baseline"]
            challenge = outcomes["challenge"]
            if (row.get("score_gap_baseline_minus_challenge") != round(
                    baseline["score"]["gated_score"] - challenge["score"]["gated_score"], 2)
                or row.get("initial_requirements_gap") != (
                    baseline["judgment"]["stage_scores"][0]["requirements"]
                    - challenge["judgment"]["stage_scores"][0]["requirements"])
                or row.get("initial_safety_gap") != (
                    baseline["judgment"]["stage_scores"][0]["safety"]
                    - challenge["judgment"]["stage_scores"][0]["safety"])):
                raise ValueError("Stored bilingual probe contrast does not recompute")
            mapped[key] = row
        selected = {**probes, "pairs": [
            pair for pair in pairs if (pair["family_id"], pair["language"]) in mapped
        ]}
        validate_probe_set(dataset, selected)
        if report.get("probe_set_sha256") != sha256_json(selected):
            raise ValueError("Bilingual probe fixture hash does not match report selection")
        return mapped

    first_rows = checked_rows(first)
    if set(first_rows) != expected_keys or not second_parts:
        raise ValueError("First report must cover every probe; second reports must be nonempty")
    second_rows: dict[tuple[str, str], dict[str, Any]] = {}
    second_identity = None
    for report in second_parts:
        identity = (report.get("judge_provider"), report.get("judge_model_id"),
                    report.get("judge_model_returned"))
        if second_identity is not None and identity != second_identity:
            raise ValueError("Second-provider reports have mixed judge identities")
        second_identity = identity
        rows = checked_rows(report)
        if set(rows) & set(second_rows):
            raise ValueError("Second-provider reports overlap")
        second_rows.update(rows)
    if set(second_rows) != expected_keys or first.get("judge_provider") == second_identity[0]:
        raise ValueError("Comparison needs complete probes from distinct providers")

    comparisons = []
    for pair in pairs:
        key = (pair["family_id"], pair["language"])
        left, right = first_rows[key], second_rows[key]
        left_challenge = left["outcomes"]["challenge"]["judgment"]
        right_challenge = right["outcomes"]["challenge"]["judgment"]
        comparisons.append({
            "family_id": key[0], "language": key[1],
            "case_id": left["case_id"], "case_content_hash": pair["case_content_hash"],
            "first_gap": left["score_gap_baseline_minus_challenge"],
            "second_gap": right["score_gap_baseline_minus_challenge"],
            "gap_difference_second_minus_first": round(
                right["score_gap_baseline_minus_challenge"]
                - left["score_gap_baseline_minus_challenge"], 2),
            "same_positive_direction": (
                left["score_gap_baseline_minus_challenge"] > 0
                and right["score_gap_baseline_minus_challenge"] > 0),
            "exact_gap_agreement": (
                left["score_gap_baseline_minus_challenge"]
                == right["score_gap_baseline_minus_challenge"]),
            "first_challenge_review_requested": left_challenge["requires_human_review"],
            "second_challenge_review_requested": right_challenge["requires_human_review"],
            "first_challenge_initial_scores": left_challenge["stage_scores"][0],
            "second_challenge_initial_scores": right_challenge["stage_scores"][0],
            "first_challenge_revision_score": left_challenge["revision_score"],
            "second_challenge_revision_score": right_challenge["revision_score"],
        })
    return {
        "status": "provisional_cross_provider_probe_comparison_not_clinical_validation",
        "probe_set_sha256": sha256_json(probes),
        "judge_instruction_sha256": instruction_sha256,
        "rubric_sha256": expected_rubric,
        "first_judge": {"provider": first["judge_provider"],
                        "model_id": first["judge_model_id"],
                        "returned_model": first["judge_model_returned"]},
        "second_judge": {"provider": second_identity[0], "model_id": second_identity[1],
                         "returned_model": second_identity[2]},
        "pair_count": len(comparisons),
        "same_positive_direction_count": sum(item["same_positive_direction"] for item in comparisons),
        "exact_gap_agreement_count": sum(item["exact_gap_agreement"] for item in comparisons),
        "challenge_review_flag_agreement_count": sum(
            item["first_challenge_review_requested"] == item["second_challenge_review_requested"]
            for item in comparisons),
        "results": comparisons,
    }
