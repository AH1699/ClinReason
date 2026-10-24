from copy import deepcopy
from pathlib import Path
import unittest

from benchmark import reference_mix_s36 as mix
from benchmark.config import load_json

ROOT = Path(__file__).resolve().parents[1]


class ReferenceMixTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_json(ROOT / mix.PLAN)
        self.records = [{"model": m, "family_id": f, "language": l, "point_score": score,
            "criterion_score_interval": [score, score], "hard_fail": False, "judge": "one-judge", "score_version": "one-version"}
            for m, score in (("A", 60), ("B", 100)) for f in ("F1", "F2") for l in ("en", "zh-Hans")]

    def report(self, records=None):
        return mix.summarize(self.records if records is None else records, ["A", "B"], ["F1", "F2"])

    def test_proposal_budget_counts(self):
        result = mix.check_plan(ROOT, self.plan)
        self.assertEqual(result, load_json(ROOT / "data/audit/s36_proposal_summary.json"))
        self.assertFalse(result["live_ready"])
        self.assertEqual(result["confirmation_unbuilt_slots"], 3)
        b = result["budget_scenarios"]
        self.assertEqual(b["maximum_attempts"], 1320)
        self.assertEqual(b["first_phase_attempts"], 816)
        self.assertEqual(b["confirmation_phase_max_attempts"], 504)
        self.assertLess(b["token_ceiling_scenario_usd"], 90)

    def test_roster_or_budget_drift_rejected(self):
        self.plan["candidates"][0]["model"] = "invented"
        with self.assertRaises(ValueError): mix.check_plan(ROOT, self.plan)
        self.setUp(); self.plan["budget"]["maximum_attempts"] += 1
        with self.assertRaises(ValueError): mix.check_plan(ROOT, self.plan)

    def test_proposal_cannot_authorize_calls(self):
        self.plan["live_call_allowance"] = 1
        with self.assertRaises(ValueError): mix.check_plan(ROOT, self.plan)

    def test_hold_or_shared_source_group_cannot_enter_split(self):
        self.plan["confirmation"][0]["family_id"] = "HC-MT-TRIAGE-018"
        with self.assertRaises(ValueError): mix.check_plan(ROOT, self.plan)
        self.setUp(); self.plan["confirmation"][0]["family_id"] = "HC-MT-REASON-021"
        with self.assertRaisesRegex(ValueError, "mechanism"): mix.check_plan(ROOT, self.plan)

    def test_equal_roster_mean_not_per_model_target(self):
        report = self.report()
        self.assertEqual(report["point_mean"], 80)
        self.assertEqual(report["per_model"]["A"]["point_mean"], 60)
        self.assertEqual(report["per_model"]["B"]["point_mean"], 100)
        self.assertEqual(report["model_mean_population_sd"], 20)

    def test_missing_cells_not_renormalized(self):
        report = self.report(self.records[:-1])
        self.assertIsNone(report["point_mean"])
        self.assertEqual(report["full_denominator_interval"], [67.5, 80])
        self.assertEqual(report["accepted_cells"], 7)
        self.assertEqual(report["expected_cells"], 8)
        self.assertIsNone(report["per_model"]["B"]["point_mean"])

    def test_unclear_cells_preserved_as_interval(self):
        self.records[0].update(point_score=None, criterion_score_interval=[50, 70])
        result = self.report()
        self.assertIsNone(result["point_mean"])
        self.assertEqual(result["full_denominator_interval"], [78.75, 81.25])
        self.assertEqual(result["unresolved_cells"], 1)

    def test_duplicate_foreign_or_pooled_cells_rejected(self):
        with self.assertRaises(ValueError): self.report(self.records + [self.records[0]])
        for field, value in (("judge", "other"), ("score_version", "other"), ("model", "other")):
            rows = deepcopy(self.records); rows[0][field] = value
            with self.assertRaises(ValueError): self.report(rows)

    def test_malformed_nonfinite_scores_rejected(self):
        for interval, point in (([0, 101], 101), ([80, 70], None), ([float('nan'), 90], None), ([0, 100], 80), ([True, True], True)):
            rows = deepcopy(self.records); rows[0].update(criterion_score_interval=interval, point_score=point)
            with self.assertRaises(ValueError): self.report(rows)

    def test_safety_and_language_not_hidden_in_mean(self):
        self.records[0]["hard_fail"] = True
        result = self.report()
        self.assertEqual(result["hard_fail_cells"], 1)
        self.assertEqual(result["per_language"]["en"]["hard_fail_cells"], 1)
        self.assertEqual(result["point_mean"], 80)

    def test_empty_panel_is_not_zero_performance(self):
        result = self.report([])
        self.assertIsNone(result["point_mean"])
        self.assertEqual(result["full_denominator_interval"], [0, 100])


if __name__ == "__main__":
    unittest.main()
