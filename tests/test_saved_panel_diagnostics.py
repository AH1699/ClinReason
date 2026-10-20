import unittest
from copy import deepcopy

from benchmark.saved_panel_diagnostics import summarize_saved_panels


def panel(candidate, en_scores, zh_scores):
    rows = []
    for suffix, scores in (("EN", en_scores), ("ZH-HANS", zh_scores)):
        rows.append({
            "candidate_id": candidate,
            "case_id": f"HC-MT-TEST-001-{suffix}",
            "case_content_hash": f"hash-{suffix}",
            "judges": [
                {"judge_id": "gemini-judge", "gated_score": scores[0],
                 "hard_fail": False, "review_required": True,
                 "same_vendor_as_candidate": candidate == "gemini"},
                {"judge_id": "grok-judge", "gated_score": scores[1],
                 "hard_fail": False, "review_required": True,
                 "same_vendor_as_candidate": False},
            ],
        })
    return {
        "status": "experimental_unvalidated_two_ai_judges_not_clinical_ranking",
        "dataset_sha256": "dataset", "rubric_sha256": "rubric",
        "criterion_anchors_sha256": "anchors",
        "judge_instruction_sha256": "instruction",
        "criterion_validator_version": "fixture-1",
        "results": rows,
    }


class SavedPanelDiagnosticTests(unittest.TestCase):
    def test_flags_ceiling_judge_and_language_gaps_without_ranking(self):
        result = summarize_saved_panels([
            panel("gemini", (100, 90), (95, 95)),
            panel("minimax", (100, 100), (90, 80)),
        ])
        self.assertEqual(result["candidate_panel_count"], 2)
        self.assertEqual(result["paired_case_revision_count"], 2)
        self.assertEqual(len(result["judge_gap_flags"]), 2)
        self.assertEqual(len(result["bilingual_gap_flags"]), 4)
        self.assertEqual(result["candidate_judge_summaries"][0]["score_100_count"], 1)
        self.assertIn("not_measurable", result["natural_answer_unsafe_false_pass_status"])
        self.assertNotIn("overall_average", result)

    def test_rejects_mismatched_case_or_protocol_and_invalid_score(self):
        a = panel("gemini", (100, 90), (95, 95))
        b = panel("minimax", (100, 100), (90, 80))
        corrupted = deepcopy(b)
        corrupted["results"][1]["case_content_hash"] = "changed"
        with self.assertRaisesRegex(ValueError, "identical case revisions"):
            summarize_saved_panels([a, corrupted])
        corrupted = deepcopy(b)
        corrupted["rubric_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "protocol bindings"):
            summarize_saved_panels([a, corrupted])
        corrupted = deepcopy(b)
        corrupted["results"][0]["judges"][0]["gated_score"] = True
        with self.assertRaisesRegex(ValueError, "number in"):
            summarize_saved_panels([a, corrupted])

    def test_synthetic_contrast_is_marked_author_only_and_protocol_bound(self):
        report = panel("gemini", (100, 90), (95, 95))
        contrast = {
            "status": "synthetic_contrast_two_ai_judges_not_clinical_validation",
            "dataset_sha256": "dataset", "rubric_sha256": "rubric",
            "criterion_anchors_sha256": "anchors",
            "judge_instruction_sha256": "instruction",
            "case_id": "HC-MT-TEST-001-EN",
            "results": {
                "gemini-judge": {"ordered_scores": True,
                                 "unsafe_error_detected": True,
                                 "unsafe_false_pass": False},
                "grok-judge": {"ordered_scores": True,
                               "unsafe_error_detected": True,
                               "unsafe_false_pass": False},
            },
        }
        result = summarize_saved_panels([report], contrast=contrast)
        self.assertTrue(result["synthetic_author_contrast_not_human_truth"]["judge_flags"]["gemini-judge"]["ordered_scores"])
        contrast["rubric_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "Synthetic contrast"):
            summarize_saved_panels([report], contrast=contrast)

    def test_rejects_incomplete_language_pair_and_wrong_contrast_case(self):
        report = panel("gemini", (100, 90), (95, 95))
        incomplete = deepcopy(report)
        incomplete["results"].pop()
        with self.assertRaisesRegex(ValueError, "complete EN/ZH"):
            summarize_saved_panels([incomplete])
        contrast = {
            "status": "synthetic_contrast_two_ai_judges_not_clinical_validation",
            "dataset_sha256": "dataset", "rubric_sha256": "rubric",
            "criterion_anchors_sha256": "anchors",
            "judge_instruction_sha256": "instruction",
            "case_id": "HC-MT-OTHER-001-EN", "results": {},
        }
        with self.assertRaisesRegex(ValueError, "Synthetic contrast"):
            summarize_saved_panels([report], contrast=contrast)


if __name__ == "__main__":
    unittest.main()
