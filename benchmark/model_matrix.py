"""Bounded, development-only multi-model/two-judge conversation diagnostic."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_settings import read_setting
from .multiturn import (build_judge_packet, ordered_variants, variant_hash,
                        variant_id, write_batch)
from .multiturn_judging import GeminiMultiturnJudge, score_judgment
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
) -> dict[str, Any]:
    if type(max_api_calls) is not int or max_api_calls < plan["total_api_calls"]:
        raise ValueError(f"--max-api-calls must be at least {plan['total_api_calls']} for this selection")
    if timeout <= 0 or retries != 0:
        raise ValueError("Model-matrix timeout must be positive and automatic retries are disabled")
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
            packet = build_judge_packet(family, language, answer)
            item: dict[str, Any] = {
                "candidate_id": spec["id"], "candidate_provider": spec["provider"],
                "candidate_model_requested": spec["model"],
                "candidate_model_returned": candidate.model_version,
                "case_id": case_id, "case_content_hash": packet["case_content_hash"],
                "answer_file": answer_path.name, "judges": [],
            }
            for judge_spec in judges:
                judge = judge_instances[judge_spec["id"]]
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


def compare_matrix_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Align completed matrix reports without treating their scores as ground truth."""
    if len(reports) < 2:
        raise ValueError("Compare at least two completed model-matrix reports")
    required = ("roster_sha256", "dataset_sha256", "candidate_instruction_sha256",
                "judge_instruction_sha256", "rubric_sha256")
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
