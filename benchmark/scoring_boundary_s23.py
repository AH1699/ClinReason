"""Offline, non-enforced criterion/dimension/threshold boundary review."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from . import judge_evidence_panel_s21 as s21
from . import judge_evidence_panel_s22_abort_audit as s22_abort
from . import paired_judge_evidence_s20 as s20
from .config import load_json
from .criterion_anchors import attach_anchors
from .multiturn import variant_id
from .multiturn_diagnostics import contrast_packet
from .multiturn_judging import score_judgment
from .provenance import sha256_json
from .providers.http_json import ProviderRequestError


POLICY_PATH = "config/scoring_boundary_s23_v1.json"
RATING_FIELDS = (("initial_requirements", 0, "requirements"),
                 ("initial_safety", 0, "safety"),
                 ("update_requirements", 1, "requirements"),
                 ("update_safety", 1, "safety"))


def point_impacts(rubric: dict[str, Any]) -> dict[str, float]:
    """Raw-score value of one 0–4 rating point, before critical-error caps."""
    maximum = rubric["scale_max"]
    conversation = rubric["conversation_weights"]
    components = rubric["stage_component_weights"]
    if maximum != 4 or sum(conversation.values()) != 1 or sum(components.values()) != 1:
        raise ValueError("S23 expects the frozen draft 0–4 rubric")
    return {f"{stage}_{component}": round(100 * conversation[stage] * components[component] / maximum, 2)
            for stage in ("initial", "update") for component in ("requirements", "safety")} | {
                "revision": round(100 * conversation["revision"] / maximum, 2)}


def _ratings(judgment: dict[str, Any]) -> dict[str, int]:
    return {name: judgment["stage_scores"][index][field] for name, index, field in RATING_FIELDS} | {
        "revision": judgment["revision_score"]}


def _one_point_sensitivity(judgment: dict[str, Any], packet: dict[str, Any],
                           rubric: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = score_judgment(judgment, packet, rubric)
    rows = []
    for name in (*[item[0] for item in RATING_FIELDS], "revision"):
        original = _ratings(judgment)[name]
        for delta in (-1, 1):
            if not 0 <= original + delta <= rubric["scale_max"]:
                continue
            hypothetical = deepcopy(judgment)
            if name == "revision":
                hypothetical["revision_score"] = original + delta
            else:
                _, index, field = next(item for item in RATING_FIELDS if item[0] == name)
                hypothetical["stage_scores"][index][field] = original + delta
            try:
                scored = score_judgment(hypothetical, packet, rubric)
            except ProviderRequestError:
                # Criterion-v2 forbids some isolated changes (for example full
                # requirements credit with an unmet criterion). Record that bound.
                rows.append({"rating": name, "change": delta, "allowed_by_validator": False})
                continue
            rows.append({"rating": name, "change": delta, "allowed_by_validator": True,
                         "hypothetical_score": scored["gated_score"],
                         "hypothetical_pass": scored["pass"],
                         "pass_flip": scored["pass"] != baseline["pass"]})
    return rows


def _s22_partial_rows(root: Path, outer: Path, verified: dict[str, Any],
                      inputs: dict[str, Any]) -> list[dict[str, Any]]:
    saved = {(row["case_id"], row["provider"], row["answer_type"]): row
             for row in verified["rows"]}
    result = []
    for key in sorted(inputs["probes"]):
        family, probe = inputs["families"][key[0]], inputs["probes"][key]
        packet = attach_anchors(contrast_packet(family, probe, "partial"), inputs["anchors"])
        case_id = variant_id(family, key[1])
        for provider in ("gemini", "grok"):
            raw = load_json(outer / "first" / s21._stem(*key) / f"{provider}-judge__partial.judgment.json")
            judgment = raw["judgment"]
            score = score_judgment(judgment, packet, inputs["rubric"])
            if saved[(case_id, provider, "partial")]["score"] != score["gated_score"]:
                raise ValueError("S23 partial score differs from audited S22 saved cell")
            statuses = {stage: [item["status"] for item in judgment["criterion_assessments"]
                                if item["stage_id"] == stage] for stage in ("initial", "update")}
            contributions = {"initial": round(score["stage_scores"]["initial"] *
                                               inputs["rubric"]["conversation_weights"]["initial"], 2),
                             "update": round(score["stage_scores"]["update"] *
                                              inputs["rubric"]["conversation_weights"]["update"], 2),
                             "revision": round(score["revision_score"] *
                                                inputs["rubric"]["conversation_weights"]["revision"], 2)}
            result.append({"case_id": case_id, "family_id": key[0], "language": key[1],
                           "provider": provider, "answer_type": "partial",
                           "exact_initial_response": probe["initial_response"],
                           "exact_update_response": probe["partial_update_response"],
                           "packet_sha256": sha256_json(packet),
                           "criterion_statuses": statuses, "ratings": _ratings(judgment),
                           "critical_error_ids": [item["error_id"] for item in judgment["critical_errors"]],
                           "contributions": contributions, "score": score["gated_score"],
                           "pass": score["pass"],
                           "one_point_counterfactuals": _one_point_sensitivity(judgment, packet, inputs["rubric"]),
                           "requires_human_review": judgment["requires_human_review"]})
    return result


def _coherence_flags(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags = []
    # Same language, same criterion/error findings, different numeric dimension.
    for case_id in sorted({row["case_id"] for row in rows}):
        pair = [row for row in rows if row["case_id"] == case_id]
        if len(pair) != 2:
            raise ValueError("S23 expects one Gemini/Grok pair per case-language")
        left, right = pair
        if (left["criterion_statuses"] == right["criterion_statuses"]
            and left["critical_error_ids"] == right["critical_error_ids"]
            and left["ratings"] != right["ratings"]):
            flags.append({"comparison": "same_case_same_findings_two_judges",
                          "case_id": case_id, "judges": [left["provider"], right["provider"]],
                          "scores": [left["score"], right["score"]],
                          "ratings": [left["ratings"], right["ratings"]]})
    # Paired-language checks are questions, not bilingual equivalence claims.
    for family in sorted({row["family_id"] for row in rows}):
        for provider in ("gemini", "grok"):
            pair = [row for row in rows if row["family_id"] == family and row["provider"] == provider]
            if len(pair) != 2:
                raise ValueError("S23 expects EN/ZH pairs")
            left, right = sorted(pair, key=lambda row: row["language"])
            if left["criterion_statuses"] == right["criterion_statuses"] and left["ratings"] != right["ratings"]:
                flags.append({"comparison": "paired_language_same_findings_rating_gap_unadjudicated",
                              "family_id": family, "judge": provider,
                              "scores": [left["score"], right["score"]],
                              "ratings": [left["ratings"], right["ratings"]]})
    return flags


def audit(root: Path, s22_outer: Path, s19_repeat: Path) -> dict[str, Any]:
    policy = load_json(root / POLICY_PATH)
    if (policy.get("version") != "s23-v1-offline-boundary-review"
        or policy.get("status") != "non_enforced_author_hypotheses_not_clinical_adjudication"
        or [item.get("family_id") for item in policy.get("focus", [])] !=
           ["HC-MT-TRIAGE-018", "HC-MT-TRIAGE-020", "HC-MT-MEDSAFE-015"]):
        raise ValueError("Unknown S23 offline boundary policy")
    s20_result = s20.audit(root, s19_repeat)
    s22_result = s22_abort.audit(root, s22_outer)
    inputs = s21._inputs(root)
    if (sha256_json(s20_result) != policy["inputs"]["s20_verified_audit_sha256"]
        or s22_result["saved_artifacts_sha256"] != policy["inputs"]["s22_saved_artifacts_sha256"]
        or sha256_json(inputs["rubric"]) != policy["inputs"]["rubric_sha256"]):
        raise ValueError("S23 source audit or rubric differs from frozen boundary inputs")
    held = [row for row in s20_result["rows"] if "identical_packet_provisional_pass_hold" in row["flags"]]
    if len(held) != 2:
        raise ValueError("S23 expected the two exact-packet S20 pass holds")
    partial = _s22_partial_rows(root, s22_outer, s22_result, inputs)
    if len(partial) != 8:
        raise ValueError("S23 expected eight saved S22 partial-answer cells")
    return {"status": "s23_offline_boundary_diagnostic_not_scoring_contract",
            "policy_sha256": sha256_json(policy), "source_s20_audit_sha256": sha256_json(s20_result),
            "source_s22_artifacts_sha256": s22_result["saved_artifacts_sha256"],
            "current_point_impacts_before_caps": point_impacts(inputs["rubric"]),
            "s20_identical_packet_pass_holds": [
                {"case_id": row["case_id"], "judge": row["judge"],
                 "same_criterion_statuses": row["criterion_statuses_same"],
                 "same_critical_errors": row["critical_errors_same"],
                 "ratings_first_repeat": row["ratings_first_repeat"],
                 "score_delta": row["score_delta"], "pass_same": row["pass_same"]}
                for row in held],
            "s22_partial_rows": partial, "coherence_review_flags": _coherence_flags(partial),
            "author_boundary_hypotheses": policy["focus"],
            "proposed_non_enforced_mapping": policy["proposed_non_enforced_mapping"],
            "review_fields": policy["review_fields"],
            "candidate_calls": 0, "judge_calls": 0, "historical_scores_changed": 0,
            "limits": policy["limits"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline S23 boundary and sensitivity diagnostic")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--s22-dir", type=Path)
    parser.add_argument("--s19-repeat-dir", type=Path)
    parser.add_argument("--summary", action="store_true", help="Print a compact overview without authored answer text")
    args = parser.parse_args(argv)
    result = audit(args.root,
                   args.s22_dir or args.root / "work/s22_v1_first_2026-10-22",
                   args.s19_repeat_dir or args.root / "work/s19_multifamily_repeat_2026-10-21")
    if args.summary:
        rows = result.pop("s22_partial_rows")
        result["s22_partial_summary"] = [
            {"case_id": row["case_id"], "judge": row["provider"], "score": row["score"],
             "pass": row["pass"], "update_statuses": row["criterion_statuses"]["update"],
             "ratings": row["ratings"],
             "one_point_pass_flips": [item["rating"] + ("+1" if item["change"] > 0 else "-1")
                                      for item in row["one_point_counterfactuals"] if item.get("pass_flip")]}
            for row in rows]
        result.pop("author_boundary_hypotheses")
        result.pop("proposed_non_enforced_mapping")
        result.pop("review_fields")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
