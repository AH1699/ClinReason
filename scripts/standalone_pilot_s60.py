"""Read-only O/P/Q pilot inputs and proposed schedule; never connects to providers.

The saved manifest freezes authoring inputs, not an executable paid protocol.
No credentials, private records, automatic registration or score computation.
"""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from benchmark.config import load_json
from benchmark.criterion_anchors import attach_anchors
from benchmark.multiturn import variant_hash
from benchmark.multiturn_diagnostics import contrast_packet
from benchmark.provenance import sha256_json
from benchmark import scoring_s36 as score
from scripts import audit_batch_o as batch_o, audit_batch_p as batch_p, audit_batch_q as batch_q
from scripts import batch_o_wording_s52 as wording, batch_o_components_s53 as components
from scripts import judge_evidence_s56 as evidence

PLAN = "config/standalone_pilot_s60_v1.json"
MANIFEST = "data/audit/s60_standalone_pilot_manifest.json"
MODULES = {"o": batch_o, "p": batch_p, "q": batch_q}
EXPECTED = {
    "HC-MT-REASON-025": ("p", "diagnostic_restraint", ["H145"]),
    "HC-MT-TRIAGE-024": ("p", "diagnostic_restraint", ["H146"]),
    "HC-MT-REASON-027": ("q", "diagnostic_restraint", ["H151"]),
    "HC-MT-REASON-024": ("o", "competing_treatment_risks", ["H142", "H144"]),
    "HC-MT-MEDSAFE-020": ("o", "competing_treatment_risks", ["H143", "H144"]),
    "HC-MT-MEDSAFE-021": ("q", "competing_treatment_risks", ["H149"]),
    "HC-MT-REASON-026": ("q", "escalation_under_uncertainty", ["H150"]),
    "HC-MT-TRIAGE-025": ("q", "escalation_under_uncertainty", ["H152"]),
}
CODE = (
    "scripts/standalone_pilot_s60.py", "tests/test_standalone_pilot_s60.py",
    "scripts/audit_batch_o.py", "scripts/audit_batch_p.py", "scripts/audit_batch_q.py",
    "scripts/batch_o_boundary_review_s51.py", "scripts/batch_o_wording_s52.py",
    "scripts/batch_o_components_s53.py", "scripts/judge_evidence_s56.py",
    "scripts/judge_observation_draft.py", "benchmark/scoring_s36.py",
    "benchmark/scoring_s26.py", "benchmark/criterion_anchors.py",
    "benchmark/multiturn.py", "benchmark/multiturn_diagnostics.py",
    "benchmark/provenance.py", "benchmark/config.py",
)


def public_path(root, relative):
    """Only explicit local public files; reject links even in parent directories."""
    path = Path(relative)
    if (path.is_absolute() or not path.parts or path.parts[0] not in {"config", "data", "scripts", "benchmark", "tests"}
            or ".." in path.parts):
        raise ValueError("Expected public repository path")
    result = root / path
    if (any((root / Path(*path.parts[:i])).is_symlink() for i in range(1, len(path.parts) + 1))
            or not result.resolve().is_relative_to(root.resolve()) or not result.is_file()):
        raise ValueError("Missing, linked or nonlocal public input")
    return result


def plan(root):
    value = load_json(public_path(root, PLAN))
    rows = value["selection"]
    selected = {r["family_id"]: (r["batch"], r["stratum"], r["review_issues"]) for r in rows}
    if (selected != EXPECTED or len(rows) != 8 or value["languages"] != ["en", "zh-Hans"]
            or value["version"] != "s60-standalone-pilot-offline-v1"
            or value["status"] != "offline_input_freeze_not_execution_authorization"
            or value["batch_o_label_version"] != "s52_derived_0.2.0_not_original_0.1.0"
            or value["candidate_instruction"] != "config/candidate_prompt_bilingual_v2.txt"
            or value["live_call_allowance"] != 0 or type(value["live_call_allowance"]) is not int
            or value["default_registry_changes"] is not False or value["private_records_included"] is not False):
        raise ValueError("Changed pilot identity, selection or offline scope")
    roster = value["candidate_roster_proposal"]
    if roster != [
        {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
        {"provider": "gemini", "model": "gemini-3.8-flash"},
        {"provider": "minimax", "model": "MiniMax-M3.1-Flash"},
        {"provider": "minimax", "model": "MiniMax-M3"}]:
        raise ValueError("Changed proposed roster; version the design")
    if value["judge_proposal"] != {"provider": "gemini", "model": "gemini-3.8-flash", "evidence_contract": "s56", "arithmetic": "unchanged_s36"}:
        raise ValueError("Changed judge or arithmetic proposal")
    cost = value["prospective_cost_policy"]
    if cost != {"max_in_flight": 1, "automatic_retries": 0, "resume_allowed": False,
                "hard_ceiling": False, "last_request_overrun_possible": True,
                "unknown_delivery_or_cost": "global_stop", "recorded_spending_stop_threshold_usd": None,
                "current_price_evidence": None, "approval": None}:
        raise ValueError("S60 cannot carry a paid approval, price or spending allowance")
    reporting = value["reporting"]
    if (any(reporting[k] is not False for k in ("pooled_model_means", "model_rankings", "retrospective_rescoring", "score_band_fitting"))
            or reporting["all_families_require_clinical_and_language_review"] is not True
            or reporting["missing_scores"] != "missing_never_zero"
            or reporting["repeats"] != "separate_never_averaged"
            or value["controls"]["profiles"] != ["safe", "partial", "unsafe"]
            or value["controls"]["numeric_targets"] is not False
            or value["controls"]["strict_order_expected"] is not False):
        raise ValueError("Changed provisional reporting/control contract")
    return value


def inputs(root):
    root = Path(root)
    spec = plan(root)
    files = {PLAN, wording.DATA, components.DATA, wording.review.DATA,
             score.COMMON, score.EVIDENCE, spec["candidate_instruction"], *CODE}
    for module in MODULES.values():
        files.update(module.FILES.values())
    # Validate every path before the materializers read it.
    for path in files:
        public_path(root, path)
    data = {b: {k: load_json(root / path) for k, path in m.FILES.items()} for b, m in MODULES.items()}
    batch_o.validate(*(data["o"][k] for k in ("cases", "anchors", "controls", "provenance")))
    batch_p.validate(data["p"])
    batch_q.validate(data["q"])
    original_o = deepcopy(data["o"]["cases"])
    derived, anchors, _, _ = wording.materialize(root)
    data["o"]["cases"], data["o"]["anchors"] = derived, anchors
    supplement = components.audit(root)
    catalog = {}
    for b, values in data.items():
        for family in values["cases"]["families"]:
            fid = family["family_id"]
            if fid in catalog:
                raise ValueError("Duplicate selected family")
            original = next(f for f in original_o["families"] if f["family_id"] == fid) if b == "o" else family
            provenance = next(r for r in values["provenance"]["records"] if r["family_id"] == fid)
            positions = [(t["stage_id"], i) for t in family["variants"]["en"]["turns"]
                         for i in range(1, len(t["critical_requirements"]) + 1)]
            if positions != [(r["stage"], r["index"]) for r in provenance["requirement_support"]]:
                raise ValueError("Incomplete source-to-requirement mapping")
            catalog[fid] = {"family": family, "original": original, "anchors": values["anchors"],
                            "provenance": provenance, "batch": b,
                            "probes": {p["language"]: p for p in values["controls"]["probes"] if p["family_id"] == fid}}
    if set(catalog) != set(EXPECTED):
        raise ValueError("Selection must include exactly the eight O/P/Q families")
    registry = load_json(public_path(root, "config/benchmark.json"))
    if any(m.FILES["cases"] in registry["multiturn_cases_paths"] for m in MODULES.values()):
        raise ValueError("Standalone pilot was silently registered")
    return spec, catalog, supplement, sorted(files)


def candidate_history(family, language, stage, initial_answer=None):
    """Transport-neutral visible messages only. Never substitutes reference answers."""
    if stage not in score.STAGES or language not in ("en", "zh-Hans"):
        raise ValueError("Unknown language or stage")
    turns = family["variants"][language]["turns"]
    messages = [{"role": "user", "content": turns[0]["user"]}]
    if stage == "initial":
        if initial_answer is not None:
            raise ValueError("Initial request cannot contain an answer")
    else:
        if not isinstance(initial_answer, str) or not initial_answer.strip():
            raise ValueError("Update requires this candidate's validated initial answer")
        messages.extend([{"role": "assistant", "content": initial_answer},
                         {"role": "user", "content": turns[1]["user"]}])
    return messages


def judge_input(root, packet):
    """No control profile, expected status, model identity or later-stage labels."""
    score.check_packet(packet)
    return {"packet": deepcopy(packet), "instruction": evidence.instruction(root, packet),
            "schema": evidence.schema(packet)}


def controls(root, catalog):
    packets, records = {}, []
    for fid, entry in catalog.items():
        for lang, probe in entry["probes"].items():
            materializer = batch_o.materialize_probe if entry["batch"] == "o" else MODULES[entry["batch"]].materialize
            pair = materializer(probe)
            omitted = (probe["construction"] if entry["batch"] == "o" else probe)["partial_omitted_requirement_index"]
            for profile in ("safe", "partial", "unsafe"):
                full = attach_anchors(contrast_packet(entry["family"], pair, profile), entry["anchors"])
                for stage in score.STAGES:
                    key = "__".join((fid, lang, stage, "shared" if stage == "initial" else profile))
                    packet = score.stage_packet(full, stage, entry["anchors"]["levels"])
                    if key in packets:
                        if packets[key] != packet:
                            raise ValueError("Cannot share unequal initial packets")
                        continue
                    packets[key] = packet
                    records.append({"key": key, "family_id": fid, "language": lang, "stage": stage,
                        "profile": None if stage == "initial" else profile,
                        "omitted_component": omitted if stage == "update" and profile == "partial" else None,
                        "hypothesized_error_id": probe["expected_unsafe_error_id"] if stage == "update" and profile == "unsafe" else None,
                        "expected_status": None, "expected_score": None,
                        "review_issues": EXPECTED[fid][2],
                        "packet_sha256": sha256_json(packet),
                        "judge_input_sha256": sha256_json(judge_input(root, packet))})
    if len(packets) != 64 or len({sha256_json(p) for p in packets.values()}) != 64:
        raise ValueError("Core controls must contain 16 shared initials and 48 distinct updates")
    return packets, records


def schedule(spec, records):
    """Proposal only. References to responses are dependencies, not placeholder answers."""
    rows = []
    for phase in ("control_first", "control_repeat"):
        for record in sorted(records, key=lambda r: (score.STAGES.index(r["stage"]), r["key"])):
            if phase == "control_repeat" and record["stage"] == "update" and record["profile"] != "partial":
                continue
            rows.append({"id": phase + "__" + record["key"], "kind": phase, "control_key": record["key"],
                         "judge_input_sha256": record["judge_input_sha256"], "dependencies": []})
    cells = [{"cell_id": "__".join((r["family_id"], lang, model["model"])), "family_id": r["family_id"],
              "language": lang, "candidate": deepcopy(model), "stratum": r["stratum"],
              "review_issues": r["review_issues"], "clinical_comparison_held": True}
             for r in spec["selection"] for lang in spec["languages"] for model in spec["candidate_roster_proposal"]]
    for kind in ("candidate", "judge_first", "judge_repeat"):
        for cell in cells:
            cid = cell["cell_id"]
            for stage in score.STAGES:
                dependencies = []
                if kind == "candidate" and stage == "update":
                    dependencies = ["candidate__" + cid + "__initial"]
                elif kind != "candidate":
                    dependencies = ["candidate__" + cid + "__" + s for s in score.STAGES
                                    if stage == "update" or s == "initial"]
                    if kind == "judge_repeat":
                        dependencies.append("judge_first__" + cid + "__" + stage)
                rows.append({"id": "__".join((kind, cid, stage)), "kind": kind, "cell_id": cid,
                             "stage": stage, "dependencies": dependencies})
    ids = set()
    for row in rows:
        if row["id"] in ids or not set(row["dependencies"]).issubset(ids):
            raise ValueError("Duplicate job or forward/missing dependency")
        ids.add(row["id"])
    return cells, rows


def snapshot(root):
    root = Path(root)
    spec, catalog, supplement, files = inputs(root)
    packets, records = controls(root, catalog)
    cells, jobs = schedule(spec, records)
    families, positions = [], 0
    for selection in spec["selection"]:
        entry = catalog[selection["family_id"]]
        family, original = entry["family"], entry["original"]
        counts = {t["stage_id"]: len(t["critical_requirements"]) for t in family["variants"]["en"]["turns"]}
        positions += sum(counts.values())
        mappings = []
        for mapping in entry["provenance"]["requirement_support"]:
            changed = entry["batch"] == "o" and (mapping["stage"], mapping["index"]) == ("update", 3)
            mappings.append({"stage": mapping["stage"], "index": mapping["index"],
                "source_mapping_sha256": sha256_json(mapping), "guidance_url": mapping["guidance_url"],
                "source_locator": mapping["source_locator"],
                "binding": "original_source_mapping_plus_unrevalidated_s52_wording" if changed else "selected_requirement_unchanged_from_source_map",
                "clinical_approval": False})
        families.append({**selection, "version": family["version"], "category": family["category"],
            "family_sha256": sha256_json(family), "original_family_sha256": sha256_json(original),
            "case_hashes": {lang: variant_hash(family, lang) for lang in spec["languages"]},
            "anchor_set_sha256": sha256_json(entry["anchors"]), "source_record_sha256": sha256_json(entry["provenance"]),
            "artifact_paths": MODULES[entry["batch"]].FILES, "criterion_counts": counts,
            "source_mapping": mappings, "related_families": entry["provenance"]["related_families"],
            "initial_candidate_messages_sha256": {lang: sha256_json(candidate_history(family, lang, "initial")) for lang in spec["languages"]},
            "clinical_and_language_review": "pending"})
    counts = dict(Counter(r["kind"] for r in jobs))
    if counts != {"control_first": 64, "control_repeat": 32, "candidate": 128, "judge_first": 128, "judge_repeat": 128}:
        raise ValueError("Changed proposed call counts")
    return {"version": spec["version"], "status": spec["status"], "plan_sha256": sha256_json(spec),
        "files": {p: hashlib.sha256(public_path(root, p).read_bytes()).hexdigest() for p in files},
        "families": families, "counts": {"families": len(families), "language_variants": 2*len(families),
            "criterion_positions": positions, "bilingual_criterion_positions": 2*positions,
            "candidate_conversations": len(cells), "control_conversations": 48,
            "unique_control_stage_packets": len(packets), "proposed_requests_by_kind": counts,
            "proposed_total_requests": len(jobs)},
        "strata": dict(Counter(r["stratum"] for r in families)),
        "categories": dict(Counter(r["category"] for r in families)),
        "controls": records, "conversation_cells": cells, "proposed_schedule_sha256": sha256_json(jobs),
        "batch_o_offline_supplement": supplement, "arithmetic": deepcopy(score.ARITHMETIC),
        "reporting": spec["reporting"], "remaining_before_paid_run": spec["remaining_before_paid_run"],
        "execution_ready": False, "live_calls": 0, "numeric_scores": 0, "new_families": 0,
        "default_registry_changes": False, "private_records_included": False,
        "clinical_validation": False, "paid_authorization": None}


def verify(root):
    actual = snapshot(root)
    if load_json(public_path(Path(root), MANIFEST)) != actual:
        raise ValueError("S60 input manifest is stale; do not silently reuse it")
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Compare current inputs to the saved manifest")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    value = verify(root) if args.verify else snapshot(root)
    if args.summary:
        value = {k: value[k] for k in ("version", "status", "counts", "strata", "categories", "remaining_before_paid_run",
                                     "execution_ready", "live_calls", "numeric_scores", "new_families", "paid_authorization")}
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
