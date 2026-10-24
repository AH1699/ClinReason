"""Offline proposal checks, cost scenarios and fixed-denominator reporting."""

from collections import Counter
import itertools
import json
import math
from pathlib import Path
from statistics import pstdev

from .config import load_json
from .portfolio_audit import _leakage_groups
from .provenance import sha256_json

PLAN = "config/reference_mix_s36_proposal_v1.json"


def budget(plan):
    n, f, c, langs, judges = (len(plan[k]) for k in ("candidates", "development", "confirmation", "languages", "judges"))
    control = len(plan["stress_families"]) * langs * judges * 6
    repeat = len(plan["development_repeat_families"]) * langs * n * judges * 2
    expected = {"control_calls": control, "development_candidate_calls": n*f*langs*2,
                "development_judge_calls": n*f*langs*judges*2, "development_repeat_judge_calls": repeat,
                "optional_single_post_revision_control_calls": control,
                "confirmation_candidate_calls": n*c*langs*2, "confirmation_judge_calls": n*c*langs*judges*2}
    expected["maximum_attempts"] = sum(expected.values())
    expected["first_phase_attempts"] = control + n*f*langs*(2+judges*2) + repeat
    expected["confirmation_phase_max_attempts"] = control + n*c*langs*(2+judges*2)
    if any(plan["budget"][k] != value for k, value in expected.items()):
        raise ValueError("Call budget differs from fixed design")
    def cost(specs, count_each, inp, out):
        return count_each * sum(inp*s["input_per_million"] + out*s["output_per_million"] for s in specs) / 1_000_000
    def estimate(which, ceiling=False):
        b = plan["budget"]
        if ceiling:
            ci = ji = b["planning_token_ceiling"]["input_per_request"]
            co = jo = b["planning_token_ceiling"]["output_including_reasoning_per_request"]
        else:
            t = b["expected_tokens"]
            ci, co, ji, jo = [t[k] for k in ("candidate_input", "candidate_output_including_reasoning", "judge_input", "judge_output_including_reasoning")]
        families = f if which == "first" else c
        extra = control + (repeat if which == "first" else 0)
        return round(cost(plan["candidates"], families*langs*2, ci, co)
            + cost(plan["judges"], (families*langs*n*judges*2+extra)/judges, ji, jo), 4)
    first, last = estimate("first"), estimate("confirmation")
    cap_first, cap_last = estimate("first", True), estimate("confirmation", True)
    return {**expected, "expected_scenario_usd": round(first+last, 4),
            "expected_first_phase_usd": first, "expected_confirmation_phase_usd": last,
            "token_ceiling_scenario_usd": round(cap_first+cap_last, 4),
            "ceiling_first_phase_usd": cap_first, "ceiling_confirmation_phase_usd": cap_last,
            "estimate_not_runtime_spend_enforcement": True}


def check_plan(root, plan):
    if plan["live_call_allowance"] != 0 or plan["status"] != "offline_proposal_not_frozen_or_authorized":
        raise ValueError("Offline proposal cannot authorize calls")
    matrix = load_json(root / "config/model_matrix.json")
    available = {(s["provider"], s["model"]) for s in matrix["candidates"]}
    roster = [(s["provider"], s["model"]) for s in plan["candidates"]]
    if len(roster) != 6 or len(set(roster)) != 6 or not set(roster) <= available:
        raise ValueError("Roster must use six distinct configured IDs")
    if Counter(p for p, _ in roster) != {"gemini": 2, "grok": 2, "minimax": 2}:
        raise ValueError("Expected two models per provider")
    if plan["languages"] != ["en", "zh-Hans"]:
        raise ValueError("Balanced paired languages required")
    dev = [r["family_id"] for r in plan["development"]]
    confirmation = [r["family_id"] for r in plan["confirmation"] if r["family_id"]]
    if len(dev) != len(set(dev)) or len(confirmation) != len(set(confirmation)) or set(dev) & set(confirmation):
        raise ValueError("Duplicate or overlapping family split")
    if plan["held"]["family_id"] in dev + confirmation:
        raise ValueError("Held red-eye family must not enter mean")
    for rows, count in ((plan["development"], 3), (plan["confirmation"], 2)):
        if Counter(r["design_stratum"] for r in rows) != {"routine": count, "conditional": count, "conflicting": count}:
            raise ValueError("Difficulty mix drift")
    families = {}
    for path in (root / "data/multiturn").glob("*cases.json"):
        families.update({f["family_id"]: f for f in load_json(path)["families"]})
    dev_sources = {s for fid in dev for s in families[fid]["source_refs"]}
    if any(dev_sources & set(families[fid]["source_refs"]) for fid in confirmation):
        raise ValueError("Shared source across split")
    groups = _leakage_groups(load_json(root / "data/audit/overlap_and_source_review.json"))
    if any(set(g) & set(dev) and set(g) & set(confirmation) for g in groups):
        raise ValueError("Declared mechanism leakage across split")
    budgets = budget(plan)
    return {"version": plan["version"], "plan_sha256": sha256_json(plan), "candidate_models": len(roster),
            "development_families": len(dev), "confirmation_existing_reservations": len(confirmation),
            "confirmation_unbuilt_slots": len(plan["confirmation"])-len(confirmation),
            "existing_split_source_and_declared_mechanism_check": "pass",
            "live_ready": False, "live_call_allowance": 0, "budget_scenarios": budgets}


def summarize(records, models, families, languages=("en", "zh-Hans")):
    """One judge and score version only. Unknown/missing cells cannot disappear.

    Each record is an accepted conversation score, never a failed provider reply.
    A caller supplies only first-pass records, with repeats reported separately.
    """
    for values in (models, families, languages):
        if not values or len(values) != len(set(values)):
            raise ValueError("Unique nonempty design dimensions required")
    expected = set(itertools.product(models, families, languages))
    cells, judges, versions = {}, set(), set()
    for row in records:
        key = row["model"], row["family_id"], row["language"]
        if key not in expected or key in cells:
            raise ValueError("Unknown or duplicate panel cell")
        low, high = row["criterion_score_interval"]
        point = row["point_score"]
        if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (low, high))
                or not 0 <= low <= high <= 100 or type(row["hard_fail"]) is not bool
                or (point is not None and (type(point) not in (int, float) or not math.isfinite(point)
                    or not low == high == point))):
            raise ValueError("Invalid derived score record")
        judges.add(row["judge"]); versions.add(row["score_version"]); cells[key] = row
    if len(judges) > 1 or len(versions) > 1:
        raise ValueError("Do not pool judges or score versions")
    def aggregate(keys):
        rows = [cells.get(key) for key in keys]
        complete = all(r is not None and r["point_score"] is not None for r in rows)
        interval = [round(sum(r["criterion_score_interval"][i] if r else missing for r in rows)/len(rows), 4)
                    for i, missing in ((0, 0), (1, 100))]
        return {"point_mean": round(sum(r["point_score"] for r in rows)/len(rows), 4) if complete else None,
                "full_denominator_interval": interval, "expected_cells": len(rows),
                "accepted_cells": sum(r is not None for r in rows),
                "unresolved_cells": sum(r is not None and r["point_score"] is None for r in rows),
                "hard_fail_cells": sum(bool(r and r["hard_fail"]) for r in rows)}
    per_model = {model: aggregate(sorted(k for k in expected if k[0] == model)) for model in models}
    result = aggregate(sorted(expected))
    means = [r["point_mean"] for r in per_model.values()]
    return {**result, "per_model": per_model,
            "model_mean_population_sd": round(pstdev(means), 4) if all(v is not None for v in means) else None,
            "per_language": {lang: aggregate(sorted(k for k in expected if k[2] == lang)) for lang in languages},
            "judge": next(iter(judges), None), "score_version": next(iter(versions), None),
            "scope": "descriptive fixed roster and case panel only; not a population estimate"}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(check_plan(root, load_json(root / PLAN)), ensure_ascii=False, indent=2))
