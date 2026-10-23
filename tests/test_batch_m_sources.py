import unittest
from pathlib import Path
from benchmark.config import load_json
from benchmark.multiturn import validate_multiturn_dataset

ROOT=Path(__file__).resolve().parents[1]


class BatchMSourceTests(unittest.TestCase):
    def setUp(self):
        self.batch=load_json(ROOT/'data/multiturn/batch_m_cases.json')
        self.ledger=load_json(ROOT/'data/multiturn/batch_m_provenance.json')

    def test_two_bilingual_drafts_no_approval(self):
        result=validate_multiturn_dataset(self.batch)
        self.assertEqual((result['family_count'],result['variant_count']),(2,4))
        self.assertFalse(result['clinical_review_complete'])
        self.assertFalse(result['language_review_complete'])
        self.assertEqual(self.ledger['split'],'public_development_not_calibration_or_gold')

    def test_all_thirteen_criteria_have_ordered_source_positions(self):
        records={r['family_id']:r for r in self.ledger['records']}
        self.assertEqual(set(records),{f['family_id'] for f in self.batch['families']})
        count=0
        for family in self.batch['families']:
            record=records[family['family_id']]
            expected=[(t['stage_id'],i) for t in family['variants']['en']['turns']
                      for i in range(1,len(t['critical_requirements'])+1)]
            self.assertEqual([(r['stage'],r['index']) for r in record['requirement_support']],expected)
            self.assertEqual(set(family['source_refs']),set(record['supporting_sources']))
            for entry in record['requirement_support']:
                self.assertIn(entry['guidance_url'],family['source_refs']);self.assertTrue(entry['basis'])
            for en,zh in zip(family['variants']['en']['turns'],family['variants']['zh-Hans']['turns']):
                self.assertEqual(len(en['critical_requirements']),len(zh['critical_requirements']))
            count+=len(expected)
        self.assertEqual(count,13)

    def test_purchased_source_locators_and_limits(self):
        for record in self.ledger['records']:
            self.assertTrue(record['raw_resource_local_only'].startswith('purchasedAssets/'))
            self.assertTrue(all(type(p) is int and p>0 for p in record['pdf_pages_one_based']))
            self.assertTrue(record['review_questions']);self.assertTrue(record['critical_error_basis'])
            self.assertTrue(record['outdated_source_warning'])
        self.assertIn('SIADH',self.ledger['records'][0]['outdated_source_warning'])


if __name__=='__main__': unittest.main()
