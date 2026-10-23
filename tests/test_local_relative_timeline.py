import unittest
from benchmark.local_relative_timeline import build_timeline


class RelativeTimelineTests(unittest.TestCase):
    def setUp(self):
        self.manifest={'status':'owner_attested_single_encounter_not_independently_identifier_verified',
                       'files':[{'source_sha256':'a','page_count':1},{'source_sha256':'b','page_count':1}]}
        self.facts={'sources':[{'source_sha256':s,'page':1,'verified_source_rows':[{'analyte':'synthetic'}]} for s in ('a','b')]}
        self.review={'verified_time_cells':[
            dict(source_sha256='a',page=1,role='collection',source_label='采样时间',local_date_time='2024-01-02T10:00:00',
                 precision='second',status='source_label_and_value_visually_checked'),
            dict(source_sha256='b',page=1,role='received',source_label='接收时间',local_date_time='2024-01-03T11:00:00',
                 precision='second',status='source_label_and_value_visually_checked')]}

    def test_receipt_does_not_place_collection_or_expose_future_results(self):
        result=build_timeline(self.manifest,self.facts,self.review)
        self.assertEqual(result['events'][1]['relative_day'],1)
        self.assertEqual(len(result['collection_linked_lab_pages']),1)
        self.assertIsNone(result['lab_pages_without_verified_collection'][0]['collection_relative_day'])
        self.assertFalse(any(e['decision_time_result_available'] for e in result['events']))
        self.assertNotIn('2024-',str(result))
        self.assertFalse(result['case_ready'])

    def test_ocr_only_or_mislabeled_time_rejected(self):
        self.review['verified_time_cells'][0]['status']='ocr_candidate'
        with self.assertRaisesRegex(ValueError,'Unverified'):build_timeline(self.manifest,self.facts,self.review)
        self.setUp();self.review['verified_time_cells'][1]['role']='collection'
        with self.assertRaisesRegex(ValueError,'role mismatch'):build_timeline(self.manifest,self.facts,self.review)

    def test_no_collection_anchor_or_foreign_source_rejected(self):
        self.review['verified_time_cells'].pop(0)
        with self.assertRaisesRegex(ValueError,'No verified collection'):build_timeline(self.manifest,self.facts,self.review)
        self.setUp();self.review['verified_time_cells'][0]['source_sha256']='outside'
        with self.assertRaisesRegex(ValueError,'out-of-scope'):build_timeline(self.manifest,self.facts,self.review)


if __name__=='__main__':unittest.main()
