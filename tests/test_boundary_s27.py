import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.boundary_s27 import inputs, schedule, validate, run, audit
from benchmark.config import load_json
from benchmark.providers.http_json import ProviderRequestError
from benchmark.scoring_s26 import check_manifest as check_s26

ROOT = Path(__file__).resolve().parents[1]


class BoundaryS27Tests(unittest.TestCase):
    def setUp(self):
        self.bundle = inputs(ROOT)
        self.policy, self.packets, self.expected, self.repeats = self.bundle

    def test_single_boundary_change_and_s26_preserved(self):
        old = load_json(ROOT/'config/multiturn_criterion_anchors_batch_g_v1.json')
        new = load_json(ROOT/'config/multiturn_criterion_anchors_batch_g_s27_v1.json')
        new['scope'] = old['scope']
        new['families'][0]['review_question'] = old['families'][0]['review_question']
        new['families'][0]['stages']['update'][1]['missed'] = old['families'][0]['stages']['update'][1]['missed']
        self.assertEqual(new, old)
        check_s26(ROOT)

    def test_packet_has_no_expected_label_or_profile(self):
        self.assertEqual(len(self.packets), 12)
        for packet in self.packets.values():
            self.assertEqual(set(packet), {'case_id','case_content_hash','language','transcript',
                                           'target_requirement','level_definitions'})
            self.assertNotIn('expected_status', json.dumps(packet))
        plan = schedule(self.policy, self.packets, self.repeats)
        self.assertEqual(len(plan), 32)
        self.assertEqual(sum(p[0] == 'repeat' for p in plan), 8)
        self.assertEqual(sum(v is not None for v in self.expected.values()), 10)

    def test_literal_update_evidence_and_absence(self):
        packet = self.packets['omitted__en']
        validate({'status':'missed','response_evidence':'','rationale':'The target plan is absent.'}, packet)
        for status, evidence in [('met',''),('partial','not a real quote'),('partial',packet['transcript'][1]['content'])]:
            with self.assertRaises(ValueError):
                validate({'status':status,'response_evidence':evidence,'rationale':'test'},packet)

    def mocks(self, root, handler):
        (root/'config').mkdir()
        (root/'config/s27_boundary_judge.txt').write_text('Synthetic test instruction')
        stack = contextlib.ExitStack()
        stack.enter_context(patch('benchmark.boundary_s27.check_manifest', return_value={}))
        stack.enter_context(patch('benchmark.boundary_s27.inputs', return_value=self.bundle))
        stack.enter_context(patch('benchmark.boundary_s27.read_setting', return_value='test-key'))
        request = stack.enter_context(patch('benchmark.boundary_s27.request', side_effect=handler))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        return stack, request

    def response(self, provider, model, key, packet, instruction, timeout):
        packet_key = next(k for k,v in self.packets.items() if v == packet)
        status = self.expected[packet_key] or 'unclear'
        judgment = {'status':status,'response_evidence': packet['transcript'][3]['content']
                    if status in ('met','partial') else '', 'rationale':'Synthetic expected-status fixture'}
        raw = {'status':'completed','model':model}
        if provider == 'gemini':
            raw['steps'] = [{'type':'model_output','content':[{'type':'text','text':json.dumps(judgment)}]}]
        else:
            raw['output'] = [{'type':'message','content':[{'type':'output_text','text':json.dumps(judgment)}]}]
        return raw, 1

    def test_mock_full_run_gate_and_saved_raw_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); output=root/'work/run'
            stack, request = self.mocks(root, self.response)
            with stack:
                result=run(root,output,root/'unused',32)
                self.assertEqual(request.call_count,32)
                self.assertEqual(result['known_status_matches'],20)
                self.assertEqual(result['repeat_status_matches'],8)
                self.assertTrue(result['ready_to_design_full_scoring_repeat'])
                self.assertFalse(result['candidate_pilot_authorized_by_this_probe'])
                path=output/'01.judgment.json'
                row=json.loads(path.read_text());row['judgment']['rationale']='tampered'
                path.write_text(json.dumps(row))
                with self.assertRaisesRegex(ValueError,'response/attempt mismatch'):
                    audit(root,output)

    def test_transport_stops_once_and_no_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); output=root/'work/run'
            stack, request = self.mocks(root, ProviderRequestError('unknown'))
            with stack:
                result=run(root,output,root/'unused',32)
                self.assertEqual((result['attempted_calls'],result['valid_judgments']), (1,0))
                self.assertEqual(result['stopped']['delivery'],'unknown')
                self.assertEqual(request.call_count,1)
                with self.assertRaisesRegex(ValueError,'fresh work/'):
                    run(root,output,root/'unused',32)

    def test_invalid_response_is_retained_without_repair(self):
        def invalid(*args):
            raw,_=self.response(*args)
            if args[0]=='gemini':raw['steps'][0]['content'][0]['text']='{}'
            else:raw['output'][0]['content'][0]['text']='{}'
            return raw,1
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); output=root/'work/run'
            stack, request = self.mocks(root,invalid)
            with stack:
                result=run(root,output,root/'unused',32)
                self.assertEqual(result['valid_judgments'],0)
                self.assertEqual(result['stopped']['delivery'],'response_saved_invalid')
                self.assertTrue((output/'01.response.json').exists())
                self.assertEqual(request.call_count,1)


if __name__ == '__main__':
    unittest.main()
