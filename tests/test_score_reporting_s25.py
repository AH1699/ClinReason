import unittest
from pathlib import Path

from benchmark.score_reporting_s25 import audit, reportability


ROOT = Path(__file__).resolve().parents[1]


class ScoreReportingS25Tests(unittest.TestCase):
    def test_complete_stable_approved_released_only_condition_for_comparison(self):
        self.assertTrue(reportability(panel_complete=True, exact_packet_pass_stable=True,
                                      clinical_and_language_approved=True,
                                      methods_released=True)["comparison_ready"])
        held = reportability(panel_complete=False, exact_packet_pass_stable=False,
                             clinical_and_language_approved=False,
                             methods_released=False)
        self.assertFalse(held["comparison_ready"])
        self.assertEqual(len(held["hold_reasons"]), 4)
        untested = reportability(panel_complete=False, exact_packet_pass_stable=None,
                                 clinical_and_language_approved=False,
                                 methods_released=False)
        self.assertIn("exact_packet_repeat_not_performed", untested["hold_reasons"])
        self.assertNotIn("identical_packet_pass_flip", untested["hold_reasons"])

    def test_frozen_s19_s22_evidence_is_not_comparison_ready(self):
        result = audit(ROOT, ROOT / "work/s19_multifamily_repeat_2026-10-21",
                       ROOT / "work/s22_v1_first_2026-10-22")
        self.assertEqual((result["s19_exact_packet_cells"], result["s19_exact_score_repeats"],
                          result["s19_provisional_pass_repeats"]), (24, 15, 22))
        self.assertEqual(result["s19_identical_packet_pass_flip_holds"], 2)
        self.assertEqual(result["s19_comparison_ready_cells"], 0)
        self.assertEqual(result["s22_saved_first_stage_cells"], 23)
        self.assertFalse(result["s22_comparison_ready"]["comparison_ready"])
        self.assertEqual((result["candidate_calls"], result["judge_calls"],
                          result["historical_scores_changed"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
