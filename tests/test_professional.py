import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json, load_jsonl
from benchmark.professional import (
    professional_candidate_rows, validate_professional_dataset,
    validate_professional_rubric,
)


class ProfessionalPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.dataset = load_json(cls.root / "data/professional/pilot_cases.json")

    def test_separate_unscored_bilingual_track(self):
        status = validate_professional_dataset(self.dataset)
        self.assertEqual((status["family_count"], status["variant_count"]), (4, 8))
        self.assertFalse(status["scoring_enabled"])
        self.assertFalse(status["clinical_review_complete"])
        self.assertFalse(status["language_review_complete"])
        rubric = load_json(self.root / "config/professional_rubric.json")
        validate_professional_rubric(rubric)
        self.assertEqual(round(sum(item["weight"] for item in rubric["dimensions"]), 8), 1)
        self.assertEqual(rubric["status"], "authoring_only_not_clinically_calibrated")

    def test_export_contains_no_labels_or_sources_and_cannot_overwrite(self):
        rows = professional_candidate_rows(self.dataset, instruction="Fixture.", prompt_template_version="v1")
        self.assertEqual(len(rows), 8)
        forbidden = ("reference_elements", "critical_errors", "source_refs", "failure_mode")
        self.assertTrue(all(not any(key in row for key in forbidden) for row in rows))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "prompts.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["export-professional-prompts", "--output", str(target)]), 0)
                self.assertEqual(main(["export-professional-prompts", "--output", str(target)]), 2)
            self.assertEqual(len(load_jsonl(target)), 8)

    def test_bilingual_mismatch_and_duplicate_rejected(self):
        corrupted = deepcopy(self.dataset)
        corrupted["families"][0]["variants"]["zh-Hans"]["critical_errors"][0]["severity"] = 1
        with self.assertRaises(ValueError):
            validate_professional_dataset(corrupted)
        rubric = load_json(self.root / "config/professional_rubric.json")
        rubric["dimensions"][0]["weight"] = 0.9
        with self.assertRaises(ValueError):
            validate_professional_rubric(rubric)
        corrupted = deepcopy(self.dataset)
        corrupted["families"].append(deepcopy(corrupted["families"][0]))
        with self.assertRaises(ValueError):
            validate_professional_dataset(corrupted)


if __name__ == "__main__":
    unittest.main()
