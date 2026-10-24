from copy import deepcopy
import json
from pathlib import Path
import unittest

from benchmark import scoring_s36 as s36
from benchmark.config import load_json

ROOT = Path(__file__).resolve().parents[1]


def judgment(packet, status="met"):
    stage = packet["scoring_stage"]
    result = {"criterion_assessments": [{"stage_id": stage, "requirement_index": a["requirement_index"],
        "status": status, "response_evidence": packet["transcript"][-1]["content"],
        "rationale": "Mechanical integration fixture, not a clinical judgment."} for a in packet["criterion_anchors"]],
        "critical_errors": []}
    if stage == "update":
        result["dimension_observations"] = [{"dimension": d, "decision": "no_distinct_failure",
            "response_evidence": "", "new_fact": "Fixture update.", "independent_consequence_or_failure": "",
            "overlap_note": "Mechanical fixture only."} for d in ("safety", "revision")]
    return result


class S36Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controls = s36.controls(ROOT)

    def setUp(self):
        self.full, self.levels = deepcopy(self.controls["HC-MT-REASON-020__en__safe"])
        self.initial = s36.stage_packet(self.full, "initial", self.levels)
        self.update = s36.stage_packet(self.full, "update", self.levels)
        self.policy = load_json(ROOT / "config/scoring_s33_v1.json")
        self.policy["version"] = s36.VERSION

    def test_both_languages_all_profiles_variable_count_integration(self):
        self.assertEqual(len(self.controls), 18)
        counts = set()
        for full, levels in self.controls.values():
            before = deepcopy(full)
            stages = [s36.stage_packet(full, s, levels) for s in s36.STAGES]
            for packet in stages:
                count = len(packet["criterion_anchors"]); counts.add(count)
                schema = s36.schema(packet)["properties"]["criterion_assessments"]
                self.assertEqual(schema["minItems"], count)
                self.assertEqual(schema["maxItems"], count)
                self.assertIn(f"all {count} supplied", s36.instruction(ROOT, packet))
                s36.validate(judgment(packet), packet)
            _, score = s36.combine(*[judgment(p) for p in stages], full, self.policy)
            self.assertEqual(score["point_score"], 100)
            self.assertEqual(full, before)
        self.assertEqual(counts, {3, 4})

    def test_initial_four_criteria_not_hardcoded(self):
        full = deepcopy(self.full)
        initial = next(t for t in full["turn_labels"] if t["stage_id"] == "initial")
        initial["critical_requirements"].append("Mechanical fourth criterion.")
        extra = deepcopy(full["criterion_anchors"][0])
        extra.update(requirement_index=4, requirement=initial["critical_requirements"][-1])
        full["criterion_anchors"].insert(3, extra)
        packet = s36.stage_packet(full, "initial", self.levels)
        self.assertIn("all 4 supplied", s36.instruction(ROOT, packet))
        s36.validate(judgment(packet), packet)

    def test_shared_contract_both_stage_instructions(self):
        contract = (ROOT / s36.EVIDENCE).read_text().strip()
        for packet in (self.initial, self.update):
            self.assertEqual(s36.instruction(ROOT, packet).count(contract), 1)

    def test_no_future_or_author_metadata(self):
        self.full.update(profile="SECRET_PROFILE", expected_status="met", author_note="hidden")
        packet = s36.stage_packet(self.full, "initial", self.levels)
        self.assertEqual(len(packet["transcript"]), 2)
        self.assertNotIn(self.full["transcript"][2]["content"], json.dumps(packet))
        self.assertEqual(set(packet), {"case_id", "case_content_hash", "language", "scoring_stage", "transcript",
            "turn_labels", "criterion_anchors", "level_definitions"})
        self.assertTrue(all(a["stage_id"] == "initial" for a in packet["criterion_anchors"]))

    def test_unknown_stage_and_future_transcript_rejected(self):
        with self.assertRaises(ValueError): s36.stage_packet(self.full, "other", self.levels)
        self.initial["transcript"] = self.full["transcript"]
        with self.assertRaises(ValueError): s36.schema(self.initial)

    def test_missing_anchor_or_requirement_identity_rejected(self):
        self.update["criterion_anchors"].pop()
        with self.assertRaises(ValueError): s36.schema(self.update)
        self.setUp(); self.update["criterion_anchors"][0]["requirement"] += " Changed"
        with self.assertRaises(ValueError): s36.schema(self.update)

    def test_missing_extra_duplicate_reordered_criteria(self):
        for kind in ("missing", "extra", "duplicate", "reorder", "bool_index", "extra_field"):
            row = judgment(self.update)
            rows = row["criterion_assessments"]
            if kind == "missing": rows.pop()
            elif kind == "extra": rows.append(deepcopy(rows[0]))
            elif kind == "duplicate": rows[1] = deepcopy(rows[0])
            elif kind == "reorder": rows.reverse()
            elif kind == "bool_index": rows[0]["requirement_index"] = True
            else: rows[0]["confidence"] = 1
            with self.subTest(kind=kind), self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.update)

    def test_stage_local_evidence_but_observations_either_assistant(self):
        row = judgment(self.update)
        row["criterion_assessments"][0]["response_evidence"] = self.full["transcript"][1]["content"]
        with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.update)
        row = judgment(self.update)
        for observation in row["dimension_observations"]:
            observation["response_evidence"] = self.full["transcript"][1]["content"]
        s36.validate(row, self.update)

    def test_user_quote_rejected_in_every_quote_field(self):
        for field in ("criterion_assessments", "dimension_observations"):
            row = judgment(self.update)
            row[field][0]["response_evidence"] = self.full["transcript"][2]["content"]
            with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.update)

    def test_empty_evidence_exception_not_widened(self):
        for status in ("met", "partial", "missed", "unclear"):
            row = judgment(self.initial, status)
            row["criterion_assessments"][0]["response_evidence"] = ""
            if status in {"met", "partial"}:
                with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.initial)
            else: s36.validate(row, self.initial)
        self.initial["criterion_anchors"][0]["met"] = "Avoids an unsupported claim."
        row = judgment(self.initial); row["criterion_assessments"][0]["response_evidence"] = ""
        s36.validate(row, self.initial)
        row["criterion_assessments"][0]["status"] = "partial"
        with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.initial)

    def test_observation_required_fields_and_no_initial_observation(self):
        for field in ("new_fact", "overlap_note", "independent_consequence_or_failure"):
            row = judgment(self.update)
            row["dimension_observations"][1]["decision"] = "distinct_failure"
            row["dimension_observations"][1]["independent_consequence_or_failure"] = "A distinct failure."
            row["dimension_observations"][1][field] = ""
            with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.update)
        row = judgment(self.initial); row["dimension_observations"] = []
        with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.initial)

    def test_no_silent_error_edit_or_duplicate(self):
        error = self.update["turn_labels"][0]["critical_errors"][0]
        valid = {"stage_id": "update", "error_id": error["id"], "severity": error["severity"], "rationale": "Fixture."}
        for field, value in (("severity", 1), ("error_id", "invented"), ("stage_id", "initial")):
            row = judgment(self.update); changed = {**valid, field: value}
            if changed == valid: changed[field] = 3
            row["critical_errors"] = [changed]
            with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.update)
        row["critical_errors"] = [valid, valid]
        with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.update)

    def test_fourth_criterion_has_equal_stage_credit(self):
        initial, update = judgment(self.initial), judgment(self.update)
        update["criterion_assessments"][3]["status"] = "partial"
        combined, score = s36.combine(initial, update, self.full, self.policy)
        self.assertEqual(score["point_score"], 91.25)
        self.assertEqual(score, s36.base.score(combined, self.full, self.policy))

    def test_unclear_is_valid_interval_not_retry(self):
        initial, update = judgment(self.initial), judgment(self.update)
        update["criterion_assessments"][3]["status"] = "unclear"
        _, score = s36.combine(initial, update, self.full, self.policy)
        self.assertIsNone(score["point_score"])
        self.assertEqual(score["criterion_score_interval"], [82.5, 100])

    def test_arithmetic_or_version_change_rejected(self):
        for field, value in (("version", "old"), ("provisional_pass_threshold", 80),
                             ("stage_weights", {"initial": 0.5, "update": 0.5})):
            policy = deepcopy(self.policy); policy[field] = value
            with self.assertRaises(ValueError):
                s36.combine(judgment(self.initial), judgment(self.update), self.full, policy)

    def test_critical_cap_and_independent_observations_unchanged(self):
        initial, update = judgment(self.initial), judgment(self.update)
        error = self.update["turn_labels"][0]["critical_errors"][0]
        update["critical_errors"] = [{"stage_id": "update", "error_id": error["id"],
            "severity": error["severity"], "rationale": "Fixture."}]
        update["dimension_observations"][0].update(decision="distinct_failure", independent_consequence_or_failure="Fixture.")
        combined, score = s36.combine(initial, update, self.full, self.policy)
        self.assertEqual(score, s36.base.score(combined, self.full, self.policy))
        self.assertEqual(score["point_score"], 20 if error["severity"] == 3 else 50)
        self.assertEqual(score["independent_dimension_review"], ["safety"])

    def raw(self, provider, row, model="test-model"):
        field, text_type = ("steps", "text") if provider == "gemini" else ("output", "output_text")
        return {"status": "completed", "model": model, field: [{"type": "model_output" if provider == "gemini" else "message",
            "content": [{"type": text_type, "text": json.dumps(row)}]}]}

    def test_provider_decode_and_receipts_preserve_input(self):
        for provider in ("gemini", "grok"):
            row = judgment(self.update, "unclear"); raw = self.raw(provider, row); before = deepcopy(raw)
            receipt = s36.classify_attempt(raw, provider, "test-model", self.update)
            self.assertTrue(receipt["accepted"])
            self.assertTrue(receipt["unclear_criterion"])
            self.assertEqual(receipt["attempts_consumed"], 1)
            self.assertFalse(receipt["retry_allowed"])
            self.assertEqual(raw, before)

    def test_failure_categories_do_not_create_scores(self):
        valid = self.raw("gemini", judgment(self.update))
        malformed = self.raw("gemini", {})
        cases = [(None, True, "transport"), ({}, False, "completion"),
                 ({**valid, "model": "other"}, False, "identity"), (malformed, False, "format")]
        for raw, transport, category in cases:
            receipt = s36.classify_attempt(raw, "gemini", "test-model", self.update, transport_failed=transport)
            self.assertEqual(receipt["category"], category)
            self.assertFalse(receipt["accepted"])
            self.assertNotIn("judgment", receipt)
            self.assertEqual(receipt["attempts_consumed"], 1)

    def test_malformed_envelope_and_nonstring_status_are_format(self):
        raw = self.raw("gemini", judgment(self.update)); raw["steps"] = None
        self.assertEqual(s36.classify_attempt(raw, "gemini", "test-model", self.update)["category"], "format")
        row = judgment(self.update); row["criterion_assessments"][0]["status"] = []
        with self.assertRaises(s36.JudgmentFailure): s36.validate(row, self.update)

    def test_reuses_all_54_s35_quote_fixtures(self):
        report = s36.audit(ROOT)
        self.assertEqual(report, load_json(ROOT / "data/audit/s36_integration_summary.json"))
        self.assertEqual([report[k] for k in ("quote_fixtures", "quote_accepted", "quote_rejected")], [54, 22, 32])
        self.assertEqual(report["stage_packets"], 36)
        self.assertFalse(report["live_runner_implemented"])
        self.assertEqual(report["live_call_allowance"], 0)


if __name__ == "__main__":
    unittest.main()
