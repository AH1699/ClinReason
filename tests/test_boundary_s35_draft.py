from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import boundary_s35_draft as draft
from benchmark.config import load_json

ROOT = Path(__file__).resolve().parents[1]


class S35DraftTests(unittest.TestCase):
    def setUp(self):
        self.dataset, self.old, self.anchors, self.probes, self.fixtures = draft.inputs(ROOT)

    def build(self):
        return draft.build_packets(self.dataset, self.old, self.anchors, self.probes, self.fixtures)

    def test_scope_counts_and_no_live_scoring(self):
        report = draft.audit(ROOT)
        for key, value in {"packet_count": 46, "target_criterion_count": 64, "author_hypothesis_criteria": 44,
                "exploratory_criteria": 20, "initial_packets_without_future_turns": 32,
                "held_followup_packets": 14, "paired_one_component_contrasts": 14,
                "changed_anchor_count": 3, "quote_fixture_count": 54, "quote_accepted": 22,
                "quote_rejected": 32}.items():
            self.assertEqual(report[key], value, key)
        for key in ("judge_calls", "candidate_calls", "numeric_scores_computed", "live_call_allowance"):
            self.assertEqual(report[key], 0)
        for key in ("live_runner_implemented", "default_adopted", "calibration_complete"):
            self.assertFalse(report[key])

    def test_summary_reproduces(self):
        self.assertEqual(draft.audit(ROOT), load_json(ROOT / "data/audit/s35_candidate_boundary_draft_summary.json"))

    def test_packets_allowlist_and_stage_visibility(self):
        packets, _ = self.build()
        for key, packet in packets.items():
            self.assertEqual(set(packet), {"case_id", "case_content_hash", "language", "scoring_stage",
                "transcript", "target_requirements", "level_definitions"})
            group = next(g for g in self.fixtures["groups"] if g["id"] == key.split("__")[0])
            self.assertEqual([a["requirement_index"] for a in packet["target_requirements"]], group["requirement_indices"])
            self.assertTrue(all(a["stage_id"] == packet["scoring_stage"] for a in packet["target_requirements"]))
            self.assertEqual(len(packet["transcript"]), 2 if packet["scoring_stage"] == "initial" else 4)
            family = next(f for f in self.dataset["families"] if f["family_id"] == group["family_id"])
            self.assertEqual(packet["transcript"][0]["content"], family["variants"][packet["language"]]["turns"][0]["user"])
            if packet["scoring_stage"] == "update":
                probe = next(p for p in self.probes if p["family_id"] == group["family_id"] and p["language"] == packet["language"])
                self.assertEqual(packet["transcript"][1]["content"], probe["initial_response"])

    def test_inputs_not_mutated(self):
        before = deepcopy((self.dataset, self.old, self.anchors, self.probes, self.fixtures))
        self.build()
        self.assertEqual((self.dataset, self.old, self.anchors, self.probes, self.fixtures), before)

    def test_only_three_anchor_edits_and_held_target_unchanged(self):
        draft.check_anchor_delta(self.dataset, self.old, self.anchors)
        eye = next(f for f in self.anchors["families"] if f["family_id"] == "HC-MT-TRIAGE-018")
        original = next(f for f in self.old["families"] if f["family_id"] == eye["family_id"])
        self.assertEqual(eye["stages"]["update"][1], original["stages"]["update"][1])
        eye["stages"]["update"][1]["met"] += " Silently resolve OR/AND."
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            self.build()

    def test_unrelated_anchor_or_level_change_rejected(self):
        for mutate in (lambda a: a["levels"].update(partial="new level"),
                       lambda a: a["families"][1]["stages"]["initial"][0].update(met="unrelated change")):
            anchors = deepcopy(self.anchors); mutate(anchors)
            with self.assertRaisesRegex(ValueError, "Undeclared"):
                draft.check_anchor_delta(self.dataset, self.old, anchors)

    def test_missing_declared_anchor_change_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing declared"):
            draft.check_anchor_delta(self.dataset, self.old, self.old)

    def test_stale_case_or_probe_rejected(self):
        self.probes[0]["case_content_hash"] = "stale"
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.build()
        self.setUp()
        self.dataset["families"][0]["variants"]["en"]["turns"][0]["user"] += " Edited."
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.build()

    def test_duplicate_probe_or_group_rejected(self):
        self.probes.append(deepcopy(self.probes[0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.build()
        self.setUp()
        self.fixtures["groups"][1] = deepcopy(self.fixtures["groups"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.build()

    def test_duplicate_profile_or_missing_coverage_rejected(self):
        self.fixtures["groups"][0]["profiles"].append(deepcopy(self.fixtures["groups"][0]["profiles"][0]))
        with self.assertRaisesRegex(ValueError, "profile"):
            self.build()
        self.setUp(); self.fixtures["groups"][0]["profiles"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.build()

    def test_target_drift_rejected(self):
        self.fixtures["groups"][0]["requirement_indices"] = [2, 3]
        with self.assertRaisesRegex(ValueError, "target"):
            self.build()

    def test_missing_language_and_empty_common_rejected(self):
        self.fixtures["groups"][0]["profiles"][0]["parts"]["elicitation"].pop("zh-Hans")
        with self.assertRaisesRegex(ValueError, "paired"):
            self.build()
        self.setUp(); self.fixtures["groups"][0]["common_response"]["en"] = " "
        with self.assertRaisesRegex(ValueError, "paired"):
            self.build()

    def test_hypotheses_and_author_notes_do_not_leak(self):
        before, _ = self.build()
        for group in self.fixtures["groups"]:
            for profile in group["profiles"]:
                profile["author_note"] = "AUTHOR_ONLY_SENTINEL"
                profile["hypotheses"] = {k: "missed" if v is not None else None for k, v in profile["hypotheses"].items()}
                for alternative in profile["alternatives"]:
                    alternative["plausible_statuses"] = ["unclear"]
        after, _ = self.build()
        self.assertEqual(before, after)

    def test_held_and_vague_probes_cannot_gain_expected_labels(self):
        for group_index, profile_index in ((2, 0), (0, 8), (1, 6)):
            self.setUp()
            profile = self.fixtures["groups"][group_index]["profiles"][profile_index]
            profile["hypotheses"][next(iter(profile["hypotheses"]))] = "met"
            with self.assertRaisesRegex(ValueError, "Exploratory"):
                self.build()

    def test_followup_alternatives_must_preserve_both_interpretations(self):
        self.fixtures["groups"][2]["profiles"][0]["alternatives"].pop()
        with self.assertRaisesRegex(ValueError, "competing"):
            self.build()

    def test_component_contrast_detects_unrelated_edit(self):
        profile = next(p for p in self.fixtures["groups"][0]["profiles"] if p["id"] == "report_request")
        profile["parts"]["safety_route"]["en"] += " Changed route."
        with self.assertRaisesRegex(ValueError, "undeclared components"):
            self.build()

    def test_duplicate_contrast_rejected(self):
        group = self.fixtures["groups"][0]
        group["contrasts"][1] = deepcopy(group["contrasts"][0])
        with self.assertRaisesRegex(ValueError, "duplicate S35 contrast"):
            self.build()

    def test_evidence_cannot_claim_source_validates_exact_labels(self):
        evidence = load_json(ROOT / draft.EVIDENCE)
        evidence["mappings"][0]["exact_statuses_established_by_source"] = True
        with self.assertRaisesRegex(ValueError, "clinical status"):
            draft.check_evidence(self.dataset, evidence)

    def test_evidence_source_must_exist_and_belong_to_case(self):
        for sources in (["unknown"], ["cdc_adult_outpatient"]):
            evidence = load_json(ROOT / draft.EVIDENCE)
            evidence["mappings"][0]["source_ids"] = sources
            with self.assertRaises(ValueError):
                draft.check_evidence(self.dataset, evidence)

    def test_prompts_have_exact_additive_delta(self):
        draft.check_prompts(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "config").mkdir()
            for path in (*draft.prior.PROMPTS.values(), *draft.PROMPTS.values(), draft.FOCUSED_PROMPT):
                (root / path).write_text((ROOT / path).read_text())
            path = root / draft.PROMPTS["initial"]
            path.write_text(path.read_text().replace("do not infer", "infer", 1))
            with self.assertRaisesRegex(ValueError, "only the criterion"):
                draft.check_prompts(root)

    def test_quote_field_scope_and_empty_exceptions_preserved(self):
        cells = draft.quote_audit(ROOT)
        for cell in cells:
            if cell["operation"] in ("wrong_turn", "empty"):
                self.assertEqual(cell["accepted"], cell["field"] == "observation")
            if cell["operation"] in ("ellipsis_join", "slash_join", "user_quote", "paraphrase"):
                self.assertFalse(cell["accepted"])

    def test_empty_observation_still_requires_explanation(self):
        _, full, _, _ = draft.prior.inputs(ROOT)
        corpus = load_json(ROOT / draft.QUOTES)["corpora"]["en"]
        judgment, packet = draft.quote_fixture(full["HC-MT-TRIAGE-018__en__safe"], self.anchors["levels"],
                                              corpus, "update", "observation", "empty")
        draft.prior.validate(judgment, packet)
        judgment["dimension_observations"][1]["new_fact"] = ""
        with self.assertRaisesRegex(ValueError, "independent evidence"):
            draft.prior.validate(judgment, packet)

    def test_shortlist_counts_and_separate_minimax_estimate(self):
        result = draft.shortlist_preview(ROOT)
        self.assertEqual(len(result["family_ids"]), 3)
        self.assertEqual(result["proposed_control_requests"], 72)
        self.assertEqual(result["separate_minimax_extension_requests"], 36)
        self.assertEqual(result["current_live_allowance"], 0)
        self.assertFalse(result["live_runner_implemented"])

    def test_shortlist_rejects_source_drift_or_budget_change(self):
        for mutate in (lambda p: p["selections"][0]["file_sha256"].update(cases="stale"),
                       lambda p: p["proposed_control_design"].update(estimated_maximum_requests=80),
                       lambda p: p.update(current_live_allowance=72)):
            plan = load_json(ROOT / draft.SHORTLIST); mutate(plan)
            with self.assertRaises(ValueError):
                draft.shortlist_preview(ROOT, plan)

    def test_audit_never_reads_secrets_calls_provider_or_computes_scores(self):
        with patch.object(draft.minimax_s34, "read_setting") as keys, \
                patch.object(draft.minimax_s34, "request") as candidate, \
                patch.object(draft.prior, "request") as judge, \
                patch.object(draft.prior.base, "score") as score:
            draft.audit(ROOT)
            keys.assert_not_called(); candidate.assert_not_called(); judge.assert_not_called(); score.assert_not_called()


if __name__ == "__main__":
    unittest.main()
