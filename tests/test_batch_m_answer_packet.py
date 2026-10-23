import unittest
from pathlib import Path
from benchmark.batch_m_packet_audit import audit, validate_packet
from benchmark.config import load_json

ROOT=Path(__file__).resolve().parents[1]


class BatchMAnswerPacketTests(unittest.TestCase):
    def setUp(self):
        self.data=load_json(ROOT/'data/multiturn/batch_m_cases.json')
        self.anchors=load_json(ROOT/'config/multiturn_criterion_anchors_batch_m_v1.json')
        self.contrasts=load_json(ROOT/'data/multiturn/batch_m_contrasts_v1.json')
        self.provenance=load_json(ROOT/'data/multiturn/batch_m_provenance.json')

    def check(self):return validate_packet(self.data,self.anchors,self.contrasts,self.provenance)

    def test_thirteen_boundaries_twelve_controlled_answers(self):
        result=audit(ROOT)
        self.assertEqual(result['criterion_positions'],13)
        self.assertEqual(result['update_answer_examples'],12)
        self.assertEqual(len(set(result['packet_hashes'].values())),12)
        self.assertEqual(result['judge_calls'],0)

    def test_case_and_answer_edits_fail(self):
        self.contrasts['probes'][0]['unsafe_update_response']+=' hidden change'
        with self.assertRaisesRegex(ValueError,'declared edits'):self.check()
        self.setUp();self.data['families'][0]['variants']['en']['turns'][0]['user']+=' changed'
        with self.assertRaisesRegex(ValueError,'Stale'):self.check()

    def test_missing_language_source_or_anchor(self):
        self.contrasts['probes'].pop()
        with self.assertRaisesRegex(ValueError,'paired language'):self.check()
        self.setUp();self.provenance['records'][0]['requirement_support'].pop()
        with self.assertRaisesRegex(ValueError,'source mapping'):self.check()
        self.setUp();self.anchors['families'].pop()
        with self.assertRaisesRegex(ValueError,'coverage mismatch'):self.check()

    def test_invented_error_or_unpaired_edit(self):
        self.contrasts['probes'][0]['expected_unsafe_error_id']='invented'
        with self.assertRaisesRegex(ValueError,'Invented critical'):self.check()
        self.setUp();self.contrasts['probes'][1]['construction']['partial_omitted_requirement_index']=3
        with self.assertRaisesRegex(ValueError,'Bilingual edit'):self.check()


if __name__=='__main__':unittest.main()
