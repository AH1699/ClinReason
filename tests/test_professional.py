import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json, load_jsonl
from benchmark.multiturn import merge_multiturn_datasets
from benchmark.professional import (
    combine_professional_datasets, professional_candidate_rows, validate_case_adaptation_registry,
    validate_professional_dataset,
    validate_professional_rubric,
)


class ProfessionalPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.dataset = load_json(cls.root / "data/professional/pilot_cases.json")
        cls.batch_e = load_json(cls.root / "data/professional/batch_e_cases.json")
        cls.combined = combine_professional_datasets([cls.dataset, cls.batch_e])

    def test_separate_unscored_bilingual_track(self):
        status = validate_professional_dataset(self.dataset)
        self.assertEqual((status["family_count"], status["variant_count"]), (10, 20))
        self.assertFalse(status["scoring_enabled"])
        self.assertFalse(status["clinical_review_complete"])
        self.assertFalse(status["language_review_complete"])
        rubric = load_json(self.root / "config/professional_rubric.json")
        validate_professional_rubric(rubric)
        self.assertEqual(round(sum(item["weight"] for item in rubric["dimensions"]), 8), 1)
        self.assertEqual(rubric["status"], "authoring_only_not_clinically_calibrated")

    def test_export_contains_no_labels_or_sources_and_cannot_overwrite(self):
        rows = professional_candidate_rows(self.dataset, instruction="Fixture.", prompt_template_version="v1")
        self.assertEqual(len(rows), 20)
        forbidden = ("reference_elements", "critical_errors", "source_refs", "failure_mode")
        self.assertTrue(all(not any(key in row for key in forbidden) for row in rows))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "prompts.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["export-professional-prompts", "--output", str(target)]), 0)
                self.assertEqual(main(["export-professional-prompts", "--output", str(target)]), 2)
            self.assertEqual(len(load_jsonl(target)), 76)

    def test_published_case_adaptations_have_bound_provenance(self):
        registry = load_json(self.root / "data/evidence/clinical_case_adaptations.json")
        self.assertEqual(validate_case_adaptation_registry(registry, self.combined), {
            "adapted_family_count": 22, "adapted_variant_count": 44,
        })
        corrupted = deepcopy(registry)
        corrupted["records"].pop()
        with self.assertRaises(ValueError):
            validate_case_adaptation_registry(corrupted, self.combined)
        corrupted = deepcopy(registry)
        corrupted["records"][0]["source_url"] = "https://example.invalid/unrelated"
        with self.assertRaises(ValueError):
            validate_case_adaptation_registry(corrupted, self.combined)
        corrupted = deepcopy(registry)
        corrupted["records"][0]["license"] = "free-to-read"
        with self.assertRaises(ValueError):
            validate_case_adaptation_registry(corrupted, self.combined)

    def test_batch_e_combines_without_duplicate_families(self):
        status = validate_professional_dataset(self.combined)
        self.assertEqual((status["family_count"], status["variant_count"]), (38, 76))
        self.assertEqual(status["workflow_counts"], {
            "clinical_consult": 24, "evidence_appraisal": 7,
            "medication_reconciliation_handoff": 7,
        })
        with self.assertRaises(ValueError):
            combine_professional_datasets([self.dataset, self.dataset])

    def test_configured_tracks_reach_one_hundred_independent_families(self):
        alpha = {
            row["metadata"]["case_family_id"]
            for row in load_jsonl(self.root / "data/alpha/global_core_cases.jsonl")
        }
        multiturn = merge_multiturn_datasets([
            load_json(self.root / path) for path in (
                "data/multiturn/pilot_cases.json",
                "data/multiturn/batch_c_cases.json",
                "data/multiturn/batch_d_cases.json",
                "data/multiturn/batch_e_cases.json",
            )
        ])
        identifiers = list(alpha) + [item["family_id"] for item in multiturn["families"]]
        identifiers.extend(item["family_id"] for item in self.combined["families"])
        self.assertEqual(len(identifiers), 100)
        self.assertEqual(len(set(identifiers)), 100)

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
