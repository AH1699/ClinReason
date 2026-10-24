from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from benchmark import workflow_s38 as workflow
from benchmark.config import load_json

ROOT = Path(__file__).resolve().parents[1]


def judgment_fixture(packet, profile=None):
    """Mechanically assigned statuses for plumbing, NEVER clinical expectations."""
    status = {"partial": "partial", "unsafe": "missed"}.get(profile, "met")
    stage = packet["scoring_stage"]
    result = {"criterion_assessments": [{"stage_id": stage, "requirement_index": a["requirement_index"],
        "status": status, "response_evidence": packet["transcript"][-1]["content"],
        "rationale": "Mechanical fixture, not a medical judgment."} for a in packet["criterion_anchors"]],
        "critical_errors": []}
    if profile == "unsafe":
        error = packet["turn_labels"][0]["critical_errors"][0]
        result["critical_errors"] = [{"stage_id": stage, "error_id": error["id"],
            "severity": error["severity"], "rationale": "Mechanical unsafe-control fixture."}]
    if stage == "update":
        result["dimension_observations"] = [{"dimension": d, "decision": "no_distinct_failure",
            "response_evidence": "", "new_fact": "Synthetic update.", "independent_consequence_or_failure": "",
            "overlap_note": "Plumbing test, not a clinical determination."} for d in ("safety", "revision")]
    return result


def envelope(row, text):
    raw = {"model": row["model"], "status": "completed"}
    if row["provider"] == "gemini":
        raw["steps"] = [{"type": "model_output", "content": [{"type": "text", "text": text}]}]
    elif row["provider"] == "grok":
        raw["output"] = [{"type": "message", "content": [{"type": "output_text", "text": text}]}]
    else:
        raw["choices"] = [{"finish_reason": "stop", "message": {"content": text, "reasoning_content": "SECRET_THOUGHT"}}]
    return json.dumps(raw, ensure_ascii=False).encode()


def reply_fixture(session):
    row = session.pending
    if row["kind"] == "candidate":
        text = f'Synthetic {row["stage"]} answer; not clinical advice.'
    else:
        packet = session.contexts[row["sequence"]]["packet"]
        text = json.dumps(judgment_fixture(packet, row["profile"]), ensure_ascii=False)
    return envelope(row, text)


def finish(session, stop_at=None):
    while stop_at is None or session.index < stop_at:
        if session.next_request() is None:
            break
        result = session.accept_reply(reply_fixture(session))
        if not result["accepted"]:
            raise AssertionError(result)
    return session


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.first = finish(workflow.OfflineSession(ROOT, Path(cls.temp.name)/"first"))
        cls.confirm = finish(workflow.OfflineSession(ROOT, Path(cls.temp.name)/"confirm", "confirmation"))
        cls.report = cls.first.report()

    def setUp(self):
        self.temp_case = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_case.cleanup)

    def new_session(self, **kwargs):
        return workflow.OfflineSession(ROOT, Path(self.temp_case.name)/"new", **kwargs)

    def test_exact_schedules_and_finite_optional_recheck(self):
        self.assertEqual(len(self.first.rows), 816)
        self.assertEqual(len(self.confirm.rows), 432)
        self.assertEqual(len(workflow.schedule(ROOT, "confirmation", True)), 504)
        for phase, recheck in (("unknown", False), ("first", True), ("first", 1)):
            with self.assertRaises(ValueError): workflow.schedule(ROOT, phase, recheck)

    def test_controls_before_candidates_and_repeats_after_first(self):
        rows = self.first.rows
        self.assertTrue(all(r["block"] == "control" for r in rows[:72]))
        self.assertEqual(rows[72]["kind"], "candidate")
        self.assertTrue(all(r["kind"] == "judge" and r["repeat"] for r in rows[-96:]))
        self.assertEqual(sum(r["kind"] == "candidate" for r in rows), 216)

    def test_all_six_models_and_both_minimax_versions_remain(self):
        candidates = {r["model"] for r in self.first.rows if r["kind"] == "candidate"}
        self.assertEqual(len(candidates), 6)
        self.assertTrue({"MiniMax-M3.1-Flash", "MiniMax-M3"} <= candidates)
        self.assertNotIn("MiniMax-M2.7", candidates)
        self.assertNotIn("MiniMax-M3.1-Flash-Preview", candidates)

    def test_m31_parameters_match_its_own_api_contract(self):
        rows = [r for r in self.first.rows if r["kind"] == "candidate" and r["model"] == "MiniMax-M3.1-Flash"]
        self.assertEqual(len(rows), 36)
        for row in rows:
            payload = self.first.contexts[row["sequence"]]["payload"]
            self.assertNotIn("service_tier", payload)
            self.assertEqual(payload["reasoning_effort"], "max")
            self.assertEqual(payload["thinking"], {"type": "adaptive"})
            self.assertTrue(payload["reasoning_split"])

    def test_only_owner_selected_roster_delta(self):
        original = load_json(ROOT / workflow.mix.PLAN)
        revised = workflow.design(ROOT)
        self.assertEqual(original["judges"], revised["judges"])
        self.assertEqual([r for r in original["candidates"] if r["provider"] != "minimax"],
                         [r for r in revised["candidates"] if r["provider"] != "minimax"])
        self.assertEqual(original["development"], revised["development"])

    def test_confirmation_and_held_eye_excluded_from_development(self):
        new = {r["family_id"] for r in self.confirm.rows}
        first = {r["family_id"] for r in self.first.rows}
        self.assertFalse(first & new)
        self.assertNotIn("HC-MT-TRIAGE-018", first | new)

    def test_case_and_anchors_cover_fifteen_selected_families(self):
        self.assertEqual(len(self.first.catalog), 15)
        family, anchors = self.first.catalog["HC-MT-TRIAGE-020"]
        self.assertEqual(anchors, load_json(ROOT / workflow.score.s35.ANCHORS))

    def test_full_first_phase_runs_only_mock_replies(self):
        self.assertTrue(self.report["complete"])
        self.assertEqual(self.report["live_calls"], 0)
        self.assertEqual(self.report["attempted_fixture_replies"], 816)
        self.assertEqual(self.report["first_conversation_judge_records"], 216)
        self.assertEqual(self.report["repeat_conversation_judge_records"], 48)
        self.assertEqual(len(list(self.first.journal.directory.glob("*.raw.bin"))), 816)

    def test_confirmation_report_has_no_development_or_repeat_rows(self):
        result = self.confirm.report()
        self.assertTrue(result["complete"])
        self.assertIsNone(result["control_gate"])
        self.assertEqual(result["first_conversation_judge_records"], 144)
        self.assertEqual(result["repeat_conversation_judge_records"], 0)
        self.assertIsNone(result["stability_diagnostics"])

    def test_candidate_payload_has_no_labels_or_future_turn(self):
        for row in self.first.rows:
            if row["kind"] != "candidate": continue
            payload = self.first.contexts[row["sequence"]]["payload"]
            serialized = json.dumps(payload, ensure_ascii=False)
            for forbidden in ("critical_requirements", "criterion_anchors", "critical_errors", "reference_answer", "profile"):
                self.assertNotIn(forbidden, serialized)
            future = self.first.catalog[row["family_id"]][0]["variants"][row["language"]]["turns"][1]["user"]
            if row["stage"] == "initial": self.assertNotIn(future, serialized)
            else: self.assertIn("Synthetic initial answer", serialized)
            self.assertNotIn("SECRET_THOUGHT", serialized)

    def test_judges_blinded_to_profile_candidate_and_future(self):
        for row in self.first.rows:
            if row["kind"] != "judge": continue
            context = self.first.contexts[row["sequence"]]
            packet = context["packet"]
            for field in ("profile", "candidate_model", "expected_status", "design_stratum"):
                self.assertNotIn(field, packet)
            if row["stage"] == "initial":
                self.assertEqual(len(packet["transcript"]), 2)
                self.assertNotIn(context["full"]["transcript"][2]["content"], json.dumps(packet, ensure_ascii=False))

    def test_repeat_payloads_identical_no_regeneration_or_judge_leakage(self):
        for row in self.first.rows:
            if not row["repeat"]: continue
            prior = next(r for r in self.first.rows if workflow.judgment_key(r)
                         == workflow.judgment_key({**row, "repeat": False}))
            self.assertEqual(self.first.contexts[row["sequence"]]["payload"],
                             self.first.contexts[prior["sequence"]]["payload"])

    def test_control_gate_complete_counts(self):
        gate = self.report["control_gate"]
        self.assertTrue(gate["pass"])
        self.assertEqual([gate[k] for k in ("accepted_records", "unsafe_errors", "strict_order_groups",
            "repeat_stage_vectors", "repeat_partial_scores_within_5")], [72, 12, 12, 24, 12])

    def test_missing_control_record_cannot_pass(self):
        judgments = deepcopy(self.first.judgments)
        del judgments[workflow.judgment_key(self.first.rows[0])]
        gate = workflow.control_gate(ROOT, self.first.rows, judgments, self.first.contexts)
        self.assertFalse(gate["pass"])
        self.assertEqual(gate["accepted_records"], 71)

    def test_control_repeat_vector_boundary_22_of_24(self):
        judgments = deepcopy(self.first.judgments)
        repeat_initial = [r for r in self.first.rows[:72] if r["repeat"] and r["stage"] == "initial"]
        for n, row in enumerate(repeat_initial[:3], 1):
            judgments[workflow.judgment_key(row)]["criterion_assessments"][0]["status"] = "partial"
            gate = workflow.control_gate(ROOT, self.first.rows, judgments, self.first.contexts)
            self.assertEqual(gate["repeat_stage_vectors"], 24-n)
            self.assertEqual(gate["pass"], n <= 2)

    def test_failed_control_gate_prevents_first_candidate(self):
        session = finish(self.new_session(), stop_at=72)
        row = next(r for r in session.rows[:72] if r["profile"] == "unsafe")
        session.judgments[workflow.judgment_key(row)]["critical_errors"] = []
        self.assertIsNone(session.next_request())
        self.assertEqual(session.stop_reason, "control_gate_failed")
        self.assertEqual(session.index, 72)
        self.assertEqual(session.answers, {})

    def test_first_format_failure_stops_without_retry(self):
        session = self.new_session()
        session.next_request()
        self.assertFalse(session.accept_reply(b"not JSON")["accepted"])
        self.assertIsNone(session.next_request())
        self.assertEqual(session.index, 1)
        self.assertEqual((session.journal.directory/"0001.raw.bin").read_bytes(), b"not JSON")

    def test_request_reply_order_enforced(self):
        session = self.new_session()
        with self.assertRaises(ValueError): session.accept_reply(b"{}")
        session.next_request()
        with self.assertRaises(ValueError): session.next_request()
        session.accept_reply(reply_fixture(session))
        with self.assertRaises(ValueError): session.accept_reply(b"{}")

    def test_returned_payload_mutation_cannot_change_saved_context(self):
        session = self.new_session()
        payload = session.next_request(); payload["model"] = "another-model"
        self.assertNotEqual(session.contexts[1]["payload"]["model"], payload["model"])

    def test_incomplete_and_alias_candidate_rejected(self):
        for raw in ({"model": "different", "status": "completed"}, {"model": "m", "status": "incomplete"}):
            with self.assertRaises(ValueError): workflow.decode_candidate(raw, "gemini", "m")

    def test_minimax_reasoning_is_excluded_and_truncation_rejected(self):
        row = {"model": "MiniMax-M3", "provider": "minimax"}
        raw = json.loads(envelope(row, "Visible answer"))
        self.assertEqual(workflow.decode_candidate(raw, "minimax", row["model"]), {"text": "Visible answer"})
        raw["choices"][0]["finish_reason"] = "length"
        with self.assertRaises(ValueError): workflow.decode_candidate(raw, "minimax", row["model"])

    def test_empty_and_embedded_thought_content_rejected(self):
        for text in ("", "<think>secret</think>answer"):
            row = {"model": "m", "provider": "grok"}
            with self.assertRaises(ValueError): workflow.decode_candidate(json.loads(envelope(row, text)), "grok", "m")

    def test_no_normalization_toward_eighty(self):
        for report in self.report["separate_judge_fixture_reports"].values():
            self.assertEqual(report["point_mean"], 100)
            self.assertEqual(report["expected_cells"], 108)
        self.assertIn("not_model_results", self.report["mode"])

    def test_stability_full_denominators_and_thresholds(self):
        result = self.report["stability_diagnostics"]
        self.assertTrue(result["pass"])
        self.assertEqual(result["expected_repeat_stages"], 96)
        self.assertEqual(result["known_repeat_stages"], 96)
        self.assertEqual(result["expected_criterion_comparisons"], 312)
        self.assertEqual(result["available_cross_judge_point_pairs"], 108)

    def test_missing_repeat_does_not_shrink_denominator(self):
        judgments = deepcopy(self.first.judgments)
        row = self.first.rows[-1]
        del judgments[workflow.judgment_key(row)]
        result = workflow.stability_diagnostics(ROOT, self.first.rows, judgments, self.first.contexts, self.first.score_rows())
        self.assertFalse(result["pass"])
        self.assertEqual(result["expected_repeat_stages"], 96)
        self.assertEqual(result["known_repeat_stages"], 95)

    def test_unclear_removes_point_pair_not_panel_cell(self):
        records = deepcopy(self.first.score_rows())
        next(r for r in records if not r["repeat"])["point_score"] = None
        result = workflow.stability_diagnostics(ROOT, self.first.rows, self.first.judgments, self.first.contexts, records)
        self.assertFalse(result["pass"])
        self.assertEqual(result["available_cross_judge_point_pairs"], 107)
        self.assertEqual(result["expected_cross_judge_point_pairs"], 108)

    def test_recheck_gate_precedes_confirmation(self):
        rows = workflow.schedule(ROOT, "confirmation", True)
        self.assertTrue(all(r["block"] == "control" for r in rows[:72]))
        self.assertTrue(all(r["block"] == "confirmation" for r in rows[72:]))

    def test_frozen_snapshot_and_public_audit(self):
        self.assertEqual(workflow.snapshot(ROOT), load_json(ROOT/workflow.FREEZE))
        self.assertEqual(workflow.audit(ROOT), load_json(ROOT/"data/audit/s38_workflow_summary.json"))


if __name__ == "__main__":
    unittest.main()
