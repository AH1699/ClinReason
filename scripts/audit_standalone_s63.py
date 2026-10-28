"""Text-free, read-only audit of a terminal S62 pilot, never a new model call.

All 64 cells and their holds remain; first/repeat stay separate. No rank, pooled
model mean, label repair, clinical adjudication or automatic further experiment.
"""

import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

from benchmark.answer_language_audit import HAN, LATIN_WORD
from scripts import standalone_live_s62 as live

VERSION = "s63-standalone-readout-v1"
FILES = ("scripts/audit_standalone_s63.py", "tests/test_audit_standalone_s63.py",
         "benchmark/answer_language_audit.py")
SCORE_FIELDS = ("score_version", "criterion_score_interval", "point_score", "provisional_pass", "hard_fail",
                "unclear_criterion", "independent_dimension_review", "clinical_review_status")


def tree_hash(root, directory):
    directory = live.previous.safe_directory(Path(root), directory)
    hashes = {}
    for path in sorted(directory.rglob("*")):
        if (path.is_symlink() or not (path.is_file() or path.is_dir())
                or path.is_file() and path.stat().st_nlink != 1):
            raise ValueError("Linked or nonregular journal artifact")
        if path.is_file():
            hashes[path.relative_to(directory).as_posix()] = live.digest(path.read_bytes())
    return live.pilot.sha256_json(hashes)


def judgment(value):
    if value is None:
        return None
    return {"criterion_assessments": [{k: r[k] for k in ("stage_id", "requirement_index", "status")}
                                     for r in value["criterion_assessments"]],
            "critical_errors": [{k: e[k] for k in ("stage_id", "error_id", "severity")}
                                for e in value["critical_errors"]],
            "dimension_observations": [{k: o[k] for k in ("dimension", "decision")}
                                       for o in value.get("dimension_observations", [])]}


def language_flag(text, language):
    """Same conservative thresholds as the existing offline language screen."""
    if language not in ("en", "zh-Hans") or not isinstance(text, str) or not text.strip():
        raise ValueError("Nonempty accepted answer and declared language required")
    han, latin = len(HAN.findall(text)), len(LATIN_WORD.findall(text))
    reason = None
    if language == "zh-Hans" and han < 3 and latin >= 20:
        reason = "zh_expected_english_script_dominant"
    elif language == "en" and latin < 5 and han >= 20:
        reason = "en_expected_han_script_dominant"
    return None if reason is None else {"reason": reason, "han_character_count": han, "latin_word_count": latin}


def conversation(cell, families):
    family = families[cell["family_id"]]
    result = {k: deepcopy(cell[k]) for k in ("cell_id", "family_id", "language", "stratum", "review_issues",
                                           "clinical_comparison_held", "answer_stages_present")}
    result.update(candidate={k: cell["candidate"][k] for k in ("provider", "model")},
        case_version=family["version"], family_sha256=family["family_sha256"],
        case_content_hash=family["case_hashes"][cell["language"]])
    for phase in ("first", "repeat"):
        value = cell[phase]
        result[phase] = {"score": None if value["score"] is None else
            {k: deepcopy(value["score"][k]) for k in SCORE_FIELDS},
            "judgments": {s: judgment(value["judgments"][s]) for s in live.base.score.STAGES}}
    return result


def phase_counts(cells, phase):
    scores = [c[phase]["score"] for c in cells if c[phase]["score"] is not None]
    points = [s["point_score"] for s in scores if s["point_score"] is not None]
    return {"expected_cells": len(cells), "complete_conversations": len(scores),
        "missing_conversations": len(cells) - len(scores), "point_scores": len(points),
        "interval_only": len(scores) - len(points), "point_range": [min(points), max(points)] if points else None,
        "exactly_100": sum(p == 100 for p in points),
        "provisional_pass_true": sum(s["provisional_pass"] is True for s in scores),
        "provisional_pass_false": sum(s["provisional_pass"] is False for s in scores),
        "provisional_pass_unresolved": sum(s["provisional_pass"] is None for s in scores),
        "hard_fail": sum(s["hard_fail"] is True for s in scores),
        "accepted_stage_judgments": sum(c[phase]["judgments"][s] is not None
                                        for c in cells for s in live.base.score.STAGES)}


def repeat_comparison(cell):
    first, repeat = cell["first"]["score"], cell["repeat"]["score"]
    if first is None or repeat is None:
        return None
    a, b = first["point_score"], repeat["point_score"]
    return {"cell_id": cell["cell_id"], "clinical_comparison_held": cell["clinical_comparison_held"],
        "first_point": a, "repeat_point": b, "point_comparable": a is not None and b is not None,
        "point_delta_repeat_minus_first": float(Decimal(str(b)) - Decimal(str(a))) if a is not None and b is not None else None,
        "stage_vector_matches": {s: live.base.workflow.vector(cell["first"]["judgments"][s]) ==
                                    live.base.workflow.vector(cell["repeat"]["judgments"][s]) for s in live.base.score.STAGES},
        "score_interval_changed": first["criterion_score_interval"] != repeat["criterion_score_interval"],
        "provisional_pass_changed": first["provisional_pass"] != repeat["provisional_pass"],
        "hard_fail_changed": first["hard_fail"] != repeat["hard_fail"],
        "independent_dimension_review_changed": first["independent_dimension_review"] != repeat["independent_dimension_review"]}


def family_readout(cells):
    values = []
    for family in dict.fromkeys(c["family_id"] for c in cells):
        group = [c for c in cells if c["family_id"] == family]
        paired = [v for c in group if (v := repeat_comparison(c)) is not None]
        deltas = [v["point_delta_repeat_minus_first"] for v in paired if v["point_comparable"]]
        values.append({"family_id": family, "expected_cells": len(group),
            "review_held_cells": sum(c["clinical_comparison_held"] for c in group),
            "first": phase_counts(group, "first"), "repeat": phase_counts(group, "repeat"),
            "complete_repeat_pairs": len(paired), "point_comparable_repeats": len(deltas),
            "exact_point_repeats": sum(d == 0 for d in deltas),
            "maximum_absolute_repeat_gap": max(map(abs, deltas)) if deltas else None,
            "matching_stage_vectors": sum(sum(v["stage_vector_matches"].values()) for v in paired),
            "compared_stage_vectors": 2*len(paired),
            "provisional_pass_changes": sum(v["provisional_pass_changed"] for v in paired)})
    return values


def control_readout(value, records):
    mapping = {r["key"]: r for r in records}
    phases, results = {}, []
    for stage in value["stage_results"]:
        phase, key = stage["job_id"].split("__", 1)
        record = mapping[key]
        row = {k: deepcopy(stage[k]) for k in ("job_id", "profile", "criterion_statuses", "critical_errors", "observations")}
        row.update({k: deepcopy(record[k]) for k in ("family_id", "language", "stage", "hypothesized_error_id")})
        results.append(row)
        phases[phase, key] = row
    changes = []
    for record in records:
        key = record["key"]
        first, repeat = phases.get(("control_first", key)), phases.get(("control_repeat", key))
        if first and repeat and first["criterion_statuses"] is not None and repeat["criterion_statuses"] is not None:
            # Error order does not change the vector, matching the frozen gate.
            vector = lambda r: (r["criterion_statuses"], sorted((e["stage_id"], e["error_id"], e["severity"])
                                                                for e in r["critical_errors"]))
            if vector(first) != vector(repeat):
                changes.append({"control_key": key, "first": first, "repeat": repeat})
    fields = ("expected_records", "accepted_records", "structurally_complete", "hypothesized_unsafe_errors",
        "observed_unsafe_error_matches", "unsafe_hypothesis_mismatches", "expected_repeat_stage_pairs",
        "matching_repeat_criterion_error_vectors", "non_unsafe_records_with_errors", "clinical_gate", "numeric_order_gate")
    return {**{k: deepcopy(value[k]) for k in fields}, "stage_results": results, "repeat_vector_changes": changes}


def audit(root, directory, freeze):
    root, directory = Path(root), Path(directory).absolute()
    if freeze != live.snapshot(root):
        raise ValueError("Frozen S62 implementation differs")
    before = tree_hash(root, directory)
    checked = live.replay(root, directory)
    report = checked["report"]
    if checked["incomplete_tail"] is not None or not checked["report_verified"] or report["terminal"] is None:
        raise ValueError("Active/interrupted prefix is not a terminal audit; use S62 replay")
    manifest = live.pilot.verify(root)
    families = {f["family_id"]: f for f in manifest["families"]}
    cells = [conversation(c, families) for c in report["conversations"]]
    by_cell = {c["cell_id"]: c for c in cells}
    attempts, language_flags, language_checked = [], [], 0
    for event in sorted((directory / "events").iterdir()):
        record = live.read(event / "reservation.json")
        outcome = live.read(event / "result.json")
        row = record["row"]
        attempts.append({"event": int(event.name), **{k: row[k] for k in
            ("id", "kind", "control_key", "cell_id", "stage") if k in row},
            "outcome": outcome["outcome"], "category": outcome["category"]})
        if row["kind"] == "candidate" and outcome["outcome"]["status"] == "accepted":
            # Replay already bound this saved text to the raw provider response,
            # model, case and stage; the enclosing before/after hash detects drift.
            cell = by_cell[row["cell_id"]]
            text = live.read(event / "transport/0001.accepted.json")["result"]["text"]
            flag = language_flag(text, cell["language"])
            language_checked += 1
            if flag is not None:
                language_flags.append({"cell_id": row["cell_id"], "stage_id": row["stage"], **flag})
    if tree_hash(root, directory) != before:
        raise ValueError("Journal changed during audit")
    counts = dict(Counter(a["outcome"]["status"] for a in attempts))
    if (len(attempts) != checked["events"] or len(attempts) != report["settled_attempts"]
            or language_checked != sum(len(c["answer_stages_present"]) for c in cells)
            or any(counts.get(k, 0) != report["outcomes"].get(k, 0) for k in ("accepted", "rejected"))):
        raise ValueError("Attempt denominator differs")
    fields = ("mode", "simulation_only", "terminal", "live_calls", "live_call_count_basis", "measured_model_scores",
        "numeric_fixture_scores_only", "settled_attempts", "unresolved_reservations", "outcomes", "unattempted_jobs",
        "unknown_cost_attempts", "monitoring_usd", "closed_candidate_models", "development_format_failures",
        "prospective_control_gate", "repeat_summary", "automatic_retries", "resume_allowed")
    return {"version": VERSION, "protocol_sha256": checked["protocol_sha256"], "source_journal_sha256": before,
        "reporter_files": {p: live.digest((root / p).read_bytes()) for p in FILES},
        "new_provider_calls_by_audit": 0, "cost_is_invoice_or_hard_ceiling": False,
        "execution": {k: deepcopy(report[k]) for k in fields},
        "control_readout": control_readout(report["control_readout"], manifest["controls"]),
        "expected_conversations": 64, "conversations": cells, "family_readout": family_readout(cells),
        "repeat_comparisons": [v for c in cells if (v := repeat_comparison(c)) is not None],
        "attempts": attempts,
        "answer_language_screen": {"expected_turns": 128, "checked_accepted_turns": language_checked,
            "missing_or_rejected_turns": 128-language_checked, "flags": language_flags,
            "method": "existing_conservative_script_thresholds_not_language_quality_or_equivalence",
            "unflagged_is_not_language_approval": True, "score_adjustments": False},
        "interpretation": {"missing_is_not_zero": True, "unclear_is_interval_not_zero": True,
            "repeat_scores_averaged": False, "pooled_model_means": False, "model_rankings": False,
            "all_clinical_holds_retained": True, "clinical_validation": False, "raw_text_exported": False,
            "score_band_fitting": False, "next_paid_diagnostic_automatically_authorized": False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--freeze", type=Path, default=Path(live.FREEZE))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(audit(root, args.directory, live.read(args.freeze)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
