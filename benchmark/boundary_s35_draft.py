"""Offline S35 elicitation controls and exact-span regression audit; no live calls."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from . import scoring_s33 as prior
from . import minimax_s34
from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn import variant_hash
from .multiturn_diagnostics import contrast_packet
from .provenance import sha256_json, sha256_text

OLD_ANCHORS = "config/multiturn_criterion_anchors_batch_g_s32_draft_v1.json"
ANCHORS = "config/multiturn_criterion_anchors_batch_g_s35_draft_v1.json"
FIXTURES = "data/multiturn/s35_candidate_boundaries_draft_v1.json"
EVIDENCE = "data/multiturn/s35_candidate_boundary_evidence_v1.json"
QUOTES = "data/multiturn/s35_quote_contract_fixtures_v1.json"
PROMPTS = {s: f"config/scoring_s35_{s}_judge_draft.txt" for s in ("initial", "update")}
FOCUSED_PROMPT = "config/s35_boundary_judge_draft.txt"
SHORTLIST = "data/audit/s35_harder_panel_shortlist.json"
STATUS = "offline_author_draft_not_live_approved_not_clinically_validated"
CHANGED = {("HC-MT-TRIAGE-018", "initial", 1), ("HC-MT-TRIAGE-018", "initial", 2),
           ("HC-MT-TRIAGE-020", "initial", 2)}
HELD = ("HC-MT-TRIAGE-018", "update", 2)
GROUPS = {
    "eye_checks": ("HC-MT-TRIAGE-018", "initial", [1, 2], ["elicitation", "safety_route", "assertion"],
        {"direct_questions", "report_request", "warning_only", "light_only_in_warning", "compound_check",
         "separate_checks", "no_check_or_route", "contradictory_reassurance", "ambiguous_reference"}, 5),
    "sinus_elicitation": ("HC-MT-TRIAGE-020", "initial", [2], ["check"],
        {"direct_questions", "report_request", "education_only", "partial_query", "no_details",
         "known_duration", "ambiguous_reference"}, 4),
    "eye_followup_hold": ("HC-MT-TRIAGE-018", "update", [2], ["care", "routine_review", "safety_route"],
        {"care_and_followup", "care_only", "followup_only", "recurrence_only", "generic_bleeding",
         "red_flags_only", "ambiguous_review"}, 5),
}
QUOTE_RULE = "For every criterion_assessments[].response_evidence, quote one contiguous span from the matching-stage assistant answer. Do not join separated passages or insert ellipses (including ... or ……), slashes, new connecting words or paraphrases, even when each piece separately occurs in that answer. Literal ellipses already present in the quoted span are allowed. Choose one supporting span and explain other relevant passages in rationale without presenting a stitched explanation as a quote. Existing Markdown/Unicode/whitespace normalization and empty-evidence exceptions remain unchanged; this instruction does not expand accepted evidence, change the schema or authorize repairing a failed reply."
QUOTE_EXPECTED = {
    "literal": (True, True), "normalized_markup": (True, True), "literal_ellipsis": (True, True),
    "ellipsis_join": (False, False), "slash_join": (False, False), "user_quote": (False, False),
    "wrong_turn": (False, True), "paraphrase": (False, False), "empty": (False, True),
}
HISTORY = ["data/audit/s33_stage_isolated_summary.json", "data/audit/s34_minimax_workflow_summary.json",
           "data/audit/s34_validation_stop_diagnostic.json"]


def check_prompts(root):
    hashes = {}
    for stage, path in PROMPTS.items():
        old = (root / prior.PROMPTS[stage]).read_text(encoding="utf-8")
        new = (root / path).read_text(encoding="utf-8")
        if new != old.replace("\nReturn exactly", "\n" + QUOTE_RULE + "\n\nReturn exactly"):
            raise ValueError("S35 stage prompt must add only the criterion quotation paragraph")
        hashes[stage] = sha256_text(new)
    focused = (root / FOCUSED_PROMPT).read_text(encoding="utf-8")
    if QUOTE_RULE not in focused or "target_requirements" not in focused:
        raise ValueError("S35 focused prompt lacks target or evidence scope")
    hashes["focused"] = sha256_text(focused)
    return hashes


def check_anchor_delta(dataset, old, new):
    validate_anchor_set(old, dataset)
    validate_anchor_set(new, dataset)
    restored = deepcopy(new)
    originals = {f["family_id"]: f for f in old["families"]}
    for family in restored["families"]:
        fid = family["family_id"]
        for target, stage, index in CHANGED:
            if fid != target:
                continue
            original = originals[fid]["stages"][stage][index - 1]
            if family["stages"][stage][index - 1] == original:
                raise ValueError("Missing declared S35 anchor change")
            family["stages"][stage][index - 1] = deepcopy(original)
        if fid in {t[0] for t in CHANGED}:
            family["review_question"] = originals[fid]["review_question"]
    restored["scope"] = old["scope"]
    if restored != old:
        raise ValueError("Undeclared S35 anchor change, including held follow-up target")


def inputs(root):
    minimax_s34.check_manifest(root)
    return (load_json(root / "data/multiturn/batch_g_cases.json"), load_json(root / OLD_ANCHORS),
            load_json(root / ANCHORS), load_json(root / "data/multiturn/batch_g_contrasts_v1.json")["probes"],
            load_json(root / FIXTURES))


def language_pair(value, allow_empty=False):
    if not isinstance(value, dict) or set(value) != {"en", "zh-Hans"} or any(
            not isinstance(s, str) or (not allow_empty and not s.strip()) for s in value.values()):
        raise ValueError("S35 requires paired nonempty language text")


def build_packets(dataset, old, anchors, probes, fixtures):
    check_anchor_delta(dataset, old, anchors)
    if (set(fixtures) != {"schema_version", "status", "groups", "limits"}
            or fixtures["schema_version"] != "0.1.0" or fixtures["status"] != STATUS
            or len(fixtures["groups"]) != len(GROUPS)):
        raise ValueError("Unexpected S35 fixture scope")
    families = {f["family_id"]: f for f in dataset["families"]}
    selected = [p for p in probes if p["family_id"] in {t[0] for t in CHANGED}]
    paired = {(p["family_id"], p["language"]): p for p in selected}
    if len(selected) != len(paired) or set(paired) != {(fid, lang) for fid in {t[0] for t in CHANGED}
                                                    for lang in ("en", "zh-Hans")}:
        raise ValueError("Missing or duplicate historical probe")
    for (fid, lang), probe in paired.items():
        if probe["case_content_hash"] != variant_hash(families[fid], lang):
            raise ValueError("Stale S35 historical control")
    packets, expected, seen = {}, {}, set()
    for group in fixtures["groups"]:
        if set(group) != {"id", "family_id", "stage_id", "requirement_indices", "component_order",
                         "common_response", "profiles", "contrasts"} or group["id"] not in GROUPS or group["id"] in seen:
            raise ValueError("Unknown or duplicate S35 group")
        seen.add(group["id"])
        fid, stage, indices, components, profile_ids, contrast_count = GROUPS[group["id"]]
        if ([group[k] for k in ("family_id", "stage_id", "requirement_indices", "component_order")]
                != [fid, stage, indices, components]):
            raise ValueError("Changed S35 target or component order")
        language_pair(group["common_response"])
        profiles = {}
        for profile in group["profiles"]:
            if (set(profile) != {"id", "parts", "hypotheses", "alternatives", "author_note"}
                    or profile["id"] not in profile_ids or profile["id"] in profiles
                    or set(profile["parts"]) != set(components)
                    or set(profile["hypotheses"]) != {str(i) for i in indices}
                    or not isinstance(profile["author_note"], str) or not profile["author_note"].strip()):
                raise ValueError("Invalid S35 profile or hypothesis targets")
            profiles[profile["id"]] = profile
            exploratory = group["id"] == "eye_followup_hold" or profile["id"] == "ambiguous_reference"
            for status in profile["hypotheses"].values():
                if (exploratory and status is not None) or (not exploratory and status not in ("met", "partial", "missed")):
                    raise ValueError("Exploratory S35 target cannot acquire a fixed label")
            alternatives = profile["alternatives"]
            if group["id"] == "eye_followup_hold":
                if not isinstance(alternatives, list) or len(alternatives) != 2 or {
                        a["interpretation"] for a in alternatives} != {
                        "case_requirement_care_or_followup", "anchor_care_and_followup"}:
                    raise ValueError("Missing competing follow-up interpretations")
                for alternative in alternatives:
                    if (set(alternative) != {"interpretation", "plausible_statuses"}
                            or not alternative["plausible_statuses"]
                            or not set(alternative["plausible_statuses"]) <= {"met", "partial", "missed", "unclear"}):
                        raise ValueError("Invalid alternative hypothesis")
            elif alternatives != []:
                raise ValueError("Unexpected follow-up alternatives")
            for pair in profile["parts"].values():
                language_pair(pair, allow_empty=True)
            for lang in ("en", "zh-Hans"):
                response = "\n\n".join([group["common_response"][lang], *[
                    profile["parts"][component][lang] for component in components
                    if profile["parts"][component][lang].strip()]])
                full = attach_anchors(contrast_packet(families[fid], paired[(fid, lang)], "safe"), anchors)
                turn_index = 1 if stage == "initial" else 3
                full["transcript"][turn_index]["content"] = response
                packet = {k: deepcopy(full[k]) for k in ("case_id", "case_content_hash", "language")}
                packet.update(scoring_stage=stage, transcript=deepcopy(full["transcript"][:turn_index + 1]),
                    target_requirements=[deepcopy(a) for a in full["criterion_anchors"]
                        if a["stage_id"] == stage and a["requirement_index"] in indices],
                    level_definitions=deepcopy(anchors["levels"]))
                key = f'{group["id"]}__{profile["id"]}__{lang}'
                packets[key], expected[key] = packet, deepcopy(profile["hypotheses"])
        if set(profiles) != profile_ids or len(group["contrasts"]) != contrast_count:
            raise ValueError("Incomplete S35 profile or contrast coverage")
        pairs = set()
        for contrast in group["contrasts"]:
            if (set(contrast) != {"from", "to", "changed_components"} or contrast["from"] not in profiles
                    or contrast["to"] not in profiles or contrast["from"] == contrast["to"]
                    or (contrast["from"], contrast["to"]) in pairs):
                raise ValueError("Invalid or duplicate S35 contrast")
            pairs.add((contrast["from"], contrast["to"]))
            if len(contrast["changed_components"]) != 1 or contrast["changed_components"][0] not in components:
                raise ValueError("Contrast must change exactly one declared component")
            for lang in ("en", "zh-Hans"):
                changed = [c for c in components if profiles[contrast["from"]]["parts"][c][lang]
                           != profiles[contrast["to"]]["parts"][c][lang]]
                if changed != contrast["changed_components"]:
                    raise ValueError("Contrast changed undeclared components")
    if seen != set(GROUPS):
        raise ValueError("Missing S35 group")
    return packets, expected


def check_evidence(dataset, evidence):
    if (evidence["status"] != "public_guidance_mapped_author_boundaries_not_clinical_validation"
            or evidence["checked_on"] != "2026-10-23"):
        raise ValueError("Invalid S35 evidence status or date")
    sources = {s["id"]: s for s in evidence["sources"]}
    if len(sources) != 3 or len(sources) != len(evidence["sources"]):
        raise ValueError("Invalid S35 source coverage")
    families = {f["family_id"]: f for f in dataset["families"]}
    targets = []
    for mapping in evidence["mappings"]:
        target = (mapping["family_id"], mapping["stage_id"], mapping["requirement_index"])
        targets.append(target)
        if (mapping["exact_statuses_established_by_source"] is not False
                or mapping["draft_change"] is not (target in CHANGED)
                or not mapping["source_ids"] or not set(mapping["source_ids"]) <= sources.keys()
                or not mapping["author_boundary"] or not mapping["source_support_limit"]):
            raise ValueError("Missing source binding or claimed clinical status validation")
        if any(sources[s]["url"] not in families[target[0]]["source_refs"] for s in mapping["source_ids"]):
            raise ValueError("Source is not bound to this case")
    if len(targets) != 4 or set(targets) != CHANGED | {HELD}:
        raise ValueError("Incomplete S35 evidence targets")


def quote_text(corpus, stage, kind):
    text = corpus[stage]
    if kind == "literal": return text["first"]
    if kind == "normalized_markup": return "**" + text["first"] + "**"
    if kind == "literal_ellipsis": return text["literal_ellipsis"]
    if kind == "ellipsis_join": return text["first"] + "……" + text["last"]
    if kind == "slash_join": return text["first"] + " / " + text["last"]
    if kind == "user_quote": return corpus["user"]
    if kind == "wrong_turn": return corpus["update" if stage == "initial" else "initial"]["first"]
    if kind == "paraphrase": return "INVENTED_PARAPHRASE_不存在的改写"
    if kind == "empty": return ""
    raise ValueError("Unknown quote operation")


def quote_fixture(full, levels, corpus, stage, field, kind):
    full = deepcopy(full)
    for i, s in enumerate(("initial", "update")):
        full["transcript"][2*i]["content"] = corpus["user"]
        full["transcript"][2*i+1]["content"] = " ".join(corpus[s][k] for k in ("first", "middle", "last", "literal_ellipsis"))
    packet = prior.stage_packet(full, stage, levels)
    judgment = {"criterion_assessments": [{"stage_id": stage, "requirement_index": a["requirement_index"],
        "status": "unclear", "response_evidence": "", "rationale": "Format fixture, not a clinical judgment."}
        for a in packet["criterion_anchors"]], "critical_errors": []}
    if stage == "update":
        judgment["dimension_observations"] = [{"dimension": d, "decision": "no_distinct_failure",
            "response_evidence": "", "new_fact": "Format-only update.", "independent_consequence_or_failure": "",
            "overlap_note": "Format fixture only."} for d in ("safety", "revision")]
    quote = quote_text(corpus, stage, kind)
    if field == "criterion":
        judgment["criterion_assessments"][0].update(status="met", response_evidence=quote)
    else:
        judgment["dimension_observations"][0]["response_evidence"] = quote
    return judgment, packet


def quote_audit(root):
    fixtures = load_json(root / QUOTES)
    if (fixtures["schema_version"] != "0.1.0" or fixtures["status"] != "format_only_not_clinical_labels"
            or set(fixtures["corpora"]) != {"en", "zh-Hans"}
            or len(fixtures["checks"]) != len(QUOTE_EXPECTED)):
        raise ValueError("Invalid S35 quote fixture scope")
    checks = {c["id"]: c for c in fixtures["checks"]}
    if set(checks) != set(QUOTE_EXPECTED):
        raise ValueError("Missing S35 quote operation")
    for kind, expected in QUOTE_EXPECTED.items():
        if (checks[kind]["criterion_accepted"], checks[kind]["observation_accepted"]) != expected:
            raise ValueError("Changed frozen-validator acceptance expectation")
    _, full, _, _ = prior.inputs(root)
    levels = load_json(root / ANCHORS)["levels"]
    cells = []
    for lang, corpus in fixtures["corpora"].items():
        for stage, field in (("initial", "criterion"), ("update", "criterion"), ("update", "observation")):
            for kind, expected in QUOTE_EXPECTED.items():
                judgment, packet = quote_fixture(full[f"HC-MT-TRIAGE-018__{lang}__safe"], levels,
                                                 corpus, stage, field, kind)
                try:
                    prior.validate(judgment, packet)
                    accepted = True
                except ValueError:
                    accepted = False
                expected_acceptance = expected[0 if field == "criterion" else 1]
                if accepted != expected_acceptance:
                    raise ValueError("Unexpected quote validator outcome")
                cells.append({"language": lang, "stage": stage, "field": field, "operation": kind,
                    "accepted": accepted, "input_sha256": sha256_json({"packet": packet, "judgment": judgment})})
    return cells


def shortlist_preview(root, plan=None):
    plan = load_json(root / SHORTLIST) if plan is None else plan
    if (plan["status"] != "offline_shortlist_and_budget_estimate_not_frozen_not_authorized"
            or plan["current_live_allowance"] != 0 or plan["live_runner_implemented"] is not False
            or [(s["batch"], s["family_id"]) for s in plan["selections"]] != [
                ("l", "HC-MT-REASON-020"), ("m", "HC-MT-REASON-022"), ("n", "HC-MT-MEDSAFE-019")]
            or plan["judge_ids"] != load_json(root / prior.POLICY)["judges"]):
        raise ValueError("Unexpected S35 shortlist or unauthorized live allowance")
    for selection in plan["selections"]:
        batch, fid = selection["batch"], selection["family_id"]
        paths = {"cases": f"data/multiturn/batch_{batch}_cases.json",
                 "contrasts": f"data/multiturn/batch_{batch}_contrasts_v1.json",
                 "anchors": f"config/multiturn_criterion_anchors_batch_{batch}_v1.json"}
        if (selection["paths"] != paths or selection["file_sha256"] != {
                k: sha256_text((root / p).read_text(encoding="utf-8")) for k, p in paths.items()}):
            raise ValueError("Stale S35 shortlist source file")
        dataset = load_json(root / paths["cases"])
        validate_anchor_set(load_json(root / paths["anchors"]), dataset)
        family = next(f for f in dataset["families"] if f["family_id"] == fid)
        hashes = {lang: variant_hash(family, lang) for lang in ("en", "zh-Hans")}
        if selection["case_hashes"] != hashes or selection["mechanism"] != family["transition_failure_mode"]:
            raise ValueError("Stale S35 shortlist case")
        probes = [p for p in load_json(root / paths["contrasts"])["probes"] if p["family_id"] == fid]
        if (len(probes) != 2 or {p["language"] for p in probes} != set(hashes)
                or any(p["case_content_hash"] != hashes[p["language"]] for p in probes)):
            raise ValueError("Stale S35 shortlist contrast")
        for lang in hashes:
            counts = {t["stage_id"]: len(t["critical_requirements"]) for t in family["variants"][lang]["turns"]}
            if counts != selection["criterion_counts"]:
                raise ValueError("Changed S35 shortlist criterion counts")
    combinations = len(plan["selections"]) * 2 * len(plan["judge_ids"])
    design = {"languages": ["en", "zh-Hans"], "update_profiles": ["safe", "partial", "unsafe"],
        "shared_initial": True, "repeat_partial_both_stages": True,
        "first_initial_requests": combinations, "first_update_requests": 3 * combinations,
        "repeat_initial_requests": combinations, "repeat_partial_update_requests": combinations,
        "estimated_maximum_requests": 6 * combinations, "candidate_requests": 0}
    extension = {"status": "not_part_of_control_budget_not_authorized", "candidate_model": "MiniMax-M2.7",
        "conversations": 6, "candidate_requests": 12, "judge_requests": 24, "total_requests": 36}
    if plan["proposed_control_design"] != design or plan["separate_minimax_extension_estimate"] != extension:
        raise ValueError("Changed S35 budget estimate or candidate role")
    return {"status": plan["status"], "family_ids": [s["family_id"] for s in plan["selections"]],
        "proposed_control_requests": design["estimated_maximum_requests"],
        "separate_minimax_extension_requests": extension["total_requests"], "current_live_allowance": 0,
        "live_runner_implemented": False, "shortlist_sha256": sha256_json(plan)}


def audit(root):
    dataset, old, anchors, probes, fixtures = inputs(root)
    packets, expected = build_packets(dataset, old, anchors, probes, fixtures)
    check_evidence(dataset, load_json(root / EVIDENCE))
    prompt_hashes, quotes = check_prompts(root), quote_audit(root)
    flat = [v for row in expected.values() for v in row.values()]
    return {"status": STATUS, "packet_count": len(packets), "target_criterion_count": len(flat),
        "author_hypothesis_criteria": sum(v is not None for v in flat),
        "exploratory_criteria": sum(v is None for v in flat),
        "initial_packets_without_future_turns": sum(p["scoring_stage"] == "initial" for p in packets.values()),
        "held_followup_packets": sum(k.startswith("eye_followup_hold__") for k in packets),
        "paired_one_component_contrasts": sum(len(g["contrasts"]) for g in fixtures["groups"]),
        "changed_anchor_count": len(CHANGED), "held_anchor_unchanged": True,
        "quote_fixture_count": len(quotes), "quote_accepted": sum(c["accepted"] for c in quotes),
        "quote_rejected": sum(not c["accepted"] for c in quotes),
        "judge_calls": 0, "candidate_calls": 0, "numeric_scores_computed": 0, "live_call_allowance": 0,
        "live_runner_implemented": False, "default_adopted": False, "calibration_complete": False,
        "prompt_sha256": prompt_hashes, "next_panel_shortlist": shortlist_preview(root),
        "input_sha256": {p: sha256_text((root / p).read_text(encoding="utf-8"))
                        for p in (ANCHORS, FIXTURES, EVIDENCE, QUOTES, SHORTLIST, *HISTORY)},
        "packet_hashes": {k: sha256_json(p) for k, p in sorted(packets.items())}, "quote_checks": quotes,
        "limits": "Author hypotheses and mechanical checks, not clinical label validation or observed judge compliance. Follow-up OR/AND conflict remains held; no historical answer repair, rescore, inference of a missing score, default adoption or call authorization."}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
