import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark import scoring_s26 as base, scoring_s28 as experiment
from benchmark.boundary_s27 import check_manifest as check_s27
from benchmark.providers.http_json import ProviderRequestError

ROOT=Path(__file__).resolve().parents[1]


class FullScoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.policy,self.packets,self.controls=experiment.inputs(ROOT)

    def fake_request(self,provider,model,key,packet,instruction,timeout):
        name=next(k for k,p in self.packets.items() if p==packet)
        rows=[dict(stage_id=a['stage_id'],requirement_index=a['requirement_index'],status='met',
                   response_evidence=packet['transcript'][1 if a['stage_id']=='initial' else 3]['content'],
                   rationale='Synthetic software fixture') for a in packet['criterion_anchors']]
        errors=[]
        if name.endswith('__partial'): rows[-1]['status']='partial'
        if name.endswith('__unsafe'):
            for row in rows:
                if row['stage_id']=='update': row['status']='missed'
            error=next(e for t in packet['turn_labels'] for e in t['critical_errors'] if e['id']==self.controls[name])
            errors=[dict(stage_id='update',error_id=error['id'],severity=error['severity'],rationale='Synthetic error fixture')]
        judgment={'criterion_assessments':rows,'critical_errors':errors,
                  'dimension_observations':[dict(dimension=d,decision='no_distinct_failure',response_evidence='',
                    new_fact='Synthetic update',independent_consequence_or_failure='',overlap_note='No separate penalty')
                    for d in ('safety','revision')]}
        text=json.dumps(judgment)
        raw={'status':'completed','model':model}
        raw.update({'steps':[{'type':'model_output','content':[{'type':'text','text':text}]}]} if provider=='gemini'
                   else {'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]})
        return raw,1

    def test_frozen_history_and_unchanged_arithmetic(self):
        base.check_manifest(ROOT); check_s27(ROOT); experiment.check_manifest(ROOT)
        old,packets,_=base.inputs(ROOT)
        self.assertEqual(len(experiment.schedule(self.policy,self.packets)),32)
        for key in old:
            if key!='version': self.assertEqual(self.policy[key],old[key])
        for key,packet in packets.items():
            self.assertEqual(packet['transcript'],self.packets[key]['transcript'])
            self.assertEqual(packet['turn_labels'],self.packets[key]['turn_labels'])
        self.assertNotEqual(packets['HC-MT-TRIAGE-018__en__unsafe']['criterion_anchors'],
                            self.packets['HC-MT-TRIAGE-018__en__unsafe']['criterion_anchors'])

    def test_complete_mock_panel_and_saved_binding(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, \
             patch.object(experiment,'read_setting',return_value='unused'), \
             patch.object(base,'request_judgment',side_effect=self.fake_request) as request:
            output=Path(tmp)/'run'
            result=experiment.run(ROOT,output,ROOT/'unused',32)
            self.assertTrue(result['advance_to_small_candidate_pilot'])
            self.assertEqual((request.call_count,result['exact_partial_repeats']),(32,8))
            raw=json.loads((output/'01.response.json').read_text())
            raw['model']='tampered'
            (output/'01.response.json').write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError,'mismatch'): experiment.audit(ROOT,output)

    def test_transport_stop_no_retry_or_resume(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, \
             patch.object(experiment,'read_setting',return_value='unused'), \
             patch.object(base,'request_judgment',side_effect=ProviderRequestError('unknown')) as request:
            output=Path(tmp)/'run'
            result=experiment.run(ROOT,output,ROOT/'unused',32)
            self.assertEqual((result['attempted_calls'],result['valid_judgments']),(1,0))
            self.assertFalse(result['advance_to_small_candidate_pilot'])
            with self.assertRaisesRegex(ValueError,'fresh ignored'): experiment.run(ROOT,output,ROOT/'unused',32)
            self.assertEqual(request.call_count,1)

    def test_invalid_raw_response_kept_no_repair(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, \
             patch.object(experiment,'read_setting',return_value='unused'), \
             patch.object(base,'request_judgment',return_value=({'status':'failed','model':'test'},1)) as request:
            output=Path(tmp)/'run'
            result=experiment.run(ROOT,output,ROOT/'unused',32)
            self.assertEqual(request.call_count,1)
            self.assertTrue((output/'01.response.json').exists())
            self.assertEqual(result['stopped']['delivery'],'response_saved_validation_failed')

    def test_unclear_cannot_pass_strict_point_order(self):
        original=self.fake_request
        def unclear(*args):
            raw,latency=original(*args)
            judgment=base.parse_response(raw,args[0])
            judgment['criterion_assessments'][-1]['status']='unclear'
            steps=raw['steps'] if args[0]=='gemini' else raw['output']
            steps[0]['content'][0]['text']=json.dumps(judgment)
            return raw,latency
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, \
             patch.object(experiment,'read_setting',return_value='unused'), \
             patch.object(base,'request_judgment',side_effect=unclear):
            result=experiment.run(ROOT,Path(tmp)/'run',ROOT/'unused',32)
            self.assertEqual(result['strict_answer_order_groups'],0)
            self.assertFalse(result['advance_to_small_candidate_pilot'])

    def test_missing_prefix_or_false_completion_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, \
             patch.object(experiment,'read_setting',return_value='unused'), \
             patch.object(base,'request_judgment',side_effect=ProviderRequestError('unknown')):
            output=Path(tmp)/'run'
            experiment.run(ROOT,output,ROOT/'unused',32)
            (output/'01.attempt.json').rename(output/'02.attempt.json')
            with self.assertRaisesRegex(ValueError,'scheduled prefix'): experiment.audit(ROOT,output)


if __name__=='__main__': unittest.main()
