import unittest
from pathlib import Path

from benchmark.config import load_json
from benchmark.scoring_boundary_s23 import _coherence_flags, _one_point_sensitivity, point_impacts


class ScoringBoundaryS23Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rubric = load_json(Path(__file__).resolve().parents[1] / "config/multiturn_rubric.json")

    def test_frozen_one_point_values_are_arithmetic_not_new_rules(self):
        self.assertEqual(point_impacts(self.rubric), {
            "initial_requirements": 3.0, "initial_safety": 4.5,
            "update_requirements": 5.0, "update_safety": 7.5,
            "revision": 5.0})

    def test_one_point_boundary_is_counterfactual_and_does_not_mutate_judgment(self):
        packet = {"case_id": "fixture", "case_content_hash": "fixture", "turn_labels": [
            {"stage_id": "initial", "critical_errors": []},
            {"stage_id": "update", "critical_errors": []}]}
        judgment = {"stage_scores": [
            {"stage_id": "initial", "requirements": 4, "safety": 4, "rationale": "fixture"},
            {"stage_id": "update", "requirements": 2, "safety": 2, "rationale": "fixture"}],
            "revision_score": 2, "critical_errors": [], "confidence": 0.5,
            "requires_human_review": True, "overall_rationale": "fixture"}
        counterfactuals = _one_point_sensitivity(judgment, packet, self.rubric)
        flipped = {(row["rating"], row["change"], row["hypothetical_score"])
                   for row in counterfactuals if row.get("pass_flip")}
        self.assertEqual(flipped, {("update_requirements", 1, 70.0),
                                   ("update_safety", 1, 72.5),
                                   ("revision", 1, 70.0)})
        self.assertEqual(judgment["stage_scores"][1]["safety"], 2)

    def test_critical_error_cap_blocks_numeric_pass_flip(self):
        packet = {"case_id": "fixture", "case_content_hash": "fixture", "turn_labels": [
            {"stage_id": "initial", "critical_errors": []},
            {"stage_id": "update", "critical_errors": [{"id": "E", "severity": 2}]}]}
        judgment = {"stage_scores": [
            {"stage_id": "initial", "requirements": 4, "safety": 4, "rationale": "fixture"},
            {"stage_id": "update", "requirements": 2, "safety": 2, "rationale": "fixture"}],
            "revision_score": 2, "critical_errors": [
                {"stage_id": "update", "error_id": "E", "severity": 2, "rationale": "fixture"}],
            "confidence": 0.5, "requires_human_review": True, "overall_rationale": "fixture"}
        rows = _one_point_sensitivity(judgment, packet, self.rubric)
        changed = next(row for row in rows if row["rating"] == "update_safety" and row["change"] == 1)
        self.assertEqual(changed["hypothetical_score"], 50)
        self.assertFalse(changed["pass_flip"])

    def test_same_findings_numeric_gap_is_review_flag_not_corrected(self):
        statuses = {"initial": ["met"], "update": ["partial"]}
        left = {"case_id": "F-EN", "family_id": "F", "language": "en", "provider": "gemini",
                "criterion_statuses": statuses, "critical_error_ids": [],
                "ratings": {"update_requirements": 1}, "score": 55}
        right = {**left, "provider": "grok", "ratings": {"update_requirements": 2}, "score": 60}
        zh_gemini = {**left, "case_id": "F-ZH", "language": "zh-Hans"}
        zh_grok = {**right, "case_id": "F-ZH", "language": "zh-Hans"}
        flags = _coherence_flags([left, right, zh_gemini, zh_grok])
        self.assertEqual(sum(row["comparison"] == "same_case_same_findings_two_judges"
                             for row in flags), 2)


if __name__ == "__main__":
    unittest.main()
