"""Offline confirmation reservation, provenance and immutable checkpoint checks.

Author examples only exercise packet construction. They are never sent to a
judge or treated as expected numerical results. This module has no live runner.
"""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from .config import load_json
from .criterion_anchors import attach_anchors, validate_anchor_set
from .multiturn import validate_multiturn_dataset, variant_hash
from .multiturn_diagnostics import contrast_packet
from .portfolio_audit import _leakage_groups
from .provenance import sha256_json
from . import reference_mix_s36 as mix
from . import scoring_s36 as scoring

CASES = "data/confirmation/s37_cases_v1.json"
ANCHORS = "data/confirmation/s37_anchors_v1.json"
ANSWERS = "data/confirmation/s37_reference_answers_v1.json"
PROVENANCE = "data/confirmation/s37_provenance_v1.json"
RESERVATION = "config/confirmation_s37_reservation_v1.json"
READINESS = "config/run_s37_readiness_v1.json"
FREEZE = "config/s37_offline_frozen_v1.json"
NEW_IDS = ("HC-MT-TRIAGE-022", "HC-MT-REASON-023", "HC-MT-TRIAGE-023")
NEW_PATHS = (CASES, ANCHORS, ANSWERS, PROVENANCE)


def normalized_source(url):
    parsed = urlsplit(url)
    return parsed.netloc.lower(), parsed.path.rstrip("/")


def reservation(root):
    """Bind all six reservations to their exact bilingual cases AND anchors."""
    plan = load_json(root / mix.PLAN)
    records = []
    for index, slot in enumerate(plan["confirmation"]):
        new = index >= 3
        case_path = CASES if new else "data/multiturn/batch_l_cases.json"
        anchor_path = ANCHORS if new else "config/multiturn_criterion_anchors_batch_l_v1.json"
        fid = NEW_IDS[index - 3] if new else slot["family_id"]
        dataset, anchors = load_json(root / case_path), load_json(root / anchor_path)
        validate_multiturn_dataset(dataset)
        validate_anchor_set(anchors, dataset)
        family = next(f for f in dataset["families"] if f["family_id"] == fid)
        anchor = next(a for a in anchors["families"] if a["family_id"] == fid)
        if family["category"] != slot["category"]:
            raise ValueError("Confirmation category differs from prospective slot")
        records.append({"slot": slot["slot"], "family_id": fid, "category": slot["category"],
            "design_stratum": slot["design_stratum"], "case_path": case_path, "anchor_path": anchor_path,
            "case_hashes": {lang: variant_hash(family, lang) for lang in plan["languages"]},
            "anchor_family_sha256": sha256_json(anchor), "source_refs": family["source_refs"],
            "author_mechanism": family["transition_failure_mode"]})
    return {"version": "s37-confirmation-reservation-v1", "status": "reserved_not_hidden_gold",
        "prior_plan_sha256": sha256_json(plan), "live_call_allowance": 0, "families": records,
        "exposure_limit": "Public author drafts; no training-unseen claim. No new model queries. Existing three had no matching local API artifact in the S36 inspection; not proof of external non-exposure.",
        "use": "No development tuning or control judgments on these six. Freeze shared scoring before one final confirmation run; any outcome closes the cycle."}


def check_sources(root, rows):
    plan = load_json(root / mix.PLAN)
    mix.check_plan(root, plan)
    dev_ids = {r["family_id"] for r in plan["development"]}
    reserved = {r["family_id"] for r in rows}
    if len(rows) != 6 or len(reserved) != 6 or reserved & dev_ids or plan["held"]["family_id"] in reserved:
        raise ValueError("Confirmation family collision")
    if Counter(r["design_stratum"] for r in rows) != {"routine": 2, "conditional": 2, "conflicting": 2}:
        raise ValueError("Confirmation stratum imbalance")
    if Counter(r["category"] for r in rows) != {"triage": 2, "clinical_reasoning": 2, "medication_safety": 2}:
        raise ValueError("Confirmation category imbalance")
    existing = {}
    for path in (root / "data/multiturn").glob("*cases.json"):
        existing.update({f["family_id"]: f for f in load_json(path)["families"]})
    if set(NEW_IDS) & set(existing):
        raise ValueError("New confirmation ID already in development")
    dev_sources = {normalized_source(s) for fid in dev_ids for s in existing[fid]["source_refs"]}
    if any(dev_sources & {normalized_source(s) for s in r["source_refs"]} for r in rows):
        raise ValueError("Source URL leakage across selected splits")
    groups = _leakage_groups(load_json(root / "data/audit/overlap_and_source_review.json"))
    if any(set(g) & dev_ids and set(g) & reserved for g in groups):
        raise ValueError("Declared mechanism group crosses split")
    # This check uses declared groups and normalized exact URLs, not a claim of
    # complete semantic independence across all clinical concepts.


def check_provenance(dataset, evidence):
    families = {f["family_id"]: f for f in dataset["families"]}
    records = evidence["records"]
    if len(records) != len(families) or {r["family_id"] for r in records} != set(families):
        raise ValueError("Missing or duplicate source mapping")
    for record in records:
        family = families[record["family_id"]]
        if record["source_refs"] != family["source_refs"]:
            raise ValueError("Source mapping drift")
        expected = [(t["stage_id"], i, req) for t in family["variants"]["en"]["turns"]
                    for i, req in enumerate(t["critical_requirements"], 1)]
        actual = [(r["stage_id"], r["requirement_index"], r["requirement"]) for r in record["criterion_map"]]
        if actual != expected:
            raise ValueError("Requirement/source mapping incomplete or stale")
        errors = [(t["stage_id"], e["id"], e["severity"]) for t in family["variants"]["en"]["turns"]
                  for e in t["critical_errors"]]
        mapped = [(r["stage_id"], r["error_id"], r["severity"]) for r in record["error_map"]]
        if mapped != errors:
            raise ValueError("Error/source mapping incomplete or stale")
        for mapping in record["criterion_map"] + record["error_map"]:
            if not mapping["sources"] or not set(mapping["sources"]) <= set(family["source_refs"]):
                raise ValueError("Unbound mapping source")


def example_packets(root):
    dataset, anchors = load_json(root / CASES), load_json(root / ANCHORS)
    validate_multiturn_dataset(dataset)
    validate_anchor_set(anchors, dataset)
    if {a["family_id"] for a in anchors["families"]} != set(NEW_IDS):
        raise ValueError("Incomplete confirmation anchors")
    references = load_json(root / ANSWERS)["answers"]
    if len(references) != 3 or {r["family_id"] for r in references} != set(NEW_IDS):
        raise ValueError("Incomplete author examples")
    refs = {r["family_id"]: r["variants"] for r in references}
    result = {}
    for family in dataset["families"]:
        for lang in ("en", "zh-Hans"):
            answer = refs[family["family_id"]][lang]
            if set(answer) != {"initial", "update"}:
                raise ValueError("Invalid stage examples")
            full = attach_anchors(contrast_packet(family, {"language": lang,
                "initial_response": answer["initial"], "safe_update_response": answer["update"]}, "safe"), anchors)
            for stage in scoring.STAGES:
                packet = scoring.stage_packet(full, stage, anchors["levels"])
                scoring.schema(packet)
                result[f"{family['family_id']}__{lang}__{stage}"] = packet
    return result


def snapshot(root):
    paths = {mix.PLAN, RESERVATION, READINESS, *NEW_PATHS,
        "benchmark/confirmation_s37.py", "benchmark/run_guard_s37.py",
        "tests/test_confirmation_s37.py", "tests/test_run_guard_s37.py",
        "benchmark/scoring_s36.py", "benchmark/reference_mix_s36.py",
        scoring.COMMON, scoring.EVIDENCE, "benchmark/criterion_anchors.py",
        "benchmark/multiturn.py", "benchmark/multiturn_diagnostics.py", "benchmark/portfolio_audit.py",
        "benchmark/config.py", "benchmark/provenance.py", "benchmark/scoring_s26.py",
        "config/benchmark.json", "config/model_matrix.json", "data/audit/overlap_and_source_review.json",
        "data/audit/s36_integration_summary.json", "data/audit/s36_proposal_summary.json"}
    paths.update(r[k] for r in reservation(root)["families"] for k in ("case_path", "anchor_path"))
    return {"version": "s37-offline-checkpoint-v1", "scope": "Cases, reservations and guard primitives only; NOT a frozen live protocol",
        "live_call_allowance": 0,
        "sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sorted(paths)}}


def audit(root):
    dataset = load_json(root / CASES)
    validate_multiturn_dataset(dataset)
    if [f["family_id"] for f in dataset["families"]] != list(NEW_IDS):
        raise ValueError("New confirmation family identity/order changed")
    check_provenance(dataset, load_json(root / PROVENANCE))
    saved = load_json(root / RESERVATION)
    if saved != reservation(root):
        raise ValueError("Stale confirmation reservation")
    check_sources(root, saved["families"])
    packets = example_packets(root)
    config = load_json(root / "config/benchmark.json")
    if CASES in config["multiturn_cases_paths"]:
        raise ValueError("Confirmation drafts entered default development")
    if snapshot(root) != load_json(root / FREEZE):
        raise ValueError("S37 offline snapshot changed")
    if scoring.audit(root) != load_json(root / "data/audit/s36_integration_summary.json"):
        raise ValueError("Earlier scoring checkpoint changed")
    return {"version": "s37-offline-confirmation-v1", "new_families": 3, "new_language_variants": 6,
        "reserved_families": 6, "reserved_language_variants": 12,
        "source_mapped_requirements": 18, "source_mapped_named_errors": 6,
        "structural_example_stage_packets": len(packets), "numerically_scored_examples": 0,
        "selected_split_source_and_declared_mechanism_check": "pass_with_documented_limits",
        "default_development_changed": False, "clinical_approval": False,
        "live_call_allowance": 0, "live_ready": False,
        "reservation_sha256": sha256_json(saved),
        "offline_snapshot_sha256": sha256_json(load_json(root / FREEZE))}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
