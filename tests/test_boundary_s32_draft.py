from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from benchmark import boundary_s32_draft as draft
from benchmark import scoring_s26 as base
from benchmark.config import load_json
from benchmark.criterion_anchors import attach_anchors
from benchmark.multiturn_diagnostics import contrast_packet

ROOT = Path(__file__).resolve().parents[1]


class S32DraftTests(unittest.TestCase):
    def setUp(self):
        self.data, self.old, self.anchors, self.probes, self.fixtures = draft.inputs(ROOT)

    def build(self):
        return draft.build_packets(self.data, self.old, self.anchors, self.probes, self.fixtures)

    def test_scope_and_allowlist(self):
        report = draft.audit(ROOT)
        self.assertEqual(report["packet_count"], 32)
        self.assertEqual(report["author_hypothesis_packets"], 28)
        self.assertEqual(report["exploratory_packets"], 4)
        self.assertEqual(report["initial_packets_without_future_turns"], 16)
        self.assertEqual(len(set(report["packet_hashes"].values())), 32)
        for packet in self.build()[0].values():
            self.assertEqual(set(packet), {"case_id", "case_content_hash", "language", "transcript",
                                           "target_requirements", "level_definitions"})
            self.assertEqual(len(packet["target_requirements"]), 1)

    def test_public_summary_reproduces_offline_audit(self):
        self.assertEqual(draft.audit(ROOT), load_json(ROOT / "data/audit/s32_care_boundary_draft_summary.json"))

    def test_initial_packets_exclude_future_clinical_facts(self):
        family = next(f for f in self.data["families"] if f["family_id"] == draft.FAMILY)
        for key, packet in self.build()[0].items():
            stage, _, language = key.split("__")
            target = packet["target_requirements"][0]
            self.assertEqual((target["stage_id"], target["requirement_index"]), (stage, draft.TARGETS[stage]))
            if stage == "initial":
                self.assertEqual(len(packet["transcript"]), 2)
                self.assertEqual(packet["transcript"][0]["content"], family["variants"][language]["turns"][0]["user"])
            else:
                self.assertEqual(len(packet["transcript"]), 4)
                probe = next(p for p in self.probes if p["family_id"] == draft.FAMILY and p["language"] == language)
                self.assertEqual(packet["transcript"][1]["content"], probe["initial_response"])
                self.assertEqual(packet["transcript"][2]["content"], family["variants"][language]["turns"][1]["user"])

    def test_does_not_mutate_inputs(self):
        before = deepcopy((self.data, self.old, self.anchors, self.probes, self.fixtures))
        self.build()
        self.assertEqual((self.data, self.old, self.anchors, self.probes, self.fixtures), before)

    def test_only_two_declared_anchor_edits(self):
        family = next(f for f in self.anchors["families"] if f["family_id"] == draft.FAMILY)
        family["stages"]["update"][2]["met"] += " Extra red flag."
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            self.build()
        self.setUp()
        with self.assertRaisesRegex(ValueError, "Missing declared"):
            draft.check_anchor_delta(self.data, self.old, self.old)

    def test_stale_case_or_probe_hash_rejected(self):
        family = next(f for f in self.data["families"] if f["family_id"] == draft.FAMILY)
        family["variants"]["en"]["turns"][0]["user"] += " Edited."
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.build()
        self.setUp()
        next(p for p in self.probes if p["family_id"] == draft.FAMILY)["case_content_hash"] = "stale"
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.build()

    def test_duplicate_historical_language_rejected(self):
        self.probes.append(deepcopy(next(p for p in self.probes if p["family_id"] == draft.FAMILY)))
        with self.assertRaisesRegex(ValueError, "duplicate historical"):
            self.build()

    def test_both_historical_answers_preserved_exactly(self):
        for profile in ("historical_generic", "historical_monitoring"):
            with self.subTest(profile=profile):
                self.setUp()
                item = next(f for f in self.fixtures["fixtures"] if f["profile"] == profile)
                item["target_responses"]["zh-Hans"] += " 新增建议。"
                with self.assertRaisesRegex(ValueError, "Historical control"):
                    self.build()

    def test_duplicate_profile_or_changed_target_rejected(self):
        self.fixtures["fixtures"][1] = deepcopy(self.fixtures["fixtures"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.build()
        self.setUp()
        self.fixtures["fixtures"][0]["requirement_index"] = 2
        with self.assertRaisesRegex(ValueError, "target/profile"):
            self.build()

    def test_missing_language_and_empty_text_rejected(self):
        self.fixtures["fixtures"][0]["target_responses"].pop("en")
        with self.assertRaisesRegex(ValueError, "paired"):
            self.build()
        self.setUp()
        self.fixtures["fixtures"][0]["target_responses"]["en"] = "  "
        with self.assertRaisesRegex(ValueError, "Missing response"):
            self.build()

    def test_exploratory_profiles_keep_no_expected_label(self):
        packets, expected = self.build()
        for key in packets:
            self.assertEqual(expected[key] is None, "__ambiguous_reference__" in key)
        next(f for f in self.fixtures["fixtures"] if f["profile"] == "ambiguous_reference")["expected_status"] = "partial"
        with self.assertRaisesRegex(ValueError, "hypothesis"):
            self.build()

    def test_author_expectations_and_notes_cannot_leak(self):
        before, _ = self.build()
        for item in self.fixtures["fixtures"]:
            item["author_note"] = "AUTHOR_ONLY_SENTINEL"
            if item["expected_status"] is not None:
                item["expected_status"] = "missed"
        after, _ = self.build()
        self.assertEqual(before, after)

    def test_evidence_links_and_author_status_limit(self):
        evidence = load_json(ROOT / draft.EVIDENCE)
        draft.check_evidence(evidence)
        evidence["mappings"][0]["exact_statuses_established_by_source"] = True
        with self.assertRaisesRegex(ValueError, "clinical status"):
            draft.check_evidence(evidence)
        evidence = load_json(ROOT / draft.EVIDENCE)
        evidence["mappings"][0]["source_ids"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "source binding"):
            draft.check_evidence(evidence)

    def test_prompt_only_adds_declared_rule(self):
        old = (ROOT / "config/scoring_s26_judge.txt").read_text()
        new = (ROOT / draft.PROMPT).read_text()
        draft.check_prompt(old, new)
        with self.assertRaisesRegex(ValueError, "only"):
            draft.check_prompt(old, new.replace("do not independently deduct", "independently deduct"))
        with self.assertRaisesRegex(ValueError, "only"):
            draft.check_prompt(old, old)

    def test_audit_never_calls_judge_or_scorer(self):
        with patch.object(base, "request_judgment") as request, patch.object(base, "score") as score:
            report = draft.audit(ROOT)
            request.assert_not_called()
            score.assert_not_called()
        for key in ("judge_calls", "candidate_calls", "numeric_scores_computed", "live_call_allowance"):
            self.assertEqual(report[key], 0)
        for key in ("live_runner_implemented", "default_adopted", "calibration_complete"):
            self.assertFalse(report[key])


class S32QuoteContractTests(unittest.TestCase):
    """Formatting fixtures only, deliberately not clinical judgments or scores."""

    def setUp(self):
        dataset, _, anchors, probes, _ = draft.inputs(ROOT)
        family = next(f for f in dataset["families"] if f["family_id"] == draft.FAMILY)
        probe = next(p for p in probes if p["family_id"] == draft.FAMILY and p["language"] == "zh-Hans")
        self.packet = attach_anchors(contrast_packet(family, probe, "safe"), anchors)
        self.initial = self.packet["transcript"][1]["content"]
        self.update = self.packet["transcript"][3]["content"]
        self.judgment = {
            "criterion_assessments": [{"stage_id": a["stage_id"], "requirement_index": a["requirement_index"],
                "status": "unclear", "response_evidence": "", "rationale": "Formatting fixture, not an assessment."}
                for a in self.packet["criterion_anchors"]],
            "critical_errors": [],
            "dimension_observations": [{"dimension": d, "decision": "no_distinct_failure",
                "response_evidence": self.update, "new_fact": "Formatting fixture update.",
                "independent_consequence_or_failure": "", "overlap_note": "Formatting fixture only."}
                for d in ("safety", "revision")],
        }

    def test_literal_span_from_either_turn_accepted(self):
        for text in (self.initial, self.update, "新出现眼周肿胀、视力变化或严重头痛应及时评估。"):
            self.judgment["dimension_observations"][0]["response_evidence"] = text
            base.validate(self.judgment, self.packet)

    def test_cross_turn_join_remains_invalid(self):
        self.judgment["dimension_observations"][0]["response_evidence"] = "出现严重新症状应及时就医。 / 新出现眼周肿胀、视力变化或严重头痛应及时评估。"
        with self.assertRaisesRegex(ValueError, "observation quote"):
            base.validate(self.judgment, self.packet)

    def test_same_turn_noncontiguous_join_remains_invalid(self):
        self.judgment["dimension_observations"][0]["response_evidence"] = "仅因鼻涕仍黄不应开始抗生素 / 新出现眼周肿胀、视力变化或严重头痛应及时评估。"
        with self.assertRaisesRegex(ValueError, "observation quote"):
            base.validate(self.judgment, self.packet)

    def test_paraphrase_remains_invalid(self):
        self.judgment["dimension_observations"][0]["response_evidence"] = "The answer gives an appropriate plan."
        with self.assertRaisesRegex(ValueError, "observation quote"):
            base.validate(self.judgment, self.packet)

    def test_empty_quote_allowed_but_required_explanations_remain(self):
        for row in self.judgment["dimension_observations"]:
            row["response_evidence"] = ""
        base.validate(self.judgment, self.packet)
        self.judgment["dimension_observations"][1]["new_fact"] = ""
        with self.assertRaisesRegex(ValueError, "independent evidence"):
            base.validate(self.judgment, self.packet)

    def test_observation_rule_does_not_relax_criterion_turn_matching(self):
        row = self.judgment["criterion_assessments"][0]
        row["status"], row["response_evidence"] = "partial", self.update
        with self.assertRaisesRegex(ValueError, "exact assistant turn"):
            base.validate(self.judgment, self.packet)


if __name__ == "__main__":
    unittest.main()
