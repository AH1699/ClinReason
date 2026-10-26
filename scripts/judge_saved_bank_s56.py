"""Read-only preparation of all 144 saved stages for a new judge-only protocol.

The private bank contains final answers, never provider reasoning. This module
has no live command, credential loading, transport or write path. Public output
is an explicit metadata allowlist. A bank hash alone is NOT provenance: verification
rehydrates the sealed S54 journal and its pinned S45/S46 upstream imports.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from scripts import audit_mixed_live_s55 as source, judge_evidence_s56 as draft

panel, live, journal = source.panel, source.live, source.journal
workflow, score, guard = panel.workflow, panel.score, panel.guard
VERSION = "s56-saved-panel-offline-v1"
PLAN = "config/judge_saved_bank_s56_v1.json"
FILES = (PLAN, "scripts/judge_evidence_s56.py", "scripts/judge_saved_bank_s56.py",
         "tests/test_judge_evidence_s56.py", "tests/test_judge_saved_bank_s56.py",
         "scripts/audit_mixed_live_s55.py", "tests/test_audit_mixed_live_s55.py")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def plan(root):
    spec = panel.read_json(root / PLAN)
    expected = {"version": VERSION, "status": "offline_preparation_not_live_protocol",
        "expected_answer_stages": 144, "expected_conversations": 72, "new_candidate_calls": 0,
        "proposed_control_judgments": 36, "proposed_first_judgments": 144,
        "proposed_repeat_judgments": 144, "proposed_maximum_judge_calls": 324,
        "judge_model": panel.saved.MODEL,
        "judge_generation_config": {"max_output_tokens": 32768, "thinking_level": "medium"},
        "live_call_allowance": 0, "live_budget_usd": None, "automatic_retries": 0,
        "resume_allowed": False, "historical_judgments_reused": False,
        "fresh_control_gate_required": True}
    if (set(spec) != set(expected) | {"source_directory", "source_protocol_sha256", "source_tree_sha256"}
            or any(type(spec.get(k)) is not type(v) or spec[k] != v for k, v in expected.items())):
        raise ValueError("Offline scope or admission changed")
    return spec


def tree_hash(directory):
    directory = journal.safe_path(directory)
    hashes = {}
    for path in sorted(directory.rglob("*")):
        if (path.is_symlink() or not (path.is_file() or path.is_dir())
                or path.is_file() and path.stat().st_nlink != 1):
            raise ValueError("Linked or nonregular source artifact")
        if path.is_file():
            hashes[path.relative_to(directory).as_posix()] = digest(path.read_bytes())
    return panel.sha256_json(hashes)


def validate_records(root, records):
    """Compatibility only. Raw provenance requires verified_bank/verify_bank."""
    expected = panel.candidate_rows(root)
    if not isinstance(records, list) or len(records) != 144:
        raise ValueError("Exactly 144 saved stages required")
    catalog, controls = workflow.families(root), score.controls(root)
    answers = {}
    for record, row in zip(records, expected):
        if not isinstance(record, dict) or set(record) != {"row", "result", "binding", "origin"}:
            raise ValueError("Unexpected bank record fields")
        result, binding = record["result"], record["binding"]
        if (record["row"] != row or not isinstance(result, dict) or set(result) != {"text"}
                or not isinstance(result["text"], str) or not result["text"].strip()
                or "<think>" in result["text"] or "</think>" in result["text"]):
            raise ValueError("Saved answer identity, order or final text changed")
        family = catalog[row["family_id"]][0]
        if (not isinstance(binding, dict) or set(binding) != {"case_version", "case_content_hash",
                "answer_sha256", "payload_sha256", "raw_sha256"}
                or binding["case_version"] != family["version"]
                or binding["case_content_hash"] != workflow.variant_hash(family, row["language"])
                or binding["answer_sha256"] != panel.sha256_json(result)
                or any(not isinstance(binding[k], str) or len(binding[k]) != 64
                    or any(c not in "0123456789abcdef" for c in binding[k])
                    for k in ("payload_sha256", "raw_sha256"))):
            raise ValueError("Saved answer/version/hash binding changed")
        answers[workflow.answer_key(row)] = deepcopy(result)
    if len(answers) != 144:
        raise ValueError("Missing or duplicate saved stage")
    for record in records:
        payload = workflow.request_context(root, record["row"], catalog, controls, answers)["payload"]
        if digest(guard._json_bytes(payload)) != record["binding"]["payload_sha256"]:
            raise ValueError("Saved prompt/model/history changed")
    return answers


def records_from_verified_state(root, directory, core):
    """Internal extraction only, after frozen replay and external source pins."""
    imports = {workflow.answer_key(r["row"]): r for r in journal.read(directory / "imports.json")}
    events = {}
    for event in sorted((directory / "events").iterdir()):
        reservation = journal.read(event / "reservation.json")
        row = reservation["row"]
        if row is not None and row["kind"] == "candidate":
            events[workflow.answer_key(row)] = (event, row)
    upstream = panel.saved.plan(root)
    catalog = workflow.families(root)
    records = []
    for row in panel.candidate_rows(root):
        key = workflow.answer_key(row)
        result = deepcopy(core.answers[key])
        if key in imports:
            old = imports[key]
            if old["result"] != result:
                raise ValueError("Upstream answer differs")
            binding = deepcopy(old["binding"])
            origin = {"kind": "upstream_import", "source_row": old["row"],
                "source_protocol_sha256": upstream["source_protocol_sha256"],
                "source_tree_sha256": upstream["source_sha256"],
                "source_bank_sha256": upstream["source_bank"]["sha256"]}
        else:
            event, saved_row = events[key]
            if core.outcomes[saved_row["sequence"]]["status"] != "accepted":
                raise ValueError("Rejected candidate cannot enter the bank")
            capture = event / "capture"
            raw = (capture / "0001.raw.bin").read_bytes()
            if workflow.decode_candidate(json.loads(raw), row["provider"], row["model"]) != result:
                raise ValueError("Candidate raw content differs")
            family = catalog[row["family_id"]][0]
            binding = {"case_version": family["version"],
                "case_content_hash": workflow.variant_hash(family, row["language"]),
                "answer_sha256": panel.sha256_json(result), "raw_sha256": digest(raw),
                "payload_sha256": digest((capture / "0001.payload.json").read_bytes())}
            origin = {"kind": "s54_candidate", "event": event.name, "source_row": saved_row,
                "capture_sha256": digest((capture / "0001.capture.json").read_bytes()),
                "reservation_sha256": digest((event / "reservation.json").read_bytes())}
        records.append({"row": deepcopy(row), "result": result, "binding": binding, "origin": origin})
    validate_records(root, records)
    return records


def verified_bank(root):
    spec = plan(root)
    directory = root / spec["source_directory"]
    freeze = panel.read_json(root / "config/mixed_live_s54_frozen_v1.json")
    if (freeze != live.snapshot(root) or panel.sha256_json(freeze) != spec["source_protocol_sha256"]
            or tree_hash(directory) != spec["source_tree_sha256"]):
        raise ValueError("Source pin or frozen implementation changed")
    checked, core, _ = source.restore(root, directory, spec["source_protocol_sha256"])
    if checked["mode"] != "live" or checked["answer_stages_present"] != 144:
        raise ValueError("Complete live answer bank required")
    records = records_from_verified_state(root, directory, core)
    if tree_hash(directory) != spec["source_tree_sha256"]:
        raise ValueError("Source changed during inspection")
    return {"version": VERSION, "mode": "saved_live_answers_not_new_judgments",
        "source_protocol_sha256": spec["source_protocol_sha256"],
        "source_tree_sha256": spec["source_tree_sha256"], "answers": records}


def verify_bank(root, bank):
    if bank != verified_bank(root):
        raise ValueError("Bank differs from raw-verified source; self-hashes are insufficient")
    return validate_records(root, bank["answers"])


def schedule(root):
    plan(root)
    rows = deepcopy([r for r in panel.schedule(root) if r["kind"] == "judge"])
    for sequence, row in enumerate(rows, 1):
        row["sequence"] = sequence
    if len(rows) != 324 or len({workflow.judgment_key(r) for r in rows}) != 324:
        raise ValueError("Judge-only schedule differs")
    return rows


def request_context(root, row, catalog, controls, answers):
    if row not in schedule(root):
        raise ValueError("Only declared judge rows are supported")
    context = panel.request_context(root, row, catalog, controls, answers)
    context["payload"]["system_instruction"] = draft.instruction(root, context["packet"])
    context["payload"]["response_format"]["schema"] = draft.schema(context["packet"])
    return context


def readiness(root, bank):
    """Verify raw provenance before exporting metadata; never expose answer text."""
    answers = verify_bank(root, bank)
    rows, cells = schedule(root), live.policy.reporting_manifest(root)["conversations"]
    catalog, controls = workflow.families(root), score.controls(root)
    payloads, contracts, first = {}, {}, {}
    for row in rows:
        context = request_context(root, row, catalog, controls, answers)
        hashed = digest(guard._json_bytes(context["payload"]))
        payloads[str(row["sequence"])] = hashed
        contracts[str(row["sequence"])] = draft.contract(context["packet"])
        key = workflow.judgment_key({**row, "repeat": False})
        if row["repeat"] and first[key] != hashed:
            raise ValueError("Repeated payload differs")
        first[key] = hashed
    return {"version": VERSION, "status": "offline_verified_not_live_ready",
        "live_calls": 0, "live_call_allowance": 0, "live_budget_usd": None,
        "live_execution_available": False, "new_candidate_calls": 0,
        "bank_sha256": panel.sha256_json(bank),
        "source_protocol_sha256": bank["source_protocol_sha256"],
        "source_tree_sha256": bank["source_tree_sha256"],
        "source_raw_replay_verified": True, "verified_answer_stages": len(answers),
        "upstream_imports": sum(r["origin"]["kind"] == "upstream_import" for r in bank["answers"]),
        "s54_candidate_stages": sum(r["origin"]["kind"] == "s54_candidate" for r in bank["answers"]),
        "proposed_control_judgments": 36, "proposed_first_judgments": 144,
        "proposed_repeat_judgments": 144, "proposed_maximum_judge_calls": len(rows),
        "fresh_control_gate_required": True, "historical_judgments_reused": False,
        "repeats_have_identical_payloads": True, "expected_conversations": len(cells),
        "review_held_conversations": sum(c["comparative_review_hold"] for c in cells),
        "schedule_sha256": panel.sha256_json(rows), "manifest_sha256": panel.sha256_json(cells),
        "request_set_sha256": panel.sha256_json(payloads), "contracts_sha256": panel.sha256_json(contracts),
        "files": {p: digest((root / p).read_bytes()) for p in FILES},
        "score_version": score.VERSION, "arithmetic_sha256": panel.sha256_json(score.ARITHMETIC),
        "numeric_scores": False, "clinical_validation": False, "new_cases": 0,
        "raw_answer_or_explanation_text_exported": False, "automatic_retries": 0, "resume_allowed": False,
        "answer_metadata": [{k: deepcopy(r[k]) for k in ("row", "binding", "origin")} for r in bank["answers"]],
        "remaining": ["new versioned execution engine and prospective freeze",
            "fresh pricing and bounded owner disclosure/spend approval", "fresh controls before development judging",
            "judge-only first and repeat results; no pooling with S55", "clinical and bilingual review deferred"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-bank", required=True, type=Path,
                        help="Private bank; public metadata only is printed")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(readiness(root, panel.read_json(args.verify_bank)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
