import unittest
from pathlib import Path

from benchmark.batch_l_packet_audit import audit, validate_packet
from benchmark.config import load_json

ROOT=Path(__file__).resolve().parents[1]


class BatchLAnswerPacketTests(unittest.TestCase):
    def setUp(self):
        self.data=load_json(ROOT/'data/multiturn/batch_l_cases.json')
        self.anchors=load_json(ROOT/'config/multiturn_criterion_anchors_batch_l_v1.json')
        self.contrasts=load_json(ROOT/'data/multiturn/batch_l_contrasts_v1.json')
        self.provenance=load_json(ROOT/'data/multiturn/batch_l_provenance.json')

    def check(self):
        return validate_packet(self.data,self.anchors,self.contrasts,self.provenance)

    def test_all_five_families_and_exact_edits(self):
        result=audit(ROOT)
        self.assertEqual(result['criterion_positions'],34)
        self.assertEqual(result['variant_count'],10)
        self.assertEqual(result['update_answer_examples'],30)
        self.assertEqual(len(set(result['packet_hashes'].values())),30)
        self.assertEqual(result['judge_calls'],0)

    def test_response_or_case_tamper_fails(self):
        self.contrasts['probes'][0]['partial_update_response']+=' extra change'
        with self.assertRaisesRegex(ValueError,'single edit'):self.check()
        self.setUp()
        self.data['families'][0]['variants']['en']['turns'][0]['user']+=' altered'
        with self.assertRaisesRegex(ValueError,'Stale'):self.check()

    def test_missing_language_or_invented_error_fails(self):
        self.contrasts['probes'].pop()
        with self.assertRaisesRegex(ValueError,'paired language'):self.check()
        self.setUp()
        self.contrasts['probes'][0]['expected_unsafe_error_id']='invented'
        with self.assertRaisesRegex(ValueError,'Invented critical error'):self.check()

    def test_missing_source_and_anchor_fails(self):
        self.provenance['records'][0]['requirement_support'].pop()
        with self.assertRaisesRegex(ValueError,'source mapping'):self.check()
        self.setUp()
        self.anchors['families'].pop()
        with self.assertRaisesRegex(ValueError,'coverage mismatch'):self.check()


if __name__=='__main__':
    unittest.main()
