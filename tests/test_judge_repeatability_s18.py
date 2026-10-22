"""No-network checks for S18 exact-cell repeatability comparison."""

import copy
import unittest

from benchmark.judge_repeatability_s18 import compare_cells


class JudgeRepeatabilityS18Tests(unittest.TestCase):
    def cells(self):
        value = {
            "returned_model": "fixed-model-id", "update_statuses": ["met", "met", "partial"],
            "requirements": 3, "safety": 4, "revision": 3,
            "gated_score": 90.0, "pass": True, "judge_requested_human_review": False,
        }
        return {(f"C-{language}", variant, judge): copy.deepcopy(value)
                for language in ("EN", "ZH")
                for variant in ("baseline", "omission")
                for judge in ("gemini-judge", "grok-judge")}

    def test_exact_repeats_count_all_eight_cells(self):
        source = self.cells()
        result = compare_cells(source, copy.deepcopy(source))
        self.assertEqual(result["cells_compared"], 8)
        self.assertEqual(result["exact_score_repeats"], 8)
        self.assertEqual(result["criterion_status_repeats"], 8)
        self.assertEqual(result["dimension_repeats"], 8)

    def test_changes_are_described_not_averaged_or_rescored(self):
        source = self.cells()
        repeated = copy.deepcopy(source)
        key = ("C-ZH", "omission", "grok-judge")
        repeated[key]["gated_score"] = 82.5
        repeated[key]["safety"] = 3
        repeated[key]["update_statuses"][2] = "missed"
        original_source = copy.deepcopy(source)
        original_repeat = copy.deepcopy(repeated)
        result = compare_cells(source, repeated)
        self.assertEqual(result["exact_score_repeats"], 7)
        self.assertEqual(result["criterion_status_repeats"], 7)
        self.assertEqual(result["dimension_repeats"], 7)
        self.assertEqual(result["pass_flag_repeats"], 8)
        self.assertEqual((source, repeated), (original_source, original_repeat))

    def test_missing_cell_is_rejected(self):
        source = self.cells()
        repeated = self.cells()
        repeated.pop(next(iter(repeated)))
        with self.assertRaisesRegex(ValueError, "missing or unexpected"):
            compare_cells(source, repeated)


if __name__ == "__main__":
    unittest.main()
