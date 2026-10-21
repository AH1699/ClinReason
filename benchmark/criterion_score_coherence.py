"""Read-only, versioned coherence flags for saved multi-turn judge exports."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .config import load_json
from .multiturn import merge_multiturn_datasets, variant_hash, variant_id
from .provenance import sha256_json, sha256_text


def _number(value: Any, label: str, maximum: float = 100) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"Invalid {label}")
    return float(value)


def _language(case_id: str) -> tuple[str, str]:
    for suffix, language in (("-ZH-HANS", "zh-Hans"), ("-EN", "en")):
        if case_id.endswith(suffix):
            return case_id[:-len(suffix)], language
    raise ValueError(f"Unsupported case language: {case_id}")


def _normalize(path: Path, row: dict[str, Any], threshold: float) -> dict[str, Any]:
    judgment, score = row.get("judgment"), row.get("score")
    if not isinstance(judgment, dict) or not isinstance(score, dict):
        raise ValueError(f"Missing saved judgment/score: {path}")
    case_id, case_hash, judge_id = (row.get(key) for key in ("case_id", "case_content_hash", "judge_id"))
    if not all(isinstance(value, str) and value for value in (case_id, case_hash, judge_id)):
        raise ValueError(f"Missing case or judge identity: {path}")
    family, language = _language(case_id)
    if score.get("case_id") != case_id or score.get("case_content_hash") != case_hash:
        raise ValueError(f"Score has wrong case binding: {path}")
    candidate = row.get("candidate_id")
    variant = row.get("variant")
    if (candidate is None) == (variant is None) or not isinstance(candidate or variant, str):
        raise ValueError(f"Missing or ambiguous answer identity: {path}")
    answer_id = candidate if candidate is not None else variant
    if not all(isinstance(row.get(key), str) and row[key] for key in
               ("rubric_sha256", "criterion_anchors_sha256", "judge_instruction_sha256")):
        raise ValueError(f"Missing protocol hash: {path}")
    scores = judgment.get("stage_scores")
    assessments = judgment.get("criterion_assessments")
    if not isinstance(scores, list) or len(scores) != 2 or not isinstance(assessments, list) or not assessments:
        raise ValueError(f"Incomplete criterion or stage scores: {path}")
    stages: dict[str, dict[str, float]] = {}
    statuses: dict[str, dict[int, str]] = defaultdict(dict)
    for stage in scores:
        if not isinstance(stage, dict) or stage.get("stage_id") not in ("initial", "update"):
            raise ValueError(f"Invalid stage: {path}")
        stage_id = stage["stage_id"]
        if stage_id in stages:
            raise ValueError(f"Duplicate stage: {path}")
        stages[stage_id] = {key: _number(stage.get(key), key, 4) for key in ("safety", "requirements")}
    if set(stages) != {"initial", "update"}:
        raise ValueError(f"Missing stage: {path}")
    for assessment in assessments:
        if not isinstance(assessment, dict):
            raise ValueError(f"Malformed criterion: {path}")
        stage_id, index, status = (assessment.get(key) for key in ("stage_id", "requirement_index", "status"))
        if stage_id not in stages or type(index) is not int or index < 1 or status not in {"met", "partial", "missed", "unclear"} or index in statuses[stage_id]:
            raise ValueError(f"Invalid criterion identity/status: {path}")
        statuses[stage_id][index] = status
    if set(statuses) != set(stages) or any(sorted(values) != list(range(1, len(values) + 1)) for values in statuses.values()):
        raise ValueError(f"Incomplete criterion vector: {path}")
    errors = judgment.get("critical_errors")
    if not isinstance(errors, list) or score.get("critical_errors") != errors:
        raise ValueError(f"Critical errors differ from saved score: {path}")
    for error in errors:
        if not isinstance(error, dict) or error.get("stage_id") not in stages or type(error.get("severity")) is not int or error["severity"] not in (1, 2, 3):
            raise ValueError(f"Malformed critical error: {path}")
    raw = _number(score.get("raw_score"), "raw score")
    gated = _number(score.get("gated_score"), "gated score")
    if type(score.get("pass")) is not bool or type(score.get("hard_fail")) is not bool:
        raise ValueError(f"Malformed saved pass status: {path}")
    if score["pass"] != (not score["hard_fail"] and gated >= threshold):
        raise ValueError(f"Saved pass flag conflicts with threshold: {path}")
    revision = _number(judgment.get("revision_score"), "revision", 4)
    return {
        "file": str(path), "case_id": case_id, "case_content_hash": case_hash,
        "family_id": family, "language": language, "judge_id": judge_id,
        "answer_id": answer_id, "answer_kind": "candidate" if candidate is not None else "authored_variant",
        "rubric_sha256": row["rubric_sha256"],
        "criterion_anchors_sha256": row["criterion_anchors_sha256"],
        "judge_instruction_sha256": row["judge_instruction_sha256"],
        "stages": stages, "statuses": {key: tuple(value[i] for i in sorted(value)) for key, value in statuses.items()},
        "revision": revision, "errors": errors, "raw": raw, "gated": gated, "pass": score["pass"],
    }


def _verify_directory_report(directory: Path, paths: list[Path]) -> None:
    """Bind selected raw exports to the already-saved panel/contrast manifest."""
    report = load_json(directory / "report.json")
    selected = {path.name: load_json(path) for path in paths}
    listed: set[str] = set()
    if report.get("status") == "experimental_unvalidated_two_ai_judges_not_clinical_ranking":
        for result in report["results"]:
            if not isinstance(result.get("answer_file"), str) or not (directory / result["answer_file"]).is_file():
                raise ValueError("Saved panel answer file is missing")
            if len(result.get("judges", [])) != 2:
                raise ValueError("Saved panel has incomplete judge pair")
            for judge in result["judges"]:
                filename = judge["judgment_file"]
                if filename in listed or filename not in selected:
                    raise ValueError("Saved panel judge file list differs from exports")
                listed.add(filename)
                row = selected[filename]
                if (row.get("candidate_id") != result["candidate_id"]
                    or row.get("case_id") != result["case_id"]
                    or row.get("case_content_hash") != result["case_content_hash"]
                    or row.get("judge_id") != judge["judge_id"]
                    or row["score"]["gated_score"] != judge["gated_score"]):
                    raise ValueError("Saved panel judge export conflicts with report")
    elif report.get("status") == "synthetic_contrast_two_ai_judges_not_clinical_validation":
        if report.get("candidate_calls") != 0 or report.get("judge_calls") != 6:
            raise ValueError("Saved contrast call count differs from expected protocol")
        for provider, result in report["results"].items():
            for variant, summary in result["variants"].items():
                filename = f"{provider}-judge__{variant}.judgment.json"
                if filename in listed or filename not in selected:
                    raise ValueError("Saved contrast judge file list differs from exports")
                listed.add(filename)
                row = selected[filename]
                if (row.get("case_id") != report["case_id"]
                    or row.get("case_content_hash") != report["case_content_hash"]
                    or row.get("probe_sha256") != report["probe_sha256"]
                    or row.get("variant") != variant
                    or row.get("judge_provider") != provider
                    or row["score"]["gated_score"] != summary["gated_score"]
                    or row["score"]["pass"] != summary["pass"]
                    or [item["status"] for item in row["judgment"]["criterion_assessments"]]
                       != summary["criterion_statuses"]):
                    raise ValueError("Saved contrast judge export conflicts with report")
    else:
        raise ValueError("Unsupported saved report status")
    if listed != set(selected) or any(
        any(row.get(key) != report.get(key) for key in
            ("rubric_sha256", "criterion_anchors_sha256", "judge_instruction_sha256"))
        for row in selected.values()
    ):
        raise ValueError("Saved report protocol or file set differs from exports")


def audit_cohort(name: str, paths: list[Path], policy: dict[str, Any],
                 expected: dict[str, Any] | None = None) -> dict[str, Any]:
    """Audit an explicit, non-overlapping cohort; never write to saved artifacts."""
    if policy.get("version") != "1.0.0-diagnostic" or policy.get("status") != "offline_review_flags_only_not_score_contract":
        raise ValueError("Unknown coherence policy")
    gap = _number(policy.get("score_gap_points"), "gap threshold")
    threshold = _number(policy.get("pass_threshold"), "pass threshold")
    if gap == 0:
        raise ValueError("Diagnostic gap threshold must be positive")
    if not name or not paths or len(set(paths)) != len(paths):
        raise ValueError("Provide named, distinct saved-judgment paths")
    rows = [_normalize(path, load_json(path), threshold) for path in paths]
    if expected is not None:
        if any(row["case_content_hash"] != expected["case_hashes"].get(row["case_id"])
               or row["rubric_sha256"] != expected["rubric_sha256"]
               or row["judge_instruction_sha256"] != expected["judge_instruction_sha256"]
               or row["criterion_anchors_sha256"] not in expected["anchor_hashes"]
               for row in rows):
            raise ValueError("Saved judgment does not match known case or protocol files")
        rubric = expected["rubric"]
        for row in rows:
            stage_points = {
                stage: round((values["safety"] * rubric["stage_component_weights"]["safety"]
                              + values["requirements"] * rubric["stage_component_weights"]["requirements"])
                             / rubric["scale_max"] * 100, 2)
                for stage, values in row["stages"].items()
            }
            revision_points = round(row["revision"] / rubric["scale_max"] * 100, 2)
            raw = round(sum(stage_points[stage] * rubric["conversation_weights"][stage]
                            for stage in ("initial", "update"))
                        + revision_points * rubric["conversation_weights"]["revision"], 2)
            deductions = sum(rubric["critical_error_rules"][str(error["severity"])].get("deduction", 0)
                             for error in row["errors"])
            caps = [rubric["critical_error_rules"][str(error["severity"])]["cap"]
                    for error in row["errors"]
                    if "cap" in rubric["critical_error_rules"][str(error["severity"])]]
            gated = max(0, round(min([raw - deductions, *caps]) if caps else raw - deductions, 2))
            hard_fail = any(rubric["critical_error_rules"][str(error["severity"])].get("hard_fail", False)
                            for error in row["errors"])
            saved = load_json(Path(row["file"]))["score"]
            if (abs(row["raw"] - raw) > 0.01 or abs(row["gated"] - gated) > 0.01
                or saved.get("stage_scores") != stage_points
                or saved.get("revision_score") != revision_points
                or saved["hard_fail"] != hard_fail):
                raise ValueError("Saved numeric score does not match bound rubric")
    protocol = tuple(rows[0][key] for key in ("rubric_sha256", "criterion_anchors_sha256", "judge_instruction_sha256"))
    if any(tuple(row[key] for key in ("rubric_sha256", "criterion_anchors_sha256", "judge_instruction_sha256")) != protocol for row in rows):
        raise ValueError("Mixed rubric, anchors or judge instruction in cohort")
    unique = set()
    for row in rows:
        identity = (row["answer_kind"], row["answer_id"], row["case_id"], row["judge_id"])
        if identity in unique:
            raise ValueError("Duplicate answer/case/judge entry")
        unique.add(identity)
    flags: list[dict[str, Any]] = []
    def flag(kind: str, left: dict[str, Any], right: dict[str, Any] | None = None, **details: Any) -> None:
        flags.append({"rule": kind, "answer_id": left["answer_id"], "case_id": left["case_id"],
                      "judge_id": left["judge_id"], "other_case_id": right["case_id"] if right else None,
                      "other_judge_id": right["judge_id"] if right else None,
                      "files": [left["file"]] + ([right["file"]] if right else []), **details})
    for row in rows:
        for stage, statuses in row["statuses"].items():
            requirement_score = row["stages"][stage]["requirements"]
            if all(status == "met" for status in statuses) and requirement_score < 4:
                flag("all_met_requirements_below_full", row, stage=stage, requirements=requirement_score)
            if "missed" in statuses and requirement_score >= 3:
                flag("missed_criterion_high_requirements", row, stage=stage, requirements=requirement_score)
        safety_net = policy.get("safety_net_review_map", {}).get(row["family_id"])
        if safety_net:
            stage = safety_net["stage"]
            index = safety_net["requirement_index"] - 1
            if (len(row["statuses"].get(stage, ())) > index
                and row["statuses"][stage][index] != "met"
                and row["stages"][stage]["safety"] < 4 and row["revision"] < 4):
                flag("safety_net_overlap_review", row, stage=stage,
                     criterion_status=row["statuses"][stage][index],
                     safety=row["stages"][stage]["safety"], revision=row["revision"])
        if any(error["severity"] == 1 for error in row["errors"]):
            if row["raw"] >= threshold:
                flag("severity1_threshold_dependence", row, raw_score=row["raw"], gated_score=row["gated"])
            if row["pass"]:
                flag("severity1_draft_pass", row, gated_score=row["gated"])
    by_answer: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    by_family: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_answer[(row["answer_kind"], row["answer_id"], row["case_id"])].append(row)
        by_family[(row["answer_kind"], row["answer_id"], row["judge_id"], row["family_id"])].append(row)
    comparisons = Counter()
    def compare(left: dict[str, Any], right: dict[str, Any], comparison: str) -> None:
        if left["case_content_hash"] != right["case_content_hash"] and comparison == "same_case_two_judges":
            raise ValueError("Judge pair has different case revisions")
        if left["statuses"] != right["statuses"]:
            return
        comparisons[comparison] += 1
        dimension_gaps = {
            f"{stage}_{dimension}": abs(left["stages"][stage][dimension] - right["stages"][stage][dimension]) * 25
            for stage in ("initial", "update") for dimension in ("safety", "requirements")
        }
        dimension_gaps["revision"] = abs(left["revision"] - right["revision"]) * 25
        dimension_gaps["gated_total"] = abs(left["gated"] - right["gated"])
        large = {key: value for key, value in dimension_gaps.items() if value >= gap}
        if large:
            flag("same_status_numeric_gap", left, right, comparison=comparison, gaps=large)
        if left["pass"] != right["pass"]:
            flag("same_status_pass_split", left, right, comparison=comparison,
                 left_pass=left["pass"], right_pass=right["pass"])
    for pair in by_answer.values():
        if len(pair) > 2:
            raise ValueError("Expected at most two judges per exact answer")
        if len(pair) == 2:
            compare(*sorted(pair, key=lambda row: row["judge_id"]), "same_case_two_judges")
    for pair in by_family.values():
        if len(pair) > 2:
            raise ValueError("Expected at most one EN/ZH pair per judge and answer")
        if len(pair) == 2:
            if {row["language"] for row in pair} != {"en", "zh-Hans"}:
                raise ValueError("Invalid EN/ZH pair")
            compare(*sorted(pair, key=lambda row: row["language"]), "authored_or_candidate_en_zh_counterpart")
    return {
        "status": "offline_diagnostic_not_rescoring_or_clinical_validation", "cohort": name,
        "policy_version": policy["version"], "judgment_count": len(rows),
        "protocol_hashes": dict(zip(("rubric_sha256", "criterion_anchors_sha256", "judge_instruction_sha256"), protocol)),
        "input_sha256": {str(path): sha256_json(load_json(path)) for path in paths},
        "same_status_comparisons": dict(comparisons),
        "flag_counts": dict(sorted(Counter(item["rule"] for item in flags).items())),
        "flags": flags,
        "limits": "An EN/ZH counterpart is not proven semantically equivalent. Same statuses do not imply identical holistic safety or revision. Flags need adjudication; historical scores are unchanged.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit saved criterion-to-score coherence without model calls")
    parser.add_argument("--group", action="append", required=True, metavar="NAME=DIR[,DIR]")
    parser.add_argument("--policy", type=Path, default=Path(__file__).resolve().parents[1] / "config/criterion_score_coherence_v1.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    policy = load_json(args.policy)
    root = Path(__file__).resolve().parents[1]
    config = load_json(root / "config/benchmark.json")
    dataset = merge_multiturn_datasets([load_json(root / path) for path in config["multiturn_cases_paths"]])
    rubric = load_json(root / "config/multiturn_rubric.json")
    if rubric["pass_threshold"] != policy["pass_threshold"]:
        raise ValueError("Diagnostic pass threshold differs from current rubric")
    expected = {
        "case_hashes": {variant_id(family, language): variant_hash(family, language)
                        for family in dataset["families"] for language in ("en", "zh-Hans")},
        "rubric_sha256": sha256_json(rubric),
        "rubric": rubric,
        "judge_instruction_sha256": sha256_text((root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip()),
        "anchor_hashes": {sha256_json(load_json(root / f"config/multiturn_criterion_anchors_{batch}_v1.json"))
                          for batch in ("batch_f", "batch_g")},
    }
    cohorts = []
    seen_paths: set[Path] = set()
    for group in args.group:
        if "=" not in group:
            parser.error("--group must be NAME=DIR[,DIR]")
        name, directories = group.split("=", 1)
        path_groups = [(Path(directory), sorted(Path(directory).glob("*.judgment.json")))
                       for directory in directories.split(",")]
        paths = sorted(path for _, found in path_groups for path in found)
        if not paths or seen_paths.intersection(paths):
            raise ValueError("Empty or overlapping judgment group")
        for directory, found in path_groups:
            if not found:
                raise ValueError(f"No saved judgments in {directory}")
            _verify_directory_report(directory, found)
        seen_paths.update(paths)
        cohorts.append(audit_cohort(name, paths, policy, expected))
    result = {"status": "offline_diagnostic_not_rescoring_or_clinical_validation",
              "policy_version": policy["version"], "policy_sha256": sha256_json(policy), "cohorts": cohorts}
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError("Refusing to overwrite a diagnostic report")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
