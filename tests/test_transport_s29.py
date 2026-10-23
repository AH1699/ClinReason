import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark import scoring_s26 as base, scoring_s28, transport_s29 as exp
from benchmark.providers.observed_http import DiagnosticRequestError
from tests import test_scoring_s28 as fixtures

ROOT=Path(__file__).resolve().parents[1]


class TransportDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.helper=fixtures.FullScoreIntegrationTests()
        self.helper.setUp()

    def fake(self,*args,**kwargs):
        self.assertIs(kwargs['transport'],exp.post_json_observed)
        self.assertEqual(args[-1],240)
        return self.helper.fake_request(*args)

    def test_frozen_exact_failed_packet(self):
        exp.check_manifest(ROOT); scoring_s28.check_manifest(ROOT)
        policy,_,packet=exp.inputs(ROOT)
        self.assertEqual(packet,self.helper.packets['HC-MT-TRIAGE-020__en__partial'])
        self.assertEqual(policy['maximum_calls'],2)

    def test_two_call_cap_and_no_clinical_gate(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, patch.object(exp,'read_setting',return_value='unused'), \
                patch.object(base,'request_judgment',side_effect=self.fake) as request:
            output=Path(tmp)/'run'; result=exp.run(ROOT,output,ROOT/'unused',2)
            self.assertEqual(request.call_count,2)
            self.assertTrue(result['may_design_fresh_full_panel'])
            self.assertFalse(result['calibration_complete'])
            with self.assertRaisesRegex(ValueError,'fresh'):exp.run(ROOT,output,ROOT/'unused',2)
            raw=json.loads((output/'01.response.json').read_text()); raw['model']='wrong'
            (output/'01.response.json').write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError,'mismatch'):exp.audit(ROOT,output)

    def test_transport_failure_saved_secret_free_and_stops(self):
        d={'version':'transport-diagnostic-v1','category':'timeout','http_status':None,'elapsed_ms':240001,
           'delivery':'unknown','attempts':1,'automatic_retries':0}
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, patch.object(exp,'read_setting',return_value='unused'), \
                patch.object(base,'request_judgment',side_effect=DiagnosticRequestError(d)) as request:
            output=Path(tmp)/'run'; result=exp.run(ROOT,output,ROOT/'unused',2)
            self.assertEqual(request.call_count,1)
            self.assertEqual(result['stopped']['diagnostic'],d)
            self.assertFalse(result['may_design_fresh_full_panel'])
            marker=json.loads((output/'stopped.json').read_text());marker['diagnostic']['body']='secret'
            (output/'stopped.json').write_text(json.dumps(marker))
            with self.assertRaisesRegex(ValueError,'unsafe diagnostic'):exp.audit(ROOT,output)

    def test_validation_failure_preserves_raw(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, patch.object(exp,'read_setting',return_value='unused'), \
                patch.object(base,'request_judgment',return_value=({'status':'failed','model':'grok-4.7'},1)) as request:
            output=Path(tmp)/'run'; result=exp.run(ROOT,output,ROOT/'unused',2)
            self.assertEqual(request.call_count,1)
            self.assertEqual(result['stopped']['kind'],'response_validation_failure')
            self.assertTrue((output/'01.response.json').exists())

    def test_nonprefix_and_false_completion_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp, patch.object(exp,'read_setting',return_value='unused'), \
                patch.object(base,'request_judgment',side_effect=self.fake):
            output=Path(tmp)/'run';exp.run(ROOT,output,ROOT/'unused',2)
            (output/'01.attempt.json').rename(output/'03.attempt.json')
            with self.assertRaisesRegex(ValueError,'prefix'):exp.audit(ROOT,output)


if __name__=='__main__':unittest.main()
