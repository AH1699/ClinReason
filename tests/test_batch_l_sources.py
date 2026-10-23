import unittest
from pathlib import Path

from benchmark.config import load_json
from benchmark.multiturn import validate_multiturn_dataset


ROOT = Path(__file__).resolve().parents[1]


class BatchLSourceTests(unittest.TestCase):
    def setUp(self):
        self.batch = load_json(ROOT / 'data/multiturn/batch_l_cases.json')
        self.provenance = load_json(ROOT / 'data/multiturn/batch_l_provenance.json')

    def test_five_bilingual_drafts_not_gold(self):
        result = validate_multiturn_dataset(self.batch)
        self.assertEqual(result['family_count'], 5)
        self.assertEqual(result['variant_count'], 10)
        self.assertFalse(result['clinical_review_complete'])
        self.assertFalse(result['language_review_complete'])
        self.assertEqual(self.provenance['split'], 'public_development_not_calibration_or_gold')

    def test_every_criterion_has_one_ordered_source_mapping(self):
        records = {r['family_id']: r for r in self.provenance['records']}
        self.assertEqual(set(records), {f['family_id'] for f in self.batch['families']})
        total = 0
        for family in self.batch['families']:
            record = records[family['family_id']]
            self.assertEqual(set(record['supporting_sources']), set(family['source_refs']))
            expected = [(t['stage_id'], i) for t in family['variants']['en']['turns']
                        for i in range(1, len(t['critical_requirements']) + 1)]
            actual = [(r['stage'], r['index']) for r in record['requirement_support']]
            self.assertEqual(actual, expected)
            total += len(expected)
            for item in record['requirement_support']:
                self.assertIn(item['guidance_url'], family['source_refs'])
                self.assertTrue(item['basis'])
            self.assertTrue(record['review_questions'])
            for english, chinese in zip(family['variants']['en']['turns'], family['variants']['zh-Hans']['turns']):
                self.assertEqual(len(english['critical_requirements']), len(chinese['critical_requirements']))
        self.assertEqual(total, 34)

    def test_exam_locators_do_not_substitute_for_current_answer_sources(self):
        for record in self.provenance['records']:
            self.assertTrue(record['raw_resource_local_only'].startswith('purchasedAssets/'))
            self.assertTrue(all(type(p) is int and p > 0 for p in record['pdf_pages_one_based']))
            self.assertTrue(record['outdated_source_warning'])
            self.assertTrue(record['critical_error_basis'])
        joint = self.provenance['records'][1]
        self.assertIn('negative-Gram', joint['outdated_source_warning'])
        hbv = self.provenance['records'][3]
        self.assertIn('not an anti-CD20', hbv['outdated_source_warning'])


if __name__ == '__main__':
    unittest.main()
