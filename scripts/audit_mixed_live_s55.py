"""Read-only, text-free diagnostics for a terminal S54 journal.

No credentials, transport, new judgments, retries or resumption. Revalidate the
frozen journal first, then reuse its unchanged scoring for separate case cells.
Never export answer text, judge explanations, pooled means or model rankings.
"""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from scripts import mixed_live_s54 as live

VERSION = "s55-mixed-panel-readonly-audit-v1"
panel, journal = live.panel, live.journal


def restore(root, directory, protocol):
    """Return verified terminal state, without modifying the frozen reader."""
    checked = live.replay(root, directory, protocol)
    if checked["interrupted"]:
        raise ValueError("Active or interrupted prefix: use S54 read-only replay instead")
    manifest = journal.read(directory / "manifest.json")
    core = panel.Rehearsal(root, journal.read(directory / "imports.json"),
        mode="offline_fixture", fixture_threshold_usd=manifest["threshold_usd"])
    attempts = []
    for event in sorted((directory / "events").iterdir()):
        request = core.prepare()
        if request is None:
            continue
        meta = journal.read(event / "capture/0001.capture.json")
        attempts.append({"row": request["row"], "category": meta["category"]})
        if meta["category"] in live.rehearsal.BODY_CATEGORIES:
            core.record((event / "capture/0001.raw.bin").read_bytes())
        else:
            core.terminal = "transport_failure_unknown_delivery_or_cost"
    if live.report(core, manifest["mode"], len(attempts)) != checked:
        raise ValueError("Diagnostic reconstruction differs from frozen replay")
    return checked, core, attempts


def stage_diagnostic(judgment):
    """Only typed status/identifier fields, never free-text evidence."""
    return {
        "criterion_statuses": [item["status"] for item in judgment["criterion_assessments"]],
        "critical_errors": [{k: item[k] for k in ("stage_id", "error_id", "severity")}
                            for item in judgment["critical_errors"]],
        "dimension_decisions": [{k: item[k] for k in ("dimension", "decision")}
                                for item in judgment.get("dimension_observations", [])],
    }


def pair_diagnostic(core, row):
    first = {**row, "stage": "initial"}
    if row["block"] == "control":
        first["profile"] = None
    keys = [panel.workflow.judgment_key(r) for r in (first, row)]
    if any(k not in core.judgments for k in keys):
        return None
    judgments = [core.judgments[k] for k in keys]
    _, combined = panel.score.combine(*judgments, core.contexts[row["sequence"]]["full"],
        {"version": panel.score.VERSION, **panel.score.ARITHMETIC})
    # Explicit allowlist prevents later scorer additions leaking prose.
    fields = ("score_version", "criterion_score_interval", "point_score",
              "provisional_pass", "hard_fail", "independent_dimension_review")
    return {"scoring": {k: deepcopy(combined[k]) for k in fields},
            "stages": {stage: stage_diagnostic(value)
                       for stage, value in zip(panel.score.STAGES, judgments)}}


def diagnostics(core):
    passed = core.gate()["pass"]
    cells = live.policy.reporting_manifest(core.root)["conversations"]
    lookup = {(r["family_id"], r["language"], r["candidate_model"], r["repeat"]): r
              for r in core.rows if r["kind"] == "judge" and r["block"] == "development"
              and r["stage"] == "update"}
    for cell in cells:
        key = cell["family_id"], cell["language"], cell["candidate_model"]
        for repeat, label in ((False, "first"), (True, "repeat")):
            row = lookup[(*key, repeat)]
            value = pair_diagnostic(core, row) if passed else None
            cell[label] = value
            cell[label + "_missing_reason"] = (None if value is not None else
                "control_gate_not_passed" if not passed else "judgment_pair_missing")
        cell["repeat_stage_vector_matches"] = None
        if cell["first"] is not None and cell["repeat"] is not None:
            cell["repeat_stage_vector_matches"] = {
                stage: panel.workflow.vector(core.judgments[panel.workflow.judgment_key(
                    {**lookup[(*key, False)], "stage": stage})]) ==
                panel.workflow.vector(core.judgments[panel.workflow.judgment_key(
                    {**lookup[(*key, True)], "stage": stage})])
                for stage in panel.score.STAGES}
    controls = []
    for row in core.rows:
        if row["block"] != "control" or row["stage"] != "update":
            continue
        value = pair_diagnostic(core, row)
        controls.append({k: row[k] for k in ("family_id", "language", "profile", "repeat")}
                        | {"diagnostic": value})
    return {"conversations": cells, "controls": controls}


def audit(root, directory, freeze):
    root, directory = Path(root), Path(directory)
    if freeze != live.snapshot(root):
        raise ValueError("Source freeze differs")
    protocol = panel.sha256_json(freeze)
    checked, core, attempts = restore(root, directory, protocol)
    counts = Counter((a["row"]["kind"], a["row"]["block"], a["row"]["model"],
                      a["row"]["repeat"], a["category"]) for a in attempts)
    result = diagnostics(core)
    cells = result["conversations"]
    return {"version": VERSION, "protocol_sha256": protocol,
        "reporter_files": {p: journal.digest((root / p).read_bytes()) for p in
            ("scripts/audit_mixed_live_s55.py", "tests/test_audit_mixed_live_s55.py")},
        "mode": checked["mode"], "simulation_only": checked["simulation_only"],
        "terminal": checked["terminal"], "scope_exhausted": core.index == len(core.rows),
        "live_calls": checked["live_calls"], "transport_attempts": checked["transport_attempts"],
        "maximum_authorized_attempts": 452 if checked["mode"] == "live" else None,
        "stop_threshold_usd": journal.read(directory / "manifest.json")["threshold_usd"],
        "monitoring_estimate_usd": checked["monitoring_estimate_usd"],
        "unknown_charge_attempts": checked["unknown_charge_attempts"],
        "cost_is_invoice_or_hard_ceiling": False,
        "outcomes": checked["outcomes"],
        "skip_reasons": dict(Counter(v["reason"] for v in core.outcomes.values() if v["status"] == "skipped")),
        "attempt_counts": [{"kind": k[0], "block": k[1], "model": k[2], "repeat": k[3],
                            "category": k[4], "count": v} for k, v in sorted(counts.items())],
        "expected_conversations": 72, "expected_answer_stages": 144,
        "answer_stages_present": checked["answer_stages_present"],
        "answer_presence": checked["conversations"],
        "control_gate": checked["control_gate"],
        "first_complete_conversation_judgments": sum(c["first"] is not None for c in cells),
        "repeat_complete_conversation_judgments": sum(c["repeat"] is not None for c in cells),
        "review_held_conversations": sum(c["comparative_review_hold"] for c in cells),
        "reporting": checked["reporting"], "automatic_retries": 0, "resume_allowed": False,
        "raw_answer_or_explanation_text_exported": False,
        "clinical_validation": False, "new_provider_calls_by_audit": 0,
        **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--freeze", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(audit(root, args.directory, journal.read(args.freeze)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
