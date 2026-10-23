import unittest
from benchmark.local_record_linkage import acceptable,compare,extract_fields,LABELS


class RecordLinkageTests(unittest.TestCase):
    def test_same_row_not_next_ocr_line(self):
        boxes=[{'text':'采样时间：','bounds':[.1,.5,.25,.52]},
               {'text':'2020-01-03 11:30','bounds':[.3,.5,.5,.52]},
               {'text':'2020-01-04','bounds':[.3,.55,.5,.57]}]
        values=extract_fields(boxes)['collection']
        self.assertEqual([r['value'] for r in values],['2020-01-03T11:30:00'])
        self.assertEqual(values[0]['method'],'same_visual_row')

    def test_do_not_jump_over_other_cell_or_parse_invalid_date(self):
        boxes=[{'text':'采样日期','bounds':[.1,.5,.25,.52]},
               {'text':'报告日期','bounds':[.26,.5,.35,.52]},
               {'text':'2020-01-03','bounds':[.36,.5,.5,.52]}]
        self.assertEqual(extract_fields(boxes)['collection'],[])
        self.assertIsNone(acceptable('collection','2020-01-019'))
        self.assertIsNone(acceptable('collection','2020-02-31'))

    def test_report_time_never_substitutes_for_collection(self):
        fields=extract_fields([{'text':'报告时间：2020-01-03 11:30','bounds':[.1,.5,.5,.52]}])
        self.assertTrue(fields['reported']);self.assertFalse(fields['collection'])

    def test_name_match_is_not_encounter_approval_and_conflicts_hold(self):
        left={r:[] for r in LABELS};right={r:[] for r in LABELS}
        for fields in (left,right):
            fields['patient_name']=[{'value':'测试人'}];fields['sex']=[{'value':'女'}]
        result=compare(left,right)
        self.assertTrue(result['same_person_candidate'])
        self.assertFalse(result['same_admission_candidate']);self.assertFalse(result['verified_linkage'])
        left['admission_id']=[{'value':'0001'}];right['admission_id']=[{'value':'0002'}]
        self.assertFalse(compare(left,right)['same_person_candidate'])
        self.assertEqual(compare(left,right)['conflicting_fields'],['admission_id'])

    def test_ambiguous_identity_not_cherry_picked(self):
        left={r:[] for r in LABELS};right={r:[] for r in LABELS}
        left['admission_id']=[{'value':'0001'},{'value':'0002'}]
        right['admission_id']=[{'value':'0001'}]
        self.assertIsNone(compare(left,right)['field_matches']['admission_id'])


if __name__=='__main__': unittest.main()
