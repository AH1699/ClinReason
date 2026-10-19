"""Bounded, development-only multi-model/two-judge conversation diagnostic."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn_diagnostics import contrast_packet
from .local_settings import read_setting
from .multiturn import (build_judge_packet, ordered_variants, variant_hash,
                        variant_id, write_batch)
from .multiturn_judging import CRITERION_VALIDATOR_VERSION, GeminiMultiturnJudge, score_judgment
from .provenance import sha256_json, sha256_text
from .providers.gemini_conversation import GeminiConversationProvider
from .providers.grok_conversation import GrokConversationProvider
from .providers.grok_multiturn_judge import GrokMultiturnJudge
from .providers.minimax_conversation import MiniMaxConversationProvider


KEYS = {"gemini": "GEMINI_API_KEY", "grok": "GROK_API_KEY",
        "minimax": "MINIMAX_API_KEY"}
CANDIDATES = {"gemini": GeminiConversationProvider,
              "grok": GrokConversationProvider,
              "minimax": MiniMaxConversationProvider}
JUDGES = {"gemini": GeminiMultiturnJudge, "grok": GrokMultiturnJudge}


def prepare_matrix(
    roster: dict[str, Any], dataset: dict[str, Any], *,
    candidate_id: str | None = None, case_id: str | None = None,
    selected_case_ids: list[str] | None = None,
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], str]], list[dict[str, str]], list[dict[str, str]]]:
    if not isinstance(roster, dict) or set(roster) != {"schema_version", "status", "case_ids", "candidates", "judges"}:
        raise ValueError("Model roster has invalid fields")
    if roster["schema_version"] != "0.1.0" or roster["status"] != "development_only":
        raise ValueError("Model roster must be a versioned development-only roster")
    candidates, judges, case_ids = (roster[key] for key in ("candidates", "judges", "case_ids"))
    if (not isinstance(candidates, list) or not candidates or not isinstance(judges, list)
        or len(judges) != 2 or not isinstance(case_ids, list) or not case_ids):
        raise ValueError("Model roster needs candidates, two judges, and cases")
    for items, allowed in ((candidates, CANDIDATES), (judges, JUDGES)):
        ids: set[str] = set()
        for item in items:
            if (not isinstance(item, dict) or set(item) != {"id", "provider", "model"}
                or not isinstance(item["id"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_-]*", item["id"])
                or item["id"] in ids or item["provider"] not in allowed
                or not isinstance(item["model"], str) or not item["model"]
                or any(char.isspace() for char in item["model"])):
                raise ValueError("Model roster has an invalid or duplicate model entry")
            ids.add(item["id"])
    if {item["provider"] for item in judges} != {"gemini", "grok"}:
        raise ValueError("Exactly one Gemini and one Grok judge are required")
    if candidate_id is not None:
        candidates = [item for item in candidates if item["id"] == candidate_id]
        if not candidates:
            raise ValueError("Unknown candidate ID in model roster")
    if case_id is not None and selected_case_ids is not None:
        raise ValueError("Select case_id or selected_case_ids, not both")
    if case_id is not None:
        case_ids = [case_id]
    if selected_case_ids is not None:
        case_ids = selected_case_ids
    if (not isinstance(case_ids, list) or not case_ids
        or any(not isinstance(value, str) for value in case_ids)
        or len(case_ids) != len(set(case_ids))):
        raise ValueError("Model roster case IDs must be unique strings")
    by_id = {variant_id(family, language): (family, language)
             for family, language in ordered_variants(dataset)}
    if any(value not in by_id for value in case_ids):
        raise ValueError("Model roster references an unknown multi-turn case")
    selected = [by_id[value] for value in case_ids]
    plan = {
        "status": "dry_run_no_api_calls_development_only",
        "roster_sha256": sha256_json(roster), "dataset_sha256": sha256_json(dataset),
        "case_revisions": [
            {"case_id": variant_id(family, language),
             "case_version": family["version"],
             "case_content_hash": variant_hash(family, language)}
            for family, language in selected
        ],
        "candidates": candidates, "judges": judges,
        "candidate_calls": len(candidates) * len(selected) * 2,
        "judge_calls": len(candidates) * len(selected) * len(judges),
        "total_api_calls": len(candidates) * len(selected) * (2 + len(judges)),
        "warning": "Call count is bounded, monetary cost is not; scores are draft AI-judge diagnostics, not a clinical ranking.",
    }
    return plan, selected, candidates, judges


def _write_json_new(path: Path, data: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def run_matrix(
    plan: dict[str, Any], selected: list[tuple[dict[str, Any], str]],
    candidates: list[dict[str, str]], judges: list[dict[str, str]],
    dataset: dict[str, Any], rubric: dict[str, Any], *,
    output_dir: str | Path, env_file: str | Path,
    candidate_instruction: str, judge_instruction: str,
    max_api_calls: int, timeout: float = 240, retries: int = 0,
    anchor_set: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if type(max_api_calls) is not int or max_api_calls < plan["total_api_calls"]:
        raise ValueError(f"--max-api-calls must be at least {plan['total_api_calls']} for this selection")
    if timeout <= 0 or retries != 0:
        raise ValueError("Model-matrix timeout must be positive and automatic retries are disabled")
    if anchor_set is not None:
        validate_anchor_set(anchor_set, dataset)
        for family, language in selected:
            item = next((entry for entry in anchor_set["families"]
                         if entry["family_id"] == family["family_id"]), None)
            if item is None or item["case_hashes"].get(language) != variant_hash(family, language):
                raise ValueError("Selected case lacks a matching criterion anchor")
    target = Path(output_dir)
    if target.exists():
        raise FileExistsError("Model-matrix output directory exists; choose a fresh directory")
    # Preflight all credentials before any billable request.
    providers = {item["provider"] for item in [*candidates, *judges]}
    keys = {provider: read_setting(env_file, KEYS[provider], secret=True)
            for provider in providers}
    judge_instances = {
        spec["id"]: JUDGES[spec["provider"]](
            model=spec["model"], api_key=keys[spec["provider"]],
            instruction=judge_instruction, timeout=timeout, retries=retries,
        )
        for spec in judges
    }
    target.mkdir(parents=True)
    _write_json_new(target / "plan.json", {**plan, "status": "live_plan_started",
                                           "generated_at": datetime.now(timezone.utc).isoformat()})
    results: list[dict[str, Any]] = []
    for spec in candidates:
        candidate = CANDIDATES[spec["provider"]](
            model=spec["model"], api_key=keys[spec["provider"]],
            instruction=candidate_instruction, timeout=timeout, retries=retries,
        )
        for family, language in selected:
            case_id = variant_id(family, language)
            stem = f"{spec['id']}__{case_id}"
            answer_path = target / f"{stem}.answers.jsonl"
            write_batch(dataset, [(family, language)], candidate, answer_path,
                        instruction=candidate_instruction,
                        provenance={"matrix_roster_sha256": plan["roster_sha256"]})
            with answer_path.open(encoding="utf-8") as handle:
                answer = json.loads(handle.readline())
            answer_manifest = json.loads(answer_path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
            packet = build_judge_packet(family, language, answer)
            if anchor_set is not None:
                packet = attach_anchors(packet, anchor_set)
            item: dict[str, Any] = {
                "candidate_id": spec["id"], "candidate_provider": spec["provider"],
                "candidate_model_requested": spec["model"],
                "candidate_model_returned": candidate.model_version,
                "candidate_request_parameters": answer_manifest["actual_request_parameters"],
                "case_id": case_id, "case_content_hash": packet["case_content_hash"],
                "answer_file": answer_path.name, "judges": [],
            }
            for judge_spec in judges:
                judge = judge_instances[judge_spec["id"]]
                judge.rejected_output_path = target / f"{stem}__{judge_spec['id']}.rejected.json"
                judgment = judge.evaluate(packet)
                score = score_judgment(judgment, packet, rubric)
                judge_path = target / f"{stem}__{judge_spec['id']}.judgment.json"
                self_judge = judge_spec["provider"] == spec["provider"]
                same_model = self_judge and judge_spec["model"] == spec["model"]
                _write_json_new(judge_path, {
                    "status": "experimental_unvalidated_ai_judge",
                    "case_id": case_id, "case_content_hash": packet["case_content_hash"],
                    "candidate_id": spec["id"], "judge_id": judge_spec["id"],
                    "judge_provider": judge_spec["provider"],
                    "judge_model_requested": judge_spec["model"],
                    "judge_model_returned": judge.model_version,
                    "same_vendor_as_candidate": self_judge,
                    "same_model_as_candidate": same_model,
                    "judge_instruction_sha256": sha256_text(judge_instruction),
                    "rubric_sha256": sha256_json(rubric),
                    "judge_contract": "criterion_v2" if anchor_set is not None else "legacy_v1",
                    "criterion_validator_version": CRITERION_VALIDATOR_VERSION if anchor_set is not None else None,
                    "criterion_anchors_sha256": sha256_json(anchor_set) if anchor_set is not None else None,
                    "judgment": judgment, "score": score,
                })
                item["judges"].append({
                    "judge_id": judge_spec["id"],
                    "provider": judge_spec["provider"],
                    "model_requested": judge_spec["model"],
                    "model_returned": judge.model_version,
                    "same_vendor_as_candidate": self_judge,
                    "same_model_as_candidate": same_model,
                    "gated_score": score["gated_score"],
                    "hard_fail": score["hard_fail"],
                    "review_required": True,
                    "judgment_file": judge_path.name,
                })
            item["judge_score_gap"] = abs(
                item["judges"][0]["gated_score"] - item["judges"][1]["gated_score"]
            )
            results.append(item)
    report = {
        "status": "experimental_unvalidated_two_ai_judges_not_clinical_ranking",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roster_sha256": plan["roster_sha256"],
        "dataset_sha256": plan["dataset_sha256"],
        "candidate_instruction_sha256": sha256_text(candidate_instruction),
        "judge_instruction_sha256": sha256_text(judge_instruction),
        "rubric_sha256": sha256_json(rubric),
        "judge_contract": "criterion_v2" if anchor_set is not None else "legacy_v1",
        "criterion_validator_version": CRITERION_VALIDATOR_VERSION if anchor_set is not None else None,
        "criterion_anchors_sha256": sha256_json(anchor_set) if anchor_set is not None else None,
        "actual_api_calls": plan["total_api_calls"],
        "results": results,
        "limitations": ["draft public cases and labels", "uncalibrated AI judges",
                        "same-vendor judge preference possible", "provider prompt serialization differs",
                        "provider-default sampling and model aliases limit replay"],
    }
    _write_json_new(target / "report.json", report)
    return {"output_dir": str(target), "report": str(target / "report.json"),
            "candidate_case_count": len(results), "api_calls": plan["total_api_calls"],
            "status": report["status"]}


def judge_saved_matrix_answer(
    source_dir: str | Path, roster: dict[str, Any], dataset: dict[str, Any],
    rubric: dict[str, Any], *, output_dir: str | Path, env_file: str | Path,
    candidate_instruction: str, judge_instruction: str,
    max_api_calls: int, timeout: float = 240,
    anchor_set: dict[str, Any] | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    """Judge one previously saved answer without instantiating a candidate provider."""
    if max_api_calls != 2 or timeout <= 0:
        raise ValueError("Saved-answer recovery requires exactly two judge calls and positive timeout")
    source, target = Path(source_dir), Path(output_dir)
    if target.exists():
        raise FileExistsError("Judge-only output directory exists; choose a fresh directory")
    plan = json.loads((source / "plan.json").read_text(encoding="utf-8"))
    if (plan.get("roster_sha256") != sha256_json(roster)
        or plan.get("dataset_sha256") != sha256_json(dataset)
        or len(plan.get("candidates", [])) != 1 or not plan.get("case_revisions")
        or len(plan.get("judges", [])) != 2
        or {item.get("provider") for item in plan["judges"]} != {"gemini", "grok"}):
        raise ValueError("Saved-answer plan does not match current dataset/roster or is not a one-case two-judge plan")
    candidate = plan["candidates"][0]
    if candidate not in roster["candidates"] or plan["judges"] != roster["judges"]:
        raise ValueError("Saved-answer model or judge selection differs from frozen roster")
    if case_id is None:
        if len(plan["case_revisions"]) != 1:
            raise ValueError("Multi-case saved run requires --case-id to select one answer")
        case_id = plan["case_revisions"][0]["case_id"]
    revisions = [row for row in plan["case_revisions"] if row.get("case_id") == case_id]
    if len(revisions) != 1:
        raise ValueError("Selected saved-answer case is absent or duplicated in plan")
    revision = revisions[0]
    selected = next(((family, language) for family, language in ordered_variants(dataset)
                     if variant_id(family, language) == case_id), None)
    if selected is None:
        raise ValueError("Saved-answer case is not in the current dataset")
    family, language = selected
    if revision != {"case_id": case_id, "case_version": family["version"],
                    "case_content_hash": variant_hash(family, language)}:
        raise ValueError("Saved-answer case revision is stale")
    stem = f"{candidate['id']}__{case_id}"
    answer_path = source / f"{stem}.answers.jsonl"
    manifest_path = source / f"{stem}.answers.manifest.json"
    answer_text = answer_path.read_text(encoding="utf-8")
    rows = [line for line in answer_text.splitlines() if line.strip()]
    if len(rows) != 1:
        raise ValueError("Saved answer must contain exactly one case")
    answer = json.loads(rows[0])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("dataset_sha256") != plan["dataset_sha256"]
        or manifest.get("candidate_instruction_sha256") != sha256_text(candidate_instruction)
        or manifest.get("case_revisions") != [revision]
        or manifest.get("requested_model") != candidate["model"]
        or answer.get("model_id") != candidate["model"]
        or manifest.get("provider") != answer.get("provider")
        or manifest.get("returned_model") != answer.get("model_version")
        or manifest.get("provenance", {}).get("matrix_roster_sha256") != plan["roster_sha256"]):
        raise ValueError("Saved-answer manifest does not match the frozen plan or instruction")
    packet = build_judge_packet(family, language, answer)
    if anchor_set is not None:
        validate_anchor_set(anchor_set, dataset)
        packet = attach_anchors(packet, anchor_set)
    # Validate all local inputs and output target before reading secrets or making requests.
    keys = {provider: read_setting(env_file, KEYS[provider], secret=True)
            for provider in ("gemini", "grok")}
    judges = {spec["id"]: JUDGES[spec["provider"]](
        model=spec["model"], api_key=keys[spec["provider"]],
        instruction=judge_instruction, timeout=timeout, retries=0,
    ) for spec in plan["judges"]}
    target.mkdir(parents=True)
    results = []
    for spec in plan["judges"]:
        judge = judges[spec["id"]]
        judge.rejected_output_path = target / f"{stem}__{spec['id']}.rejected.json"
        judgment = judge.evaluate(packet)
        score = score_judgment(judgment, packet, rubric)
        judge_path = target / f"{stem}__{spec['id']}.judgment.json"
        same_vendor = spec["provider"] == candidate["provider"]
        _write_json_new(judge_path, {
            "status": "experimental_unvalidated_ai_judge", "case_id": case_id,
            "case_content_hash": packet["case_content_hash"],
            "candidate_id": candidate["id"], "judge_id": spec["id"],
            "judge_provider": spec["provider"], "judge_model_requested": spec["model"],
            "judge_model_returned": judge.model_version,
            "same_vendor_as_candidate": same_vendor,
            "same_model_as_candidate": same_vendor and spec["model"] == candidate["model"],
            "judge_instruction_sha256": sha256_text(judge_instruction),
            "rubric_sha256": sha256_json(rubric),
            "judge_contract": "criterion_v2" if anchor_set is not None else "legacy_v1",
            "criterion_validator_version": CRITERION_VALIDATOR_VERSION if anchor_set is not None else None,
            "criterion_anchors_sha256": sha256_json(anchor_set) if anchor_set is not None else None,
            "judgment": judgment, "score": score,
        })
        results.append({
            "judge_id": spec["id"], "provider": spec["provider"],
            "model_requested": spec["model"], "model_returned": judge.model_version,
            "same_vendor_as_candidate": same_vendor,
            "same_model_as_candidate": same_vendor and spec["model"] == candidate["model"],
            "gated_score": score["gated_score"], "hard_fail": score["hard_fail"],
            "review_required": True, "judgment_file": judge_path.name,
        })
    report = {
        "status": "experimental_unvalidated_two_ai_judges_not_clinical_ranking",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recovery_mode": "judge_only_no_candidate_calls",
        "source_answer_sha256": sha256_text(answer_text),
        "roster_sha256": plan["roster_sha256"], "dataset_sha256": plan["dataset_sha256"],
        "candidate_instruction_sha256": sha256_text(candidate_instruction),
        "judge_instruction_sha256": sha256_text(judge_instruction),
        "rubric_sha256": sha256_json(rubric),
        "judge_contract": "criterion_v2" if anchor_set is not None else "legacy_v1",
        "criterion_validator_version": CRITERION_VALIDATOR_VERSION if anchor_set is not None else None,
        "criterion_anchors_sha256": sha256_json(anchor_set) if anchor_set is not None else None,
        "actual_api_calls": 2,
        "results": [{
            "candidate_id": candidate["id"], "candidate_provider": candidate["provider"],
            "candidate_model_requested": candidate["model"],
            "candidate_model_returned": answer["model_version"],
            "candidate_request_parameters": manifest["actual_request_parameters"],
            "case_id": case_id, "case_content_hash": packet["case_content_hash"],
            "answer_file": answer_path.name, "judges": results,
            "judge_score_gap": abs(results[0]["gated_score"] - results[1]["gated_score"]),
        }],
        "limitations": ["draft public cases and labels", "uncalibrated AI judges",
                        "same-vendor judge preference possible", "saved candidate answer not regenerated"],
    }
    _write_json_new(target / "report.json", report)
    return {"output_dir": str(target), "report": str(target / "report.json"),
            "candidate_calls": 0, "judge_calls": 2, "status": report["status"]}


def run_anchored_contrast(
    probe: dict[str, Any], roster: dict[str, Any], dataset: dict[str, Any],
    rubric: dict[str, Any], anchors: dict[str, Any], *, output_dir: str | Path,
    env_file: str | Path, judge_instruction: str, max_api_calls: int,
    timeout: float = 240,
) -> dict[str, Any]:
    """Run two judges on fixed strong/partial/unsafe text, with no candidate calls."""
    if max_api_calls != 6 or timeout <= 0:
        raise ValueError("Contrast requires exactly six judge calls and positive timeout")
    target = Path(output_dir)
    if target.exists():
        raise FileExistsError("Contrast output directory exists; choose a fresh directory")
    validate_anchor_set(anchors, dataset)
    if (set(probe) != {"schema_version", "status", "family_id", "language", "case_content_hash",
                       "expected_unsafe_error_id", "initial_response", "safe_update_response",
                       "partial_update_response", "unsafe_update_response"}
        or probe["schema_version"] != "0.1.0"
        or probe["status"] != "synthetic_unreviewed_development_probe"):
        raise ValueError("Invalid synthetic contrast probe")
    family = next((item for item in dataset["families"] if item["family_id"] == probe["family_id"]), None)
    if family is None or probe["language"] not in family["variants"] or probe["case_content_hash"] != variant_hash(family, probe["language"]):
        raise ValueError("Synthetic contrast probe does not match exact case revision")
    if probe["expected_unsafe_error_id"] not in {
        error["id"] for error in family["variants"][probe["language"]]["turns"][1]["critical_errors"]
    }:
        raise ValueError("Probe expected error is not configured for update")
    packets = {variant: attach_anchors(contrast_packet(family, probe, variant), anchors)
               for variant in ("safe", "partial", "unsafe")}
    judge_specs = roster["judges"]
    if len(judge_specs) != 2 or {spec["provider"] for spec in judge_specs} != {"gemini", "grok"}:
        raise ValueError("Contrast requires the frozen Gemini/Grok judges")
    keys = {provider: read_setting(env_file, KEYS[provider], secret=True)
            for provider in ("gemini", "grok")}
    judges = {spec["id"]: JUDGES[spec["provider"]](
        model=spec["model"], api_key=keys[spec["provider"]],
        instruction=judge_instruction, timeout=timeout, retries=0,
    ) for spec in judge_specs}
    target.mkdir(parents=True)
    results = {}
    for spec in judge_specs:
        judge = judges[spec["id"]]
        per_variant = {}
        for variant, packet in packets.items():
            judge.rejected_output_path = target / f"{spec['id']}__{variant}.rejected.json"
            judgment = judge.evaluate(packet)
            score = score_judgment(judgment, packet, rubric)
            _write_json_new(target / f"{spec['id']}__{variant}.judgment.json", {
                "case_id": packet["case_id"], "case_content_hash": packet["case_content_hash"],
                "probe_sha256": sha256_json(probe), "judge_instruction_sha256": sha256_text(judge_instruction),
                "criterion_anchors_sha256": sha256_json(anchors), "rubric_sha256": sha256_json(rubric),
                "judge_id": spec["id"], "judge_provider": spec["provider"],
                "judge_model_requested": spec["model"], "judge_model_returned": judge.model_version,
                "variant": variant, "judgment": judgment, "score": score,
            })
            per_variant[variant] = {
                "gated_score": score["gated_score"], "hard_fail": score["hard_fail"],
                "pass": score["pass"],
                "critical_error_ids": [error["error_id"] for error in judgment["critical_errors"]],
                "criterion_statuses": [item["status"] for item in judgment["criterion_assessments"]],
            }
        results[spec["provider"]] = {
            "model_requested": spec["model"], "model_returned": judge.model_version,
            "variants": per_variant,
            "ordered_scores": per_variant["safe"]["gated_score"] > per_variant["partial"]["gated_score"] > per_variant["unsafe"]["gated_score"],
            "unsafe_error_detected": probe["expected_unsafe_error_id"] in per_variant["unsafe"]["critical_error_ids"],
            "unsafe_false_pass": per_variant["unsafe"]["pass"],
        }
    report = {
        "status": "synthetic_contrast_two_ai_judges_not_clinical_validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": variant_id(family, probe["language"]),
        "case_content_hash": probe["case_content_hash"],
        "probe_sha256": sha256_json(probe), "roster_sha256": sha256_json(roster),
        "dataset_sha256": sha256_json(dataset), "rubric_sha256": sha256_json(rubric),
        "criterion_anchors_sha256": sha256_json(anchors),
        "judge_instruction_sha256": sha256_text(judge_instruction),
        "candidate_calls": 0, "judge_calls": 6, "results": results,
        "warning": "Synthetic authored answers test grader behavior only; no human clinical ground truth.",
    }
    _write_json_new(target / "report.json", report)
    return {"output_dir": str(target), "report": str(target / "report.json"),
            "candidate_calls": 0, "judge_calls": 6, "status": report["status"]}


def compare_matrix_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Align completed matrix reports without treating their scores as ground truth."""
    if len(reports) < 2:
        raise ValueError("Compare at least two completed model-matrix reports")
    required = ("roster_sha256", "dataset_sha256", "candidate_instruction_sha256",
                "judge_instruction_sha256", "rubric_sha256", "judge_contract",
                "criterion_anchors_sha256", "criterion_validator_version")
    first = reports[0]
    expected_status = "experimental_unvalidated_two_ai_judges_not_clinical_ranking"
    if first.get("status") != expected_status or not first.get("results"):
        raise ValueError("First model-matrix report is incomplete")

    def index(report: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]], dict[str, tuple[str, str]]]:
        if report.get("status") != expected_status or any(report.get(key) != first.get(key) for key in required):
            raise ValueError("Model-matrix reports have incompatible provenance or incomplete status")
        rows = report.get("results")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Model-matrix report contains no results")
        candidates = {row.get("candidate_id") for row in rows if isinstance(row, dict)}
        if len(candidates) != 1 or None in candidates:
            raise ValueError("Each compared report must contain exactly one candidate")
        if len({sha256_json(row.get("candidate_request_parameters")) for row in rows}) != 1:
            raise ValueError("Candidate request policy changed within a matrix report")
        by_case = {row.get("case_id"): row for row in rows if isinstance(row, dict)}
        if len(by_case) != len(rows) or None in by_case:
            raise ValueError("Model-matrix report has duplicate or missing cases")
        judge_models: dict[str, tuple[str, str]] = {}
        for row in rows:
            judges = row.get("judges")
            if not isinstance(judges, list) or len(judges) != 2:
                raise ValueError("Model-matrix report lacks two judges")
            providers = {judge.get("provider") for judge in judges if isinstance(judge, dict)}
            if providers != {"gemini", "grok"}:
                raise ValueError("Model-matrix report judge providers changed")
            for judge in judges:
                provider = judge["provider"]
                model_pair = (judge.get("model_requested"), judge.get("model_returned"))
                if (not all(isinstance(value, str) and value for value in model_pair)
                    or provider in judge_models and judge_models[provider] != model_pair
                    or type(judge.get("gated_score")) not in (int, float)
                    or not 0 <= judge["gated_score"] <= 100):
                    raise ValueError("Model-matrix report has incompatible judge models or scores")
                judge_models[provider] = model_pair
        return next(iter(candidates)), by_case, judge_models

    first_candidate, first_cases, first_judges = index(first)
    seen_candidates = {first_candidate}
    candidate_results = []
    for report in reports:
        candidate, cases, judge_models = index(report)
        if candidate != first_candidate and candidate in seen_candidates:
            raise ValueError("Compared reports repeat a candidate")
        if candidate != first_candidate:
            seen_candidates.add(candidate)
        if set(cases) != set(first_cases) or judge_models != first_judges or any(
            cases[case_id].get("case_content_hash") != first_cases[case_id].get("case_content_hash")
            for case_id in first_cases
        ):
            raise ValueError("Compared reports do not use the same case revisions and judges")
        candidate_results.append({
            "candidate_id": candidate,
            "candidate_provider": next(iter(cases.values()))["candidate_provider"],
            "candidate_model_requested": next(iter(cases.values()))["candidate_model_requested"],
            "candidate_model_returned": next(iter(cases.values()))["candidate_model_returned"],
            "candidate_request_parameters": next(iter(cases.values())).get("candidate_request_parameters"),
            "cases": [
                {"case_id": case_id,
                 "judge_scores": {judge["provider"]: judge["gated_score"]
                                  for judge in cases[case_id]["judges"]},
                 "judge_score_gap": cases[case_id]["judge_score_gap"]}
                for case_id in sorted(first_cases)
            ],
        })
    if len(seen_candidates) != len(reports):
        raise ValueError("Compared reports repeat a candidate")
    return {
        "status": "experimental_unvalidated_multi_candidate_comparison_not_ranking",
        "case_revisions": [
            {"case_id": case_id, "case_content_hash": first_cases[case_id]["case_content_hash"]}
            for case_id in sorted(first_cases)
        ],
        "judges": {provider: {"requested": pair[0], "returned": pair[1]}
                   for provider, pair in sorted(first_judges.items())},
        "roster_sha256": first["roster_sha256"],
        "dataset_sha256": first["dataset_sha256"],
        "rubric_sha256": first["rubric_sha256"],
        "candidate_results": candidate_results,
        "warning": "Provisional public development cases; AI-judge results are not clinical rankings.",
    }


def audit_matrix_report(report: dict[str, Any], report_dir: str | Path) -> dict[str, Any]:
    """Expose per-requirement differences, score ceilings, and safety gates without averaging judges."""
    if report.get("status") != "experimental_unvalidated_two_ai_judges_not_clinical_ranking":
        raise ValueError("Expected a completed two-judge matrix report")
    directory = Path(report_dir)
    rows = []
    for item in report.get("results", []):
        judges = item.get("judges", [])
        if len(judges) != 2 or {entry.get("provider") for entry in judges} != {"gemini", "grok"}:
            raise ValueError("Matrix audit requires exactly two independent judges per case")
        details = {}
        for entry in judges:
            filename = entry.get("judgment_file")
            if not isinstance(filename, str) or Path(filename).name != filename:
                raise ValueError("Unsafe judgment filename in matrix report")
            record = json.loads((directory / filename).read_text(encoding="utf-8"))
            if (record.get("case_id") != item.get("case_id")
                or record.get("case_content_hash") != item.get("case_content_hash")
                or record.get("candidate_id") != item.get("candidate_id")
                or record.get("judge_provider") != entry["provider"]
                or record.get("judge_model_requested") != entry.get("model_requested")
                or record.get("judge_model_returned") != entry.get("model_returned")
                or record.get("judge_instruction_sha256") != report.get("judge_instruction_sha256")
                or record.get("rubric_sha256") != report.get("rubric_sha256")
                or record.get("judge_contract") != report.get("judge_contract")
                or record.get("criterion_anchors_sha256") != report.get("criterion_anchors_sha256")
                or record.get("score", {}).get("gated_score") != entry.get("gated_score")
                or record.get("score", {}).get("hard_fail") != entry.get("hard_fail")):
                raise ValueError("Matrix audit found inconsistent judgment provenance or score")
            judgment = record["judgment"]
            if report.get("judge_contract") == "criterion_v2" and not judgment.get("criterion_assessments"):
                raise ValueError("Criterion-v2 report lacks requirement-level evidence")
            details[entry["provider"]] = {
                "gated_score": entry["gated_score"], "hard_fail": entry["hard_fail"],
                "stage_scores": judgment["stage_scores"],
                "revision_score": judgment["revision_score"],
                "critical_error_ids": [error["error_id"] for error in judgment["critical_errors"]],
                "criterion_assessments": judgment.get("criterion_assessments"),
                "unquoted_met_count": sum(
                    assessment["status"] == "met" and not assessment["response_evidence"].strip()
                    for assessment in judgment.get("criterion_assessments", [])
                ),
            }
        first, second = details["gemini"], details["grok"]
        differences = []
        if first["criterion_assessments"] is not None and second["criterion_assessments"] is not None:
            if len(first["criterion_assessments"]) != len(second["criterion_assessments"]):
                raise ValueError("Judge criterion counts differ")
            for a, b in zip(first["criterion_assessments"], second["criterion_assessments"]):
                key_a = (a["stage_id"], a["requirement_index"])
                key_b = (b["stage_id"], b["requirement_index"])
                if key_a != key_b:
                    raise ValueError("Judge criterion order differs")
                if a["status"] != b["status"]:
                    differences.append({"stage_id": key_a[0], "requirement_index": key_a[1],
                                        "gemini": a["status"], "grok": b["status"]})
        rows.append({
            "candidate_id": item["candidate_id"], "case_id": item["case_id"],
            "case_content_hash": item["case_content_hash"],
            "judges": details, "score_gap": abs(first["gated_score"] - second["gated_score"]),
            "criterion_disagreements": differences,
            "critical_error_disagreement": first["critical_error_ids"] != second["critical_error_ids"],
            "hard_fail_disagreement": first["hard_fail"] != second["hard_fail"],
        })
    if not rows:
        raise ValueError("Matrix report has no results")
    language_summary = {}
    for language, suffix in (("en", "-EN"), ("zh-Hans", "-ZH-HANS")):
        selected = [row for row in rows if row["case_id"].endswith(suffix)]
        if not selected:
            continue
        language_summary[language] = {
            "candidate_case_count": len(selected),
            "judges": {
                provider: {
                    "mean_gated_score": round(sum(row["judges"][provider]["gated_score"]
                                                   for row in selected) / len(selected), 2),
                    "full_score_count": sum(row["judges"][provider]["gated_score"] == 100
                                            for row in selected),
                    "hard_fail_count": sum(row["judges"][provider]["hard_fail"] for row in selected),
                    "unquoted_met_count": sum(row["judges"][provider]["unquoted_met_count"] for row in selected),
                    "criterion_status_counts": {
                        level: sum(assessment["status"] == level for row in selected
                                   for assessment in (row["judges"][provider]["criterion_assessments"] or []))
                        for level in ("met", "partial", "missed", "unclear")
                    },
                } for provider in ("gemini", "grok")
            },
        }
    by_variant = {(row["candidate_id"], row["case_id"]): row for row in rows}
    bilingual_pairs = []
    for row in rows:
        if row["case_id"].endswith("-EN"):
            partner_id = row["case_id"][:-3] + "-ZH-HANS"
            partner = by_variant.get((row["candidate_id"], partner_id))
            if partner is not None:
                bilingual_pairs.append({
                    "candidate_id": row["candidate_id"], "family_id": row["case_id"][:-3],
                    "score_delta_en_minus_zh": {
                        provider: round(row["judges"][provider]["gated_score"]
                                        - partner["judges"][provider]["gated_score"], 2)
                        for provider in ("gemini", "grok")
                    },
                })
    return {
        "status": "development_only_descriptive_judge_audit_not_ground_truth",
        "report_hashes": {key: report.get(key) for key in (
            "roster_sha256", "dataset_sha256", "candidate_instruction_sha256",
            "judge_instruction_sha256", "rubric_sha256", "criterion_anchors_sha256",
            "criterion_validator_version")},
        "candidate_case_count": len(rows),
        "full_score_counts": {provider: sum(row["judges"][provider]["gated_score"] == 100 for row in rows)
                              for provider in ("gemini", "grok")},
        "score_disagreement_count": sum(row["score_gap"] > 0 for row in rows),
        "criterion_disagreement_count": sum(len(row["criterion_disagreements"]) for row in rows),
        "hard_fail_disagreement_count": sum(row["hard_fail_disagreement"] for row in rows),
        "critical_error_disagreement_count": sum(row["critical_error_disagreement"] for row in rows),
        "language_summary": language_summary,
        "bilingual_pairs": bilingual_pairs,
        "cases": rows,
        "warning": "No human reference judgments: unsafe false-pass rate and clinical ranking cannot be inferred.",
    }


def assemble_matrix_artifacts(
    sources: list[str | Path], roster: dict[str, Any], dataset: dict[str, Any],
    rubric: dict[str, Any], anchors: dict[str, Any], *, candidate_id: str,
    case_ids: list[str], output_dir: str | Path,
    candidate_instruction: str, judge_instruction: str,
) -> dict[str, Any]:
    """Assemble a complete report from verified saved answers and judgments; no API calls."""
    target = Path(output_dir)
    if target.exists():
        raise FileExistsError("Assembled matrix output already exists")
    if not sources or not case_ids or len(case_ids) != len(set(case_ids)):
        raise ValueError("Assembly needs source directories and unique case IDs")
    validate_anchor_set(anchors, dataset)
    candidate = next((item for item in roster["candidates"] if item["id"] == candidate_id), None)
    if candidate is None or len(roster["judges"]) != 2 or {item["provider"] for item in roster["judges"]} != {"gemini", "grok"}:
        raise ValueError("Assembly candidate or judge roster is invalid")
    by_id = {variant_id(family, language): (family, language)
             for family, language in ordered_variants(dataset)}
    if any(case_id not in by_id for case_id in case_ids):
        raise ValueError("Assembly contains unknown case IDs")
    directories = [Path(path) for path in sources]
    for directory in directories:
        if not directory.is_dir():
            raise ValueError("Assembly source directory is absent")
        plan_path = directory / "plan.json"
        if plan_path.exists():
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            if (plan.get("roster_sha256") != sha256_json(roster)
                or plan.get("dataset_sha256") != sha256_json(dataset)
                or plan.get("candidates") != [candidate]
                or plan.get("judges") != roster["judges"]
                or plan.get("criterion_anchors_sha256") not in (None, sha256_json(anchors))
                or plan.get("judge_contract") not in (None, "criterion_v2")):
                raise ValueError("Assembly source plan has incompatible provenance")

    def find_one(filename: str) -> Path:
        matches = [directory / filename for directory in directories if (directory / filename).is_file()]
        if len(matches) != 1:
            raise ValueError(f"Assembly requires exactly one verified artifact: {filename}")
        return matches[0]

    staged = []
    judge_models: dict[str, set[str]] = {"gemini": set(), "grok": set()}
    candidate_models: set[str] = set()
    request_policies: set[str] = set()
    for case_id in case_ids:
        family, language = by_id[case_id]
        stem = f"{candidate_id}__{case_id}"
        answer_path = find_one(f"{stem}.answers.jsonl")
        manifest_path = find_one(f"{stem}.answers.manifest.json")
        if answer_path.parent != manifest_path.parent:
            raise ValueError("Assembly answer and manifest came from different runs")
        rows = [line for line in answer_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(rows) != 1:
            raise ValueError("Assembly answer must contain exactly one row")
        answer = json.loads(rows[0])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        revision = {"case_id": case_id, "case_version": family["version"],
                    "case_content_hash": variant_hash(family, language)}
        if (manifest.get("case_revisions") != [revision]
            or manifest.get("dataset_sha256") != sha256_json(dataset)
            or manifest.get("candidate_instruction_sha256") != sha256_text(candidate_instruction)
            or manifest.get("requested_model") != candidate["model"]
            or manifest.get("returned_model") != answer.get("model_version")
            or manifest.get("provider") != answer.get("provider")
            or answer.get("model_id") != candidate["model"]):
            raise ValueError("Assembly answer manifest has incompatible provenance")
        packet = attach_anchors(build_judge_packet(family, language, answer), anchors)
        candidate_models.add(answer["model_version"])
        request_policies.add(sha256_json(manifest["actual_request_parameters"]))
        judges = []
        judge_files = []
        for spec in roster["judges"]:
            path = find_one(f"{stem}__{spec['id']}.judgment.json")
            record = json.loads(path.read_text(encoding="utf-8"))
            if (record.get("case_id") != case_id
                or record.get("case_content_hash") != revision["case_content_hash"]
                or record.get("candidate_id") != candidate_id
                or record.get("judge_id") != spec["id"]
                or record.get("judge_provider") != spec["provider"]
                or record.get("judge_model_requested") != spec["model"]
                or not isinstance(record.get("judge_model_returned"), str)
                or not record["judge_model_returned"]
                or record.get("same_vendor_as_candidate") != (spec["provider"] == candidate["provider"])
                or record.get("same_model_as_candidate") != (spec["provider"] == candidate["provider"] and spec["model"] == candidate["model"])
                or record.get("judge_instruction_sha256") != sha256_text(judge_instruction)
                or record.get("rubric_sha256") != sha256_json(rubric)
                or record.get("judge_contract") != "criterion_v2"
                or record.get("criterion_anchors_sha256") != sha256_json(anchors)):
                raise ValueError("Assembly judge record has incompatible provenance")
            score = score_judgment(record["judgment"], packet, rubric)
            if score != record.get("score"):
                raise ValueError("Assembly judge score does not recompute")
            judge_models[spec["provider"]].add(record["judge_model_returned"])
            judges.append({
                "judge_id": spec["id"], "provider": spec["provider"],
                "model_requested": spec["model"], "model_returned": record["judge_model_returned"],
                "same_vendor_as_candidate": spec["provider"] == candidate["provider"],
                "same_model_as_candidate": spec["provider"] == candidate["provider"] and spec["model"] == candidate["model"],
                "gated_score": score["gated_score"], "hard_fail": score["hard_fail"],
                "review_required": True, "judgment_file": path.name,
            })
            judge_files.append(path)
        staged.append((answer_path, manifest_path, judge_files, {
            "candidate_id": candidate_id, "candidate_provider": candidate["provider"],
            "candidate_model_requested": candidate["model"],
            "candidate_model_returned": answer["model_version"],
            "candidate_request_parameters": manifest["actual_request_parameters"],
            "case_id": case_id, "case_content_hash": revision["case_content_hash"],
            "answer_file": answer_path.name, "judges": judges,
            "judge_score_gap": abs(judges[0]["gated_score"] - judges[1]["gated_score"]),
        }))
    if len(candidate_models) != 1 or len(request_policies) != 1 or any(len(models) != 1 for models in judge_models.values()):
        raise ValueError("Assembly found inconsistent candidate or judge model/protocol identities")
    target.mkdir(parents=True)
    for answer_path, manifest_path, judge_files, _item in staged:
        for path in (answer_path, manifest_path, *judge_files):
            shutil.copyfile(path, target / path.name)
    report = {
        "status": "experimental_unvalidated_two_ai_judges_not_clinical_ranking",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recovery_mode": "offline_assembled_from_verified_artifacts",
        "roster_sha256": sha256_json(roster), "dataset_sha256": sha256_json(dataset),
        "candidate_instruction_sha256": sha256_text(candidate_instruction),
        "judge_instruction_sha256": sha256_text(judge_instruction),
        "rubric_sha256": sha256_json(rubric), "judge_contract": "criterion_v2",
        "criterion_anchors_sha256": sha256_json(anchors),
        "criterion_validator_version": CRITERION_VALIDATOR_VERSION,
        "actual_api_calls": None, "logical_calls_included": len(staged) * 4,
        "results": [item for *_paths, item in staged],
        "limitations": ["offline assembly cannot establish total billed attempts across failed runs",
                        "draft public cases and uncalibrated AI judges", "provider sampling/model alias limits"],
    }
    _write_json_new(target / "report.json", report)
    return {"output_dir": str(target), "report": str(target / "report.json"),
            "candidate_case_count": len(staged), "api_calls": 0, "status": report["status"]}
