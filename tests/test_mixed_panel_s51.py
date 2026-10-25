"""Offline mixed-panel fixtures. No credentials, network or clinical expectations."""

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts import mixed_panel_s51 as run
from tests.test_workflow_s38 import envelope, judgment_fixture
from tests.test_usage_s39 import usage_fixture

ROOT = Path(__file__).resolve().parents[1]


def imports():
    rows = [r for r in run.old.schedule(ROOT, run.old.plan(ROOT)) if r["kind"] == "candidate"]
    answers = {run.workflow.answer_key(r): {"text": f'Imported fixture {r["model"]} {r["language"]} {r["stage"]}.'} for r in rows}
    catalog, controls = run.workflow.families(ROOT), run.score.controls(ROOT)
    records = []
    for row in rows:
        result = answers[run.workflow.answer_key(row)]
        payload = run.workflow.request_context(ROOT, row, catalog, controls, answers)["payload"]
        family = catalog[row["family_id"]][0]
        records.append({"row": row, "result": result, "binding": {
            "case_version": family["version"], "case_content_hash": run.workflow.variant_hash(family, row["language"]),
            "answer_sha256": run.sha256_json(result), "raw_sha256": hashlib.sha256(envelope(row, result["text"])).hexdigest(),
            "payload_sha256": hashlib.sha256(run.guard._json_bytes(payload)).hexdigest()}})
    return records


def reply(session, transform=None):
    row = session.pending
    if row["kind"] == "candidate":
        text = f'New fixture {row["model"]} {row["family_id"]} {row["language"]} {row["stage"]}.'
    else:
        text = json.dumps(judgment_fixture(session.contexts[row["sequence"]]["packet"], row["profile"]))
    raw = json.loads(envelope(row, text))
    raw["usage"] = usage_fixture(row["provider"])
    if transform:
        transform(raw)
    return json.dumps(raw, ensure_ascii=False).encode()


def advance(session, until=None):
    while (until is None or session.index < until) and session.prepare() is not None:
        session.record(reply(session))
    return session


class MixedPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = imports()
        cls.complete = advance(run.Rehearsal(ROOT, cls.records, mode="offline_fixture"))

    def new(self, **kwargs):
        return run.Rehearsal(ROOT, self.records, mode="offline_fixture", **kwargs)

    def test_fixed_manifest_and_roster(self):
        cells = run.conversation_manifest(ROOT)
        self.assertEqual(len(cells), 72)
        self.assertEqual(len({(c['family_id'],c['language'],c['candidate_model']) for c in cells}),72)
        self.assertEqual(sum(c['comparative_review_hold'] for c in cells),8)
        self.assertEqual({c['candidate_model'] for c in cells},set(run.old.plan(ROOT)['candidate_models']))
        self.assertTrue(all(c['family_id'] in run.FAMILIES for c in cells))

    def test_schedule_has_no_import_regeneration(self):
        rows = run.schedule(ROOT)
        self.assertEqual(len(rows),452)
        self.assertTrue(all(r['kind']=='candidate' and r['family_id']!=run.HOLD for r in rows[:128]))
        self.assertTrue(all(r['block']=='control' for r in rows[128:164]))
        self.assertTrue(all(r['block']=='development' and not r['repeat'] for r in rows[164:308]))
        self.assertTrue(all(r['block']=='development' and r['repeat'] for r in rows[308:]))
        self.assertEqual([r['sequence'] for r in rows],list(range(1,453)))

    def test_missing_duplicate_and_foreign_imports_rejected(self):
        for records in (self.records[:-1],self.records+self.records[:1]):
            with self.assertRaises(ValueError):run.validate_import_records(ROOT,records)
        records=deepcopy(self.records); records[0]['row']['family_id']='HC-MT-REASON-015'
        with self.assertRaises(ValueError):run.validate_import_records(ROOT,records)

    def test_case_answer_raw_and_payload_bindings(self):
        for key,value in (('case_version','wrong'),('case_content_hash','f'*64),
                          ('answer_sha256','e'*64),('payload_sha256','d'*64),('raw_sha256','not-a-hash')):
            records=deepcopy(self.records);records[0]['binding'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):run.validate_import_records(ROOT,records)

    def test_model_provider_stage_language_and_extra_fields(self):
        for key,value in (('provider','grok'),('model','grok-4.7'),('stage','update'),
                          ('language','fr'),('kind','judge'),('repeat',True)):
            records=deepcopy(self.records);records[0]['row'][key]=value
            with self.subTest(key=key),self.assertRaises((ValueError,KeyError)):
                run.validate_import_records(ROOT,records)
        records=deepcopy(self.records);records[0]['result']['reasoning']='not an answer'
        with self.assertRaises(ValueError):run.validate_import_records(ROOT,records)

    def test_changed_initial_answer_cannot_keep_old_update_request(self):
        records=deepcopy(self.records)
        record=next(x for x in records if x['row']['stage']=='initial')
        record['result']['text']+=' Changed history.'
        record['binding']['answer_sha256']=run.sha256_json(record['result'])
        with self.assertRaisesRegex(ValueError,'history'):run.validate_import_records(ROOT,records)

    def test_source_verification_requires_actual_replay_and_pins(self):
        spec=run.saved.plan(ROOT)
        value={'mode':'live','bank':{'mode':'live','answers':self.records},
               'source_sha256':spec['source_sha256'],'source_protocol_sha256':spec['source_protocol_sha256'],
               'bank_sha256':spec['source_bank']['sha256']}
        with patch.object(run.saved,'source',return_value=value) as source:
            with self.assertRaises(ValueError):run.verified_source(ROOT)
            source.assert_called_once_with(ROOT)

    def test_offline_plan_does_not_read_source_or_credentials(self):
        with patch.object(run.saved,'source',side_effect=AssertionError('Private source accessed')), \
             patch.object(run.old.prior,'read_setting',side_effect=AssertionError('Key read')):
            result=run.readiness(ROOT)
        self.assertFalse(result['private_source_verified'])
        self.assertEqual(result['verified_imported_stages'],0)
        self.assertFalse(result['live_execution_available'])
        self.assertIsNone(result['live_budget_usd'])

    def test_live_mode_and_cli_run_are_unavailable(self):
        with self.assertRaises(ValueError):run.Rehearsal(ROOT,self.records,mode='live')
        p=subprocess.run([sys.executable,'-m','scripts.mixed_panel_s51','run'],cwd=ROOT,capture_output=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn(b'invalid choice',p.stderr)

    def test_complete_rehearsal_keeps_fixed_denominator_and_no_scores(self):
        result=self.complete.report()
        self.assertEqual(result['terminal'],'schedule_complete')
        self.assertEqual(result['simulated_attempts'],452)
        self.assertEqual(result['answer_stages_present'],144)
        self.assertEqual(len(result['conversations']),72)
        self.assertTrue(result['control_gate']['pass'])
        self.assertTrue(all(len(c['first_judgment_stages_present'])==len(c['repeat_judgment_stages_present'])==2
                            for c in result['conversations']))
        self.assertTrue(result['simulation_only'])
        self.assertFalse(result['numeric_scores'])
        self.assertEqual(result['live_calls'],0)

    def test_all_repeats_are_identical_payloads(self):
        s=self.complete
        for row in s.rows:
            if row['kind']=='judge' and row['repeat']:
                key=run.workflow.judgment_key({**row,'repeat':False})
                self.assertEqual(run.guard._json_bytes(s.contexts[row['sequence']]['payload']),s.first_payloads[key])

    def test_uniform_judge_draft_and_unchanged_candidate_settings(self):
        s=self.complete
        for row in s.rows:
            payload=s.contexts[row['sequence']]['payload']
            if row['kind']=='judge':
                self.assertEqual(payload['generation_config'],{'max_output_tokens':32768,'thinking_level':'medium'})
            else:
                original=run.workflow.request_context(ROOT,row,s.catalog,s.controls,s.answers)['payload']
                self.assertEqual(original,payload)

    def test_update_history_is_same_model_and_not_reference_labels(self):
        s=self.complete
        for row in s.rows[:128]:
            serialized=json.dumps(s.contexts[row['sequence']]['payload'],ensure_ascii=False)
            family=s.catalog[row['family_id']][0]
            text=s.answers[run.workflow.answer_key(row,'initial')]['text']
            if row['stage']=='update':self.assertIn(text,serialized)
            else:
                self.assertNotIn(text,serialized)
                self.assertNotIn(family['variants'][row['language']]['turns'][1]['user'],serialized)
            self.assertNotIn('critical_requirements',serialized)
            self.assertNotIn('criterion_anchors',serialized)

    def test_initial_judge_excludes_update_and_model_identity(self):
        for row in self.complete.rows:
            if row['kind']=='judge' and row['block']=='development' and row['stage']=='initial':
                packet=self.complete.contexts[row['sequence']]['packet']
                serialized=json.dumps(packet,ensure_ascii=False)
                self.assertNotIn(self.complete.answers[run.workflow.answer_key(row,'update')]['text'],serialized)
                self.assertNotIn('candidate_model',packet)
                self.assertEqual(len(packet['transcript']),2)

    def test_pending_request_and_duplicate_reply_rejected(self):
        s=self.new();s.prepare()
        with self.assertRaises(ValueError):s.prepare()
        s.record(reply(s))
        with self.assertRaises(ValueError):s.record(b'{}')

    def test_known_cost_failure_closes_only_candidate_lane(self):
        s=self.new();first=s.prepare()['row']
        s.record(reply(s,lambda raw:raw.update(status='incomplete')))
        self.assertIsNone(s.terminal)
        next_row=s.prepare()['row']
        self.assertNotEqual(first['model'],next_row['model'])
        self.assertEqual(s.outcomes[2]['reason'],'model_lane_closed')
        self.assertEqual(len(s.report()['conversations']),72)
        self.assertEqual(len(s.answers),16)

    def test_unknown_cost_stops_globally_without_retry(self):
        s=self.new();s.prepare()
        s.record(reply(s,lambda raw:raw.pop('usage')))
        self.assertEqual(s.terminal,'unknown_charge')
        self.assertIsNone(s.prepare())
        self.assertEqual(s.report()['unknown_simulated_charge_attempts'],1)
        self.assertEqual(len(s.report()['conversations']),72)

    def test_malformed_response_is_unknown_not_free(self):
        s=self.new();s.prepare();s.record(b'not json')
        self.assertEqual(s.terminal,'unknown_charge')
        self.assertIsNone(s.prepare())

    def test_threshold_overrun_stops_after_one_supplied_reply(self):
        s=self.new(fixture_threshold_usd='0.01');s.prepare()
        def expensive(raw):
            raw['usage'].update(total_input_tokens=1000,total_output_tokens=8000,total_thought_tokens=22,total_tokens=9022)
        s.record(reply(s,expensive))
        self.assertEqual(s.terminal,'spend_threshold_reached')
        self.assertIsNone(s.prepare())
        self.assertGreater(Decimal(s.report()['simulated_monitoring_usd']),Decimal('.01'))

    def test_invalid_fixture_threshold(self):
        for value in ('0','-1','NaN','Infinity','0.001'):
            with self.subTest(value=value),self.assertRaises(ValueError):self.new(fixture_threshold_usd=value)

    def test_out_of_scope_usage_stays_unknown(self):
        s=self.new();s.prepare()
        def too_long(raw):
            raw['usage'].update(total_input_tokens=16001,total_output_tokens=20,total_thought_tokens=22,total_tokens=16043)
        s.record(reply(s,too_long))
        self.assertEqual(s.terminal,'unknown_charge')
        self.assertIsNone(s.prepare())

    def test_unexpected_local_failure_cannot_accept_second_reply(self):
        s=self.new();s.prepare();raw=reply(s)
        with patch.object(run.saved.previous,'account',side_effect=RuntimeError('fixture interruption')):
            with self.assertRaises(RuntimeError):s.record(raw)
        self.assertEqual(s.terminal,'local_reply_failure')
        with self.assertRaises(ValueError):s.record(raw)
        with self.assertRaises(ValueError):s.prepare()

    def test_missing_initial_and_missing_conversation_skip_not_zero(self):
        s=self.new();row=s.rows[1]
        self.assertEqual(s.skip_reason(row),'initial_answer_missing')
        judge=s.rows[164]
        self.assertEqual(s.skip_reason(judge),'candidate_conversation_missing')
        result=s.report()
        self.assertEqual(result['expected_conversations'],72)
        self.assertEqual(sum(len(c['answer_stages_present']) for c in result['conversations']),16)
        self.assertTrue(all('point_score' not in c for c in result['conversations']))

    def test_failed_control_gate_blocks_development(self):
        s=deepcopy(self.complete)
        s.judgments={k:v for k,v in s.judgments.items() if k[1]!='control'}
        row=s.rows[164]
        self.assertEqual(s.skip_reason(row),'judge_control_gate_not_passed')

    def test_repeat_drift_stops_instead_of_sending_changed_answer(self):
        s=deepcopy(self.complete);s.index=308;s.terminal=None
        row=s.rows[308]
        s.answers[run.workflow.answer_key(row,'initial')]['text']+=' Tampered.'
        with self.assertRaisesRegex(ValueError,'repeat payload drift'):s.prepare()
        self.assertEqual(s.terminal,'local_context_failure')
        self.assertIsNone(s.prepare())

    def test_source_answers_are_copied_not_mutated(self):
        before=deepcopy(self.records)
        s=self.new();s.prepare();s.record(reply(s))
        self.assertEqual(self.records,before)


if __name__=='__main__':unittest.main()
