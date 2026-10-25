"""Offline mixed saved/new-answer schedule. No credentials, HTTP or live command.

`verify` reads the pinned private S45/S46 captures through their frozen replay.
The in-memory rehearsal consumes supplied fixture bytes only. It is not a
durable execution engine, a new budget, or permission to send generated payloads.
"""

import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from scripts import judge_saved_bank_s48 as saved, medication_boundary_s50 as boundary

old, workflow, score, guard = saved.old, saved.workflow, saved.score, saved.guard
read_json, sha256_json = saved.read_json, saved.sha256_json
VERSION = "s51-mixed-panel-offline-v1"
PLAN = "config/mixed_panel_s51_v1.json"
FAMILIES = ["HC-MT-" + s for s in (
    "TRIAGE-019", "TRIAGE-020", "REASON-015", "REASON-014", "MEDSAFE-013",
    "MEDSAFE-014", "REASON-020", "REASON-022", "MEDSAFE-019")]
HOLD = "HC-MT-MEDSAFE-013"


def plan(root):
    value = read_json(root / PLAN)
    expected = {
        "version": VERSION, "status": "offline_design_not_live_protocol", "families": FAMILIES,
        "languages": ["en", "zh-Hans"], "candidate_models": old.plan(root)["candidate_models"],
        "judge_models": [saved.MODEL], "source_pins_from": saved.PLAN,
        "imported_answer_stages": 16, "expected_conversations": 72, "new_candidate_stages": 128,
        "control_judgments": 36, "first_development_judgments": 144,
        "repeat_development_judgments": 144, "proposed_new_requests": 452,
        "live_call_allowance": 0, "live_budget_usd": None, "automatic_retries": 0, "resume_allowed": False,
        "judge_draft": {"instruction_schema": "s47_observation_completeness", "max_output_tokens": 32768,
            "thinking_level": "medium", "sampling": "provider_defaults_unpinned",
            "status": "offline_draft_pending_prospective_decision"},
        "review_holds": {HOLD: {"initial": {"2": ["H137"]}, "update": {"3": ["H136", "H140"]},
            "additional_advice": ["H141"], "comparative_claims": "held_no_cell_removal_or_reweighting"}}}
    if (guard._json_bytes(value) != guard._json_bytes(expected)
            or set(FAMILIES) != {f["family_id"] for f in workflow.design(root)["development"]}):
        raise ValueError("Offline design changed; no implicit roster or authorization expansion")
    return value


def candidate_rows(root):
    spec = plan(root)
    rows = [r for r in workflow.schedule(root) if r["kind"] == "candidate"
            and r["family_id"] in spec["families"] and r["model"] in spec["candidate_models"]]
    order = {fid: i for i, fid in enumerate(spec["families"])}
    return sorted(rows, key=lambda r: (order[r["family_id"]], spec["languages"].index(r["language"]),
        spec["candidate_models"].index(r["model"]), score.STAGES.index(r["stage"])))


def validate_import_records(root, records):
    """Check compatibility, NOT raw provenance. Real imports must use verified_source."""
    expected = {workflow.answer_key(r): r for r in candidate_rows(root) if r["family_id"] == HOLD}
    answers, bindings = {}, {}
    catalog, controls = workflow.families(root), score.controls(root)
    for record in records:
        if set(record) != {"row", "result", "binding"}:
            raise ValueError("Unexpected saved record fields")
        row, result, binding = record["row"], record["result"], record["binding"]
        key = workflow.answer_key(row)
        if (key not in expected or key in answers or set(row) != set(expected[key])
                or type(row["sequence"]) is not int or row["sequence"] < 1
                or any(row[k] != v for k, v in expected[key].items() if k != "sequence")
                or set(result) != {"text"} or not isinstance(result["text"], str)
                or not result["text"].strip() or "<think>" in result["text"] or "</think>" in result["text"]):
            raise ValueError("Duplicate, incompatible or incomplete saved answer")
        family = catalog[row["family_id"]][0]
        if (set(binding) != {"case_version", "case_content_hash", "answer_sha256", "raw_sha256", "payload_sha256"}
                or binding["case_version"] != family["version"]
                or binding["case_content_hash"] != workflow.variant_hash(family, row["language"])
                or binding["answer_sha256"] != sha256_json(result)
                or any(not isinstance(binding[k], str) or not re.fullmatch(r"[a-f0-9]{64}", binding[k])
                       for k in ("raw_sha256", "payload_sha256"))):
            raise ValueError("Saved answer/version/hash binding mismatch")
        answers[key], bindings[key] = deepcopy(result), binding
    if set(answers) != set(expected) or len(records) != 16:
        raise ValueError("Exactly the 16 saved stages are required; missing imports are not regenerated")
    for key, row in expected.items():
        payload = workflow.request_context(root, row, catalog, controls, answers)["payload"]
        if hashlib.sha256(guard._json_bytes(payload)).hexdigest() != bindings[key]["payload_sha256"]:
            raise ValueError("Saved prompt/model/history incompatible with new candidate policy")
    return answers


def verified_source(root):
    """Rehydrate the exact historical bank, including all upstream raw captures."""
    boundary.audit(root)
    value = saved.source(root)
    saved.verify_source(value, saved.plan(root), "live")
    validate_import_records(root, value["bank"]["answers"])
    return value


def schedule(root):
    spec = plan(root)
    candidates = [r for r in candidate_rows(root) if r["family_id"] != HOLD]
    controls = [r for r in workflow.schedule(root) if r["block"] == "control" and r["model"] == saved.MODEL]
    development = []
    for candidate in candidate_rows(root):
        development.append({**candidate, "kind": "judge", "provider": "gemini", "model": saved.MODEL})
    rows = deepcopy(candidates + controls + development + [{**r, "repeat": True} for r in development])
    for sequence, row in enumerate(rows, 1):
        row["sequence"] = sequence
    if (len(rows) != spec["proposed_new_requests"] or len(candidates) != 128
            or len(controls) != 36 or len(development) != 144
            or len({workflow.judgment_key(r) for r in rows if r["kind"] == "judge"}) != 324):
        raise ValueError("Duplicate or missing schedule cells")
    return rows


def conversation_manifest(root):
    spec, catalog = plan(root), workflow.families(root)
    return [{"family_id": fid, "language": lang, "candidate_model": model,
             "case_version": catalog[fid][0]["version"],
             "case_content_hash": workflow.variant_hash(catalog[fid][0], lang),
             "answer_stage_origins": {stage: "imported" if fid == HOLD else "new" for stage in score.STAGES},
             "comparative_review_hold": fid in spec["review_holds"]}
            for fid in spec["families"] for lang in spec["languages"] for model in spec["candidate_models"]]


def request_context(root, row, catalog, controls, answers):
    context = workflow.request_context(root, row, catalog, controls, answers)
    if row["kind"] == "judge":
        payload = context["payload"]
        payload["system_instruction"] = saved.draft.instruction(root, context["packet"])
        payload["response_format"]["schema"] = saved.draft.schema(context["packet"])
        payload["generation_config"] = {"max_output_tokens": 32768, "thinking_level": "medium"}
    return context


def readiness(root, *, verify_private=False):
    """Public metadata only. Does not claim that future answers or a live runner exist."""
    spec, rows, cells = plan(root), schedule(root), conversation_manifest(root)
    prior = boundary.audit(root)
    value = verified_source(root) if verify_private else None
    paths = (PLAN, "scripts/mixed_panel_s51.py", "tests/test_mixed_panel_s51.py")
    return {"version": VERSION, "mode": "offline_readiness", "live_calls": 0,
        "live_execution_available": False, "live_authorization": False, "live_budget_usd": None,
        "s50_protocol_sha256": prior["protocol_sha256"],
        "files": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
        "schedule_sha256": sha256_json(rows), "manifest_sha256": sha256_json(cells),
        "expected_conversations": len(cells), "expected_answer_stages": 144,
        "imported_answer_stages_required": 16, "private_source_verified": value is not None,
        "verified_imported_stages": 16 if value else 0,
        "source": {k: value[k] for k in ("source_sha256", "source_protocol_sha256", "bank_sha256")} if value else None,
        "proposed_new_requests": len(rows), "new_candidate_stages": 128,
        "control_judgments": 36, "first_development_judgments": 144, "repeat_development_judgments": 144,
        "candidate_models": spec["candidate_models"], "judge_models": spec["judge_models"],
        "review_held_conversations": sum(c["comparative_review_hold"] for c in cells),
        "review_holds": spec["review_holds"], "judge_draft": spec["judge_draft"], "conversations": cells,
        "numeric_scores": False, "clinical_validation": False, "new_cases": 0,
        "remaining": ["versioned decision on disputed criteria and uniform prospective judge policy",
                      "durable mixed-run capture/replay and fresh freeze",
                      "current pricing verification, new spending policy and explicit paid-call approval"]}


class Rehearsal:
    """In-memory fixture consumer. Deliberately no transport, keys, persistence or resume."""

    def __init__(self, root, records, *, mode, fixture_threshold_usd="1.00"):
        if mode != "offline_fixture":
            raise ValueError("No live execution in S51")
        threshold = Decimal(fixture_threshold_usd)
        if not threshold.is_finite() or threshold <= 0 or threshold.as_tuple().exponent < -2:
            raise ValueError("Invalid simulated threshold")
        self.root, self.rows = root, schedule(root)
        self.catalog, self.controls = workflow.families(root), score.controls(root)
        self.answers = validate_import_records(root, records)
        self.contexts, self.judgments, self.outcomes, self.first_payloads = {}, {}, {}, {}
        self.accounts, self.closed_lanes = [], {}
        self.index, self.monitored, self.unknown = 0, 0, 0
        self.threshold = int(threshold * old.TICKS_PER_USD)
        self.pending, self.terminal = None, None

    def gate(self):
        return old.single_judge_gate(self.root, self.rows, self.judgments, self.contexts, saved.MODEL)

    def skip_reason(self, row):
        if old.lane(row) in self.closed_lanes:
            return "model_lane_closed"
        if row["kind"] == "candidate":
            if workflow.answer_key(row) in self.answers:
                raise ValueError("Never regenerate an imported or accepted stage")
            if row["stage"] == "update" and workflow.answer_key(row, "initial") not in self.answers:
                return "initial_answer_missing"
        else:
            if row["block"] == "development":
                if any(workflow.answer_key(row, stage) not in self.answers for stage in score.STAGES):
                    return "candidate_conversation_missing"
                if not self.gate()["pass"]:
                    return "judge_control_gate_not_passed"
            if row["repeat"] and workflow.judgment_key({**row, "repeat": False}) not in self.judgments:
                return "first_judgment_missing"
        return None

    def prepare(self):
        if self.pending is not None:
            raise ValueError("A supplied fixture reply is still pending; no duplicate dispatch")
        if self.terminal:
            return None
        while self.index < len(self.rows):
            row = self.rows[self.index]
            reason = self.skip_reason(row)
            if reason:
                self.outcomes[row["sequence"]] = {"status": "skipped", "reason": reason}
                self.index += 1
                continue
            try:
                context = request_context(self.root, row, self.catalog, self.controls, self.answers)
                body = guard._json_bytes(context["payload"])
                if row["kind"] == "judge":
                    key = workflow.judgment_key({**row, "repeat": False})
                    if row["repeat"] and body != self.first_payloads[key]:
                        raise ValueError("Identical-request repeat payload drift")
                    self.first_payloads.setdefault(key, body)
                self.contexts[row["sequence"]] = context
                self.pending = deepcopy(row)
                return {"row": deepcopy(row), "payload": deepcopy(context["payload"])}
            except Exception:
                self.terminal = "local_context_failure"
                raise
        self.terminal = "schedule_complete"
        return None

    def record(self, raw_bytes):
        if self.pending is None or self.terminal:
            raise ValueError("No pending fixture reply")
        # An unexpected parser/accounting/local failure cannot consume a second
        # supplied reply as though it were a retry of this same attempt.
        self.terminal = "local_reply_failure"
        outcome = self._record(raw_bytes)
        if self.terminal == "local_reply_failure":
            self.terminal = None
        return outcome

    def _record(self, raw_bytes):
        row = self.pending
        context = self.contexts[row["sequence"]]
        spec = next(v for v in workflow.design(self.root)["candidates"] + workflow.design(self.root)["judges"]
                    if v["provider"] == row["provider"] and v["model"] == row["model"])
        raw, result = None, None
        try:
            raw = saved.capture.strict_json(raw_bytes)
        except (ValueError, TypeError, UnicodeDecodeError):
            pass
        account = saved.previous.account(raw, spec, context["payload"])
        self.accounts.append(account)
        delta = old.monitoring_delta(account, row["provider"])["delta_ticks"]
        self.monitored += delta or 0
        if delta is None:
            self.unknown += 1
            category = "unknown_charge"
            self.terminal = category
        else:
            try:
                result = (workflow.decode_candidate(raw, row["provider"], row["model"]) if row["kind"] == "candidate"
                          else score.decode(raw, row["provider"], row["model"], context["packet"]))
                category = "accepted"
            except (ValueError, KeyError, TypeError, IndexError, AttributeError):
                category = "response_validation"
                self.closed_lanes[old.lane(row)] = category
            if self.monitored >= self.threshold:
                self.terminal = "spend_threshold_reached"
        if category == "accepted":
            if row["kind"] == "candidate":
                self.answers[workflow.answer_key(row)] = result
            else:
                self.judgments[workflow.judgment_key(row)] = result
        outcome = {"status": "accepted" if category == "accepted" else "rejected", "category": category}
        self.outcomes[row["sequence"]] = outcome
        self.index += 1
        self.pending = None
        return deepcopy(outcome)

    def report(self):
        cells = conversation_manifest(self.root)
        for cell in cells:
            key = cell["family_id"], cell["language"], cell["candidate_model"]
            cell["answer_stages_present"] = [s for s in score.STAGES if (*key, s) in self.answers]
            for repeat, label in ((False, "first"), (True, "repeat")):
                cell[label + "_judgment_stages_present"] = [s for s in score.STAGES if any(
                    r["block"] == "development" and r["kind"] == "judge" and r["repeat"] == repeat
                    and workflow.answer_key(r) == (*key, s)
                    and workflow.judgment_key(r) in self.judgments for r in self.rows)]
        return {"version": VERSION, "mode": "offline_fixture", "simulation_only": True,
            "terminal": self.terminal, "expected_conversations": 72, "conversations": cells,
            "expected_answer_stages": 144, "answer_stages_present": len(self.answers),
            "proposed_new_requests": 452, "simulated_attempts": len(self.accounts),
            "outcomes": dict(Counter(v["status"] for v in self.outcomes.values())),
            "simulated_monitoring_usd": format(Decimal(self.monitored) / old.TICKS_PER_USD, "f"),
            "unknown_simulated_charge_attempts": self.unknown, "control_gate": self.gate(),
            "numeric_scores": False, "clinical_validation": False, "live_calls": 0,
            "automatic_retries": 0, "resume_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "verify"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(readiness(root, verify_private=args.command == "verify"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
