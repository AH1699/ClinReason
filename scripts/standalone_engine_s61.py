"""Offline state machine for the S60 inputs. No network or credential interface."""

from collections import Counter
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

from scripts import standalone_pilot_s60 as pilot
from scripts import transport_s46 as capture
from benchmark import workflow_s38 as workflow
from benchmark.spending_s40 import monitoring_delta, TICKS_PER_USD
from benchmark.multiturn import variant_id

score, guard = pilot.score, capture.guard
VERSION = "s61-standalone-offline-integration-v1"
PLAN = "config/standalone_rehearsal_s61_v1.json"


def policy(root):
    value = pilot.load_json(pilot.public_path(Path(root), PLAN))
    expected = {"version": VERSION, "mode": "offline_transport_fixture", "parent": pilot.MANIFEST,
        "maximum_requests": 480,
        "judge_settings": {"max_output_tokens": 32768, "thinking_level": "medium", "service_tier": "standard"},
        "candidate_settings": "unchanged_s38_visible_text_history",
        "control_admission": "all_96_format_valid_records_for_fixture_engineering_only",
        "clinical_control_gate": "not_selected_or_authorized_by_this_rehearsal",
        "control_disagreement": "retain_diagnostics_no_relabel_or_retry",
        "known_cost_invalid_candidate": "close_only_that_candidate_model_lane",
        "known_cost_invalid_judge": "stop_no_retry", "unknown_delivery_or_cost": "global_stop",
        "max_in_flight": 1, "automatic_retries": 0, "resume_allowed": False, "live_call_allowance": 0,
        "live_budget_usd": None, "pricing_status": "historical_rates_for_simulated_accounting_only_not_current_quote",
        "reporting": "all_64_cells_first_repeat_separate_missing_not_zero_all_clinically_held"}
    if guard._json_bytes(value) != guard._json_bytes(expected):
        raise ValueError("Changed offline integration policy; no implicit live admission")
    return value


def answer_id(cell_id, stage):
    return "candidate__" + cell_id + "__" + stage


def first_id(row):
    if row["kind"] == "control_repeat":
        return "control_first__" + row["control_key"]
    if row["kind"] == "judge_repeat":
        return "judge_first__" + row["cell_id"] + "__" + row["stage"]
    return row["id"]


class Engine:
    def __init__(self, root, *, mode, fixture_threshold_usd="1.00"):
        if mode != "offline_transport_fixture":
            raise ValueError("S61 has no live engine")
        if not isinstance(fixture_threshold_usd, str):
            raise ValueError("Explicit simulated USD threshold required")
        threshold = Decimal(fixture_threshold_usd)
        if not threshold.is_finite() or threshold <= 0 or threshold.as_tuple().exponent < -2:
            raise ValueError("Invalid simulated threshold")
        self.root = Path(root)
        self.policy, self.parent = policy(self.root), pilot.verify(self.root)
        self.spec, self.catalog, _, _ = pilot.inputs(self.root)
        self.controls, self.control_records = pilot.controls(self.root, self.catalog)
        cells, self.rows = pilot.schedule(self.spec, self.control_records)
        self.cells = {c["cell_id"]: c for c in cells}
        self.threshold = int(threshold * TICKS_PER_USD)
        self.index, self.monitored, self.unknown = 0, 0, 0
        self.pending, self.terminal = None, None
        self.outcomes, self.answers, self.judgments, self.contexts, self.first_payloads = {}, {}, {}, {}, {}
        self.accounts, self.closed_candidates = [], set()
        self.model_specs = {(s["provider"], s["model"]): s for s in
                            workflow.design(self.root)["candidates"] + workflow.design(self.root)["judges"]}

    def provider(self, row):
        return (self.cells[row["cell_id"]]["candidate"] if row["kind"] == "candidate"
                else {k: self.spec["judge_proposal"][k] for k in ("provider", "model")})

    def stage_answer(self, cell, stage):
        row_id = answer_id(cell["cell_id"], stage)
        record = self.answers[row_id]
        family = self.catalog[cell["family_id"]]["family"]
        expected = {"cell_id": cell["cell_id"], "stage": stage, **cell["candidate"],
                    "case_content_hash": pilot.variant_hash(family, cell["language"]),
                    "answer_sha256": pilot.sha256_json(record["answer"]),
                    "payload_sha256": pilot.sha256_json(self.contexts[row_id]["payload"])}
        if record["binding"] != expected or self.outcomes.get(row_id, {}).get("status") != "accepted":
            raise ValueError("Candidate answer identity/version/request binding changed")
        return record["answer"]["text"]

    def candidate_packet(self, cell, stage):
        entry = self.catalog[cell["family_id"]]
        family, lang = entry["family"], cell["language"]
        initial = self.stage_answer(cell, "initial")
        if stage == "update":
            full = workflow.full_packet(family, entry["anchors"], lang, initial, self.stage_answer(cell, "update"))
        else:
            # Construct only the observed stage: no fabricated follow-up answer.
            turn = family["variants"][lang]["turns"][0]
            full = pilot.attach_anchors({"case_id": variant_id(family, lang), "language": lang,
                "case_content_hash": pilot.variant_hash(family, lang),
                "transcript": [{"role": "user", "content": turn["user"]}, {"role": "assistant", "content": initial}],
                "turn_labels": [{k: deepcopy(turn[k]) for k in ("stage_id", "critical_requirements", "critical_errors")}]}, entry["anchors"])
        return score.stage_packet(full, stage, entry["anchors"]["levels"])

    def context(self, row):
        model = self.provider(row)
        if row["kind"] == "candidate":
            cell = self.cells[row["cell_id"]]
            family = self.catalog[cell["family_id"]]["family"]
            initial = self.stage_answer(cell, "initial") if row["stage"] == "update" else None
            messages = pilot.candidate_history(family, cell["language"], row["stage"], initial)
            payload = guard.candidate_payload(model["provider"], model["model"], messages,
                (self.root / self.spec["candidate_instruction"]).read_text())
            if model["provider"] == "minimax":
                payload["thinking"] = {"type": "adaptive"}
                if model["model"] == "MiniMax-M3.1-Flash":
                    payload.pop("service_tier")
                    payload["reasoning_effort"] = "max"
            return {**model, "payload": payload, "packet": None}
        packet = (deepcopy(self.controls[row["control_key"]]) if row["kind"].startswith("control")
                  else self.candidate_packet(self.cells[row["cell_id"]], row["stage"]))
        judge = pilot.judge_input(self.root, packet)
        if "control_key" in row and pilot.sha256_json(judge) != row["judge_input_sha256"]:
            raise ValueError("Frozen control input changed")
        settings = self.policy["judge_settings"]
        payload = {"model": model["model"], "system_instruction": judge["instruction"],
            "input": json.dumps(packet, ensure_ascii=False), "store": False,
            "service_tier": settings["service_tier"],
            "generation_config": {k: settings[k] for k in ("max_output_tokens", "thinking_level")},
            "response_format": {"type": "text", "mime_type": "application/json", "schema": judge["schema"]}}
        return {**model, "payload": payload, "packet": packet}

    def prepare(self):
        if self.pending is not None:
            raise ValueError("One attempt is already pending; no duplicate dispatch")
        if self.terminal:
            return None
        self.terminal = "local_context_failure"
        while self.index < len(self.rows):
            row = self.rows[self.index]
            reason = None
            if row["kind"] == "candidate" and self.provider(row)["model"] in self.closed_candidates:
                reason = "candidate_model_lane_closed"
            elif any(self.outcomes.get(d, {}).get("status") != "accepted" for d in row["dependencies"]):
                reason = "accepted_dependency_missing"
            if reason:
                self.outcomes[row["id"]] = {"status": "skipped", "reason": reason}
                self.index += 1
                continue
            if not row["kind"].startswith("control") and not self.control_readout()["structurally_complete"]:
                self.terminal = "control_records_incomplete"
                return None
            context = self.context(row)
            if row["kind"] != "candidate":
                original = first_id(row)
                body = guard._json_bytes(context["payload"])
                if original != row["id"] and self.first_payloads.get(original) != body:
                    raise ValueError("Repeat request bytes changed")
                self.first_payloads.setdefault(original, body)
            self.contexts[row["id"]] = context
            self.pending = deepcopy(row)
            self.terminal = None
            return {"row": deepcopy(row), "context": deepcopy(context)}
        self.terminal = "schedule_complete"
        return None

    def decode(self, raw):
        context = self.contexts[self.pending["id"]]
        return (workflow.decode_candidate(raw, context["provider"], context["model"])
                if self.pending["kind"] == "candidate" else
                score.decode(raw, context["provider"], context["model"], context["packet"]))

    def consume(self, result, raw_bytes):
        if self.pending is None or self.terminal:
            raise ValueError("No pending attempt")
        self.terminal = "local_reply_failure"
        row, context = self.pending, self.contexts[self.pending["id"]]
        account = result["accounting"]
        self.accounts.append(deepcopy(account))
        delta = monitoring_delta(account, context["provider"])["delta_ticks"]
        self.monitored += delta or 0
        category = result["category"]
        if delta is None:
            self.unknown += 1
            self.terminal = "unknown_delivery_or_cost"
        else:
            self.terminal = None
            if not result["accepted"]:
                if row["kind"] == "candidate":
                    self.closed_candidates.add(context["model"])
                else:
                    self.terminal = "invalid_judge_reply"
        if result["accepted"]:
            parsed = self.decode(capture.strict_json(raw_bytes))
            if parsed != result["result"] or delta is None:
                raise ValueError("Capture/decoder/accounting mismatch")
            if row["kind"] == "candidate":
                cell = self.cells[row["cell_id"]]
                family = self.catalog[cell["family_id"]]["family"]
                self.answers[row["id"]] = {"answer": parsed, "binding": {
                    "cell_id": cell["cell_id"], "stage": row["stage"], **cell["candidate"],
                    "case_content_hash": pilot.variant_hash(family, cell["language"]),
                    "answer_sha256": pilot.sha256_json(parsed), "payload_sha256": pilot.sha256_json(context["payload"])}}
            else:
                self.judgments[row["id"]] = parsed
        if not self.terminal and self.monitored >= self.threshold:
            self.terminal = "simulated_spend_threshold_reached"
        outcome = {"status": "accepted" if result["accepted"] else "rejected", "category": category}
        self.outcomes[row["id"]] = outcome
        self.pending = None
        self.index += 1
        return deepcopy(outcome)

    def control_readout(self):
        ids = [r["id"] for r in self.rows[:96]]
        accepted = sum(i in self.judgments for i in ids)
        unsafe, mismatches, repeats, non_unsafe_errors, stages = 0, [], 0, [], []
        records = {r["key"]: r for r in self.control_records}
        for row in self.rows[:96]:
            judgment = self.judgments.get(row["id"])
            record = records[row["control_key"]]
            if judgment is not None and record["profile"] != "unsafe" and judgment["critical_errors"]:
                non_unsafe_errors.append(row["id"])
            stages.append({"job_id": row["id"], "profile": record["profile"],
                "criterion_statuses": [r["status"] for r in judgment["criterion_assessments"]] if judgment else None,
                "critical_errors": [{k: e[k] for k in ("stage_id", "error_id", "severity")}
                                    for e in judgment["critical_errors"]] if judgment else None,
                "observations": [{k: o[k] for k in ("dimension", "decision")}
                                 for o in judgment.get("dimension_observations", [])] if judgment else None})
        for record in self.control_records:
            first = self.judgments.get("control_first__" + record["key"])
            repeat = self.judgments.get("control_repeat__" + record["key"])
            if first is not None and repeat is not None:
                repeats += workflow.vector(first) == workflow.vector(repeat)
            if first is not None and record["hypothesized_error_id"] is not None:
                found = any(e["error_id"] == record["hypothesized_error_id"] for e in first["critical_errors"])
                unsafe += found
                if not found:
                    mismatches.append(record["key"])
        return {"expected_records": 96, "accepted_records": accepted, "structurally_complete": accepted == 96,
            "hypothesized_unsafe_errors": 16, "observed_unsafe_error_matches": unsafe,
            "unsafe_hypothesis_mismatches": mismatches, "expected_repeat_stage_pairs": 32,
            "matching_repeat_criterion_error_vectors": repeats,
            "non_unsafe_records_with_errors": non_unsafe_errors, "stage_results": stages,
            "clinical_gate": "not_selected", "numeric_order_gate": False,
            "meaning": "Fixture engineering admission only; semantic observations are not clinical truth"}

    def report(self):
        cells = []
        pairs, equal_points, same_vectors, pass_changes = 0, 0, 0, []
        for cid, original in self.cells.items():
            cell = deepcopy(original)
            cell["answer_stages_present"] = [s for s in score.STAGES if answer_id(cid, s) in self.answers]
            for phase in ("first", "repeat"):
                judgments = {s: deepcopy(self.judgments.get("judge_" + phase + "__" + cid + "__" + s)) for s in score.STAGES}
                cell[phase] = {"judgments": judgments, "score": None}
                if all(judgments.values()):
                    entry = self.catalog[cell["family_id"]]
                    full = workflow.full_packet(entry["family"], entry["anchors"], cell["language"],
                                                self.stage_answer(cell, "initial"), self.stage_answer(cell, "update"))
                    _, value = score.combine(judgments["initial"], judgments["update"], full,
                                             {"version": score.VERSION, **score.ARITHMETIC})
                    cell[phase]["score"] = value
            a, b = cell["first"]["score"], cell["repeat"]["score"]
            if a is not None and b is not None:
                pairs += 1
                equal_points += a["point_score"] is not None and a["point_score"] == b["point_score"]
                if a["provisional_pass"] is not None and b["provisional_pass"] is not None and a["provisional_pass"] != b["provisional_pass"]:
                    pass_changes.append(cid)
            for s in score.STAGES:
                a, b = cell["first"]["judgments"][s], cell["repeat"]["judgments"][s]
                same_vectors += a is not None and b is not None and workflow.vector(a) == workflow.vector(b)
            cells.append(cell)
        status = Counter(v["status"] for v in self.outcomes.values())
        return {"version": VERSION, "simulation_only": True, "live_calls": 0, "measured_model_scores": 0,
            "numeric_fixture_scores_only": True, "clinical_validation": False, "terminal": self.terminal,
            "proposed_requests": 480, "settled_fixture_attempts": len(self.accounts),
            "unresolved_reservations": int(self.pending is not None), "outcomes": dict(status),
            "unattempted_jobs": 480 - len(self.outcomes) - int(self.pending is not None),
            "unknown_simulated_cost_attempts": self.unknown,
            "simulated_monitoring_usd": format(Decimal(self.monitored) / TICKS_PER_USD, "f"),
            "closed_candidate_models": sorted(self.closed_candidates),
            "control_readout": self.control_readout(), "expected_conversations": 64, "conversations": cells,
            "repeat_summary": {"expected_conversation_pairs": 64, "complete_pairs": pairs,
                "matching_known_point_scores": equal_points, "expected_stage_pairs": 128,
                "matching_criterion_error_vectors": same_vectors, "pass_changed_cells": pass_changes},
            "reporting": deepcopy(self.spec["reporting"]), "automatic_retries": 0, "resume_allowed": False}
