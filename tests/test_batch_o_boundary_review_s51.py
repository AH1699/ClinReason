from copy import deepcopy
from pathlib import Path
import unittest

from scripts import batch_o_boundary_review_s51 as review

ROOT = Path(__file__).resolve().parents[1]


class BatchOBoundaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.value = review.batch.load_json(ROOT / review.DATA)

    def test_all_twelve_positions_bound_without_case_changes(self):
        result = review.validate(ROOT, self.value)
        self.assertEqual(result['reviewed_criterion_positions'], 12)
        self.assertEqual(result['bilingual_requirement_positions'], 24)
        self.assertEqual(result['boundary_decisions'], 2)
        self.assertEqual(result['case_changes'], 0)
        self.assertFalse(result['clinical_validation'])

    def test_missing_and_duplicate_positions_rejected(self):
        for records in (self.value['criteria'][:-1], self.value['criteria'] + self.value['criteria'][:1]):
            value = deepcopy(self.value); value['criteria'] = records
            with self.assertRaises(ValueError): review.validate(ROOT, value)

    def test_changed_artifact_and_requirement_hashes_rejected(self):
        value = deepcopy(self.value); value['artifact_hashes']['cases'] = 'f'*64
        with self.assertRaises(ValueError): review.validate(ROOT, value)
        value = deepcopy(self.value); value['criteria'][0]['binding']['requirements_sha256'] = 'f'*64
        with self.assertRaises(ValueError): review.validate(ROOT, value)

    def test_cannot_promote_review_to_clinical_approval(self):
        value = deepcopy(self.value); value['clinical_validation'] = True
        with self.assertRaises(ValueError): review.validate(ROOT, value)
        value = deepcopy(self.value); value['criteria'][0]['resolved'] = True
        with self.assertRaises(ValueError): review.validate(ROOT, value)

    def test_each_position_needs_both_languages_and_next_control(self):
        for key in ('question_en','question_zh','next_control'):
            value = deepcopy(self.value); value['criteria'][0][key] = ''
            with self.subTest(key=key), self.assertRaises(ValueError): review.validate(ROOT, value)


if __name__ == '__main__': unittest.main()
