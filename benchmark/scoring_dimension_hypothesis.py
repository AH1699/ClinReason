"""Read-only S15 comparison of saved scoring dimensions and a fresh frozen probe."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .config import load_json
from .frozen_batch_g import load_batch_g_dataset
from .criterion_score_coherence import _normalize, _verify_directory_report, audit_cohort
from .multiturn import merge_multiturn_datasets, variant_hash, variant_id
from .provenance import sha256_json, sha256_text
from .scoring_probe_run import audit_saved, load_inputs


POLICY_PATH = "config/scoring_dimension_hypotheses_s15_v1.json"
OLD_POLICY_PATH = "config/criterion_score_coherence_v1.json"
S15_STATUS = "offline_dimension_hypothesis_diagnostic_not_rescoring_or_clinical_validation"


def validate_fresh_probe(root: Path, dataset: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Freeze an existing family's controlled EN/ZH answer edits without judging them."""
    probe = load_json(root / policy["fresh_probe_path"])
    if (probe.get("status") != "frozen_author_probe_not_clinical_truth_no_live_calls"
        or probe.get("family_id") != "HC-MT-REASON-015"
        or probe.get("target_requirement_index") != 3
        or len(probe.get("languages", [])) != 2):
        raise ValueError("Unknown S15 fresh probe")
    family = next((item for item in dataset["families"]
                   if item["family_id"] == probe["family_id"]), None)
    if family is None or probe["source_refs"] != family["source_refs"]:
        raise ValueError("S15 fresh source or family mismatch")
    contrasts = load_json(root / "data/multiturn/batch_g_contrasts_v1.json")["probes"]
    by_language = {(item["family_id"], item["language"]): item for item in contrasts}
    manifest = []
    for item in probe["languages"]:
        language = item["language"]
        if language not in ("en", "zh-Hans") or item["case_content_hash"] != variant_hash(family, language):
            raise ValueError("S15 fresh case hash mismatch")
        segments = item["base_update_segments"]
        if len(segments) != 3 or any(not isinstance(part, str) or not part for part in segments):
            raise ValueError("S15 fresh segments must be three nonempty strings")
        separator = item["separator"]
        if separator not in ("", " "):
            raise ValueError("S15 fresh separator changed")
        source = by_language[(probe["family_id"], language)]
        baseline = separator.join(segments)
        omission = separator.join(segments[:2])
        if (item["initial_response"] != source["initial_response"]
            or baseline != source["safe_update_response"]
            or omission == baseline or segments[2] in omission):
            raise ValueError("S15 fresh probe is not a one-segment edit of the frozen safe answer")
        case_id = variant_id(family, language)
        manifest.append({
            "case_id": case_id, "case_content_hash": item["case_content_hash"],
            "initial_response_sha256": sha256_text(item["initial_response"]),
            "baseline_update_sha256": sha256_text(baseline),
            "omission_update_sha256": sha256_text(omission),
            "omitted_segment_sha256": sha256_text(segments[2]),
            "planned_judge_calls": 0,
        })
    if {row["case_id"] for row in manifest} != {
        variant_id(family, "en"), variant_id(family, "zh-Hans")
    }:
        raise ValueError("S15 fresh bilingual pair incomplete")
    return {"probe_sha256": sha256_json(probe), "manifest": manifest,
            "author_hypotheses_not_gold": probe["author_hypotheses_not_gold"]}


def compare_pairs(rows: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    """Contrast saved ratings, not hypothetical new scores or correctness."""
    if {row["family_id"] for row in rows} != {spec["family_id"]}:
        raise ValueError("Unexpected family in S15 cohort")
    identity: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["case_id"], row["judge_id"], row["answer_id"])
        if key in identity:
            raise ValueError("Duplicate S15 saved judgment")
        identity[key] = row
    pairs = []
    for case_id in sorted({row["case_id"] for row in rows}):
        for judge_id in sorted({row["judge_id"] for row in rows}):
            baseline = identity.get((case_id, judge_id, spec["baseline_variant"]))
            target = identity.get((case_id, judge_id, spec["target_variant"]))
            if baseline is None or target is None:
                raise ValueError("Missing S15 baseline or edited answer")
            index = spec["update_safety_net_requirement_index"] - 1
            if (baseline["statuses"]["initial"] != target["statuses"]["initial"]
                or baseline["statuses"]["update"][index] != "met"
                or target["statuses"]["update"][index] == "met"
                or baseline["errors"] or target["errors"]):
                raise ValueError("S15 contrast is not the predeclared no-error safety-net comparison")
            delta = {
                "requirements": round(target["stages"]["update"]["requirements"] - baseline["stages"]["update"]["requirements"], 2),
                "safety": round(target["stages"]["update"]["safety"] - baseline["stages"]["update"]["safety"], 2),
                "revision": round(target["revision"] - baseline["revision"], 2),
                "gated_score": round(target["gated"] - baseline["gated"], 2),
            }
            lowered = [name for name in ("requirements", "safety", "revision") if delta[name] < 0]
            pairs.append({
                "case_id": case_id, "judge_id": judge_id,
                "baseline_update_statuses": list(baseline["statuses"]["update"]),
                "edited_update_statuses": list(target["statuses"]["update"]),
                "dimension_delta_from_baseline": delta,
                "dimensions_lowered": lowered,
                "baseline_gated_score": baseline["gated"], "edited_gated_score": target["gated"],
                "baseline_pass": baseline["pass"], "edited_pass": target["pass"],
                "saved_files": [baseline["file"], target["file"]],
            })
    if len(pairs) != 4 or {row["case_id"] for row in pairs} != {
        spec["family_id"] + "-EN", spec["family_id"] + "-ZH-HANS"
    }:
        raise ValueError("S15 cohort requires both languages and both judges")
    return {
        "cohort": spec["id"], "isolation": spec["isolation"],
        "judgment_count": len(rows), "pair_count": len(pairs),
        "observed_lowered_patterns": dict(sorted(Counter("+".join(row["dimensions_lowered"]) or "none" for row in pairs).items())),
        "pairs": pairs,
        "interpretation_limit": "Mixed edits cannot isolate a safety-net effect; even a single edit cannot establish clinically correct dimension scores."
        if spec["isolation"].startswith("mixed_") else
        "A single authored edit isolates wording, not clinical severity or independent evidence for overlapping deductions.",
    }


def audit(root: Path, work_root: Path) -> dict[str, Any]:
    policy = load_json(root / POLICY_PATH)
    if (policy.get("version") != "s15-v1-offline-hypotheses"
        or policy.get("status") != "review_hypotheses_only_not_a_scoring_contract"
        or [item["id"] for item in policy.get("cohorts", [])] !=
        ["s9_triage_018", "s11_triage_019", "s14_triage_020"]):
        raise ValueError("Unknown S15 policy")
    dataset = load_batch_g_dataset(root)
    rubric = load_json(root / "config/multiturn_rubric.json")
    old_policy = load_json(root / OLD_POLICY_PATH)
    if old_policy["pass_threshold"] != rubric["pass_threshold"]:
        raise ValueError("S15 comparison threshold differs from bound rubric")
    expected = {
        "case_hashes": {variant_id(family, language): variant_hash(family, language)
                        for family in dataset["families"] for language in ("en", "zh-Hans")},
        "rubric_sha256": sha256_json(rubric), "rubric": rubric,
        "judge_instruction_sha256": sha256_text((root / "config/multiturn_judge_prompt_v2.txt").read_text(encoding="utf-8").strip()),
        "anchor_hashes": {sha256_json(load_json(root / "config/multiturn_criterion_anchors_batch_g_v1.json"))},
    }
    cohorts = []
    for spec in policy["cohorts"]:
        paths = []
        for name in spec["directories"]:
            directory = work_root / name
            found = sorted(directory.glob("*.judgment.json"))
            if not found:
                raise ValueError(f"Missing saved S15 judgment cohort: {name}")
            if spec["id"] == "s14_triage_020":
                audit_saved(load_inputs(root), directory)
            else:
                _verify_directory_report(directory, found)
            paths.extend(found)
        audit_cohort(spec["id"], paths, old_policy, expected)
        rows = [_normalize(path, load_json(path), rubric["pass_threshold"]) for path in paths]
        cohorts.append(compare_pairs(rows, spec))
    return {
        "status": S15_STATUS, "policy_sha256": sha256_json(policy),
        "fresh_probe": validate_fresh_probe(root, dataset, policy),
        "cohorts": cohorts, "saved_judgments_checked": sum(row["judgment_count"] for row in cohorts),
        "paired_safety_net_comparisons": sum(row["pair_count"] for row in cohorts),
        "candidate_calls": 0, "judge_calls": 0,
        "limits": policy["limits"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit saved S9/S11/S14 dimension ratings; no model calls")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = audit(args.root, args.work_root or args.root / "work")
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError("Refusing to overwrite S15 report")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
