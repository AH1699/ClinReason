"""Synthetic transport and analysis tests, never evidence of judge accuracy."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import medication_boundary_s50 as run
from tests.test_transport_s39 import Connection, Response
from tests.test_usage_s39 import usage_fixture

ROOT = Path(__file__).resolve().parents[1]


def fixture(job, status="met"):
    packet = job["packet"]
    return {"criterion_assessments": [{"requirement_index": packet["target_requirements"][0]["requirement_index"],
        "status": status, "response_evidence": packet["transcript"][-1]["content"],
        "rationale": "Mechanically assigned fixture, not a clinical judgment."}]}


def judgments(selected):
    value, _, _ = run.draft.load(ROOT)
    expected = {p["id"]+"__"+lang: p["author_hypothesis"] or "unclear" for p in value["profiles"] for lang in run.draft.LANGS}
    return {j["row"]["sequence"]: fixture(j, expected[j["row"]["packet_key"]]) for j in selected}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.selected = run.jobs(ROOT)

    def test_56_requests_and_identical_blinded_repeats(self):
        self.assertEqual(len(self.selected), 56)
        self.assertEqual([j["row"]["phase"] for j in self.selected], ["first"]*28+["repeat"]*28)
        for first, repeat in zip(self.selected[:28], self.selected[28:]):
            self.assertEqual(first["payload"], repeat["payload"])
            self.assertEqual(first["row"]["packet_key"], repeat["row"]["packet_key"])
            self.assertEqual(first["payload"]["generation_config"], {"max_output_tokens":32768,"thinking_level":"medium"})
            outgoing = run.guard._json_bytes(first["payload"]).decode()
            for secret in (first["row"]["packet_key"], "author_hypothesis", "packet_key", "H140", "H137", "H136"):
                self.assertNotIn(secret, outgoing)
            self.assertNotIn("previous_interaction_id", outgoing)

    def test_schedule_is_hash_sorted_not_profile_order(self):
        hashes = [j["row"]["packet_sha256"] for j in self.selected[:28]]
        self.assertEqual(hashes, sorted(hashes)); self.assertEqual(len(set(hashes)), 28)

    def test_initial_packet_excludes_future_answer(self):
        for job in self.selected:
            if job["row"]["stage"] == "initial": self.assertEqual(len(job["packet"]["transcript"]), 2)
            else: self.assertEqual(len(job["packet"]["transcript"]), 4)

    def test_schema_targets_exactly_one_index(self):
        for job in self.selected[:28]:
            array = run.schema(job["packet"])["properties"]["criterion_assessments"]
            self.assertEqual((array["minItems"],array["maxItems"]),(1,1))
            self.assertEqual(array["items"]["properties"]["requirement_index"]["enum"],
                             [job["packet"]["target_requirements"][0]["requirement_index"]])

    def test_missing_extra_bad_index_bool_or_blank_rationale_rejected(self):
        job = self.selected[0]
        for kind in ("missing", "extra", "index", "bool", "blank", "duplicate", "status"):
            value = fixture(job); row = value["criterion_assessments"][0]
            if kind == "missing": row.pop("rationale")
            if kind == "extra": value["score"] = 100
            if kind == "index": row["requirement_index"] = 99
            if kind == "bool": row["requirement_index"] = True
            if kind == "blank": row["rationale"] = "  "
            if kind == "duplicate": value["criterion_assessments"].append(deepcopy(row))
            if kind == "status": row["status"] = "approved"
            with self.subTest(kind=kind), self.assertRaises(ValueError): run.validate(value, job["packet"])

    def test_quote_must_be_current_assistant_not_user_or_initial(self):
        job = next(j for j in self.selected if j["row"]["stage"] == "update")
        for text in (job["packet"]["transcript"][0]["content"], job["packet"]["transcript"][1]["content"], "not in answer"):
            value = fixture(job); value["criterion_assessments"][0]["response_evidence"] = text
            with self.assertRaises(ValueError): run.validate(value, job["packet"])

    def test_stitched_quote_rejected(self):
        job = self.selected[0]; text = job["packet"]["transcript"][-1]["content"]
        value = fixture(job); value["criterion_assessments"][0]["response_evidence"] = text[:20]+" ... "+text[-20:]
        with self.assertRaises(ValueError): run.validate(value, job["packet"])

    def test_empty_quote_only_missed_or_unclear(self):
        job = self.selected[0]
        for status in run.STATUSES:
            value = fixture(job,status); value["criterion_assessments"][0]["response_evidence"] = ""
            if status in {"met","partial"}:
                with self.assertRaises(ValueError): run.validate(value, job["packet"])
            else: run.validate(value,job["packet"])

    def test_duplicate_json_keys_rejected(self):
        raw = {"model":run.MODEL,"status":"completed","steps":[{"type":"model_output","content":[
            {"type":"text","text":'{"criterion_assessments": [], "criterion_assessments": []}'}]}]}
        with self.assertRaises(ValueError): run.decode(raw,self.selected[0]["packet"])

    def test_one_use_lock_prevents_new_uuid_allowance(self):
        with tempfile.TemporaryDirectory() as temp:
            run.consume(Path(temp),"fixture-protocol","one")
            with self.assertRaises(FileExistsError): run.consume(Path(temp),"fixture-protocol","two")

    def test_wrong_or_missing_approval_blocks_before_credential_access(self):
        with patch.object(run,"audit",return_value={"protocol_sha256":"FROZEN"}), patch.object(run.old.prior,"read_setting") as read:
            for note, protocol in (("", "FROZEN"),("old one-call approval",None),("new scope","WRONG")):
                with self.assertRaises(ValueError): run.run_live(ROOT,"00000000-0000-4000-8000-000000000001",note,protocol)
            read.assert_not_called()


class AnalysisTests(unittest.TestCase):
    def setUp(self): self.selected = run.jobs(ROOT); self.values = judgments(self.selected)

    def test_simulation_has_expected_denominators_not_clinical_accuracy(self):
        result = run.analyze(ROOT,self.selected,self.values,"offline_fixture")
        self.assertTrue(result["author_boundary_gate"]); self.assertTrue(result["simulation_only"])
        self.assertEqual((result["first_author_hypothesis_matches"],result["exact_status_repeats"],result["exploratory_first_observed"]),(16,28,12))
        self.assertEqual(len(result["contrasts"]),44); self.assertEqual(len(result["language_pairs"]),28)
        self.assertIsNone(result["clinical_accuracy"]); self.assertFalse(result["numeric_scores"])

    def test_exploratory_labels_do_not_enter_agreement(self):
        base = run.analyze(ROOT,self.selected,self.values,"offline_fixture")
        held = {r["packet_key"] for r in base["cells"] if r["author_hypothesis"] is None}
        for job in self.selected:
            if job["row"]["packet_key"] in held: self.values[job["row"]["sequence"]] = fixture(job,"missed")
        result = run.analyze(ROOT,self.selected,self.values,"offline_fixture")
        self.assertEqual(result["first_author_hypothesis_matches"],16)
        self.assertTrue(result["author_boundary_gate"])

    def test_missing_cells_never_shrink_expected_denominators(self):
        result = run.analyze(ROOT,self.selected,{1:self.values[1]},"offline_fixture")
        self.assertEqual(result["expected_judgments"],56); self.assertEqual(result["repeat_pairs_expected"],28)
        self.assertEqual(result["first_author_hypothesis_expected"],16); self.assertFalse(result["author_boundary_gate"])

    def test_repeat_disagreement_is_retained_not_averaged(self):
        job = self.selected[28]; original = self.values[29]["criterion_assessments"][0]["status"]
        self.values[29] = fixture(job,"missed" if original != "missed" else "met")
        result = run.analyze(ROOT,self.selected,self.values,"offline_fixture")
        self.assertEqual(result["exact_status_repeats"],27); self.assertFalse(result["author_boundary_gate"])
        self.assertEqual(len([r for r in result["repeats"] if not r["match"]]),1)

    def test_hypothesis_disagreement_blocks_gate_but_is_valid_data(self):
        value = run.analyze(ROOT,self.selected,self.values,"offline_fixture")
        cell = next(c for c in value["cells"] if c["phase"]=="first" and c["author_hypothesis"] is not None)
        self.values[cell["sequence"]] = fixture(self.selected[cell["sequence"]-1],"unclear")
        result = run.analyze(ROOT,self.selected,self.values,"offline_fixture")
        self.assertEqual(result["valid_judgments"],56); self.assertFalse(result["author_boundary_gate"])


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name); self.selected = run.jobs(ROOT); self.values = judgments(self.selected); self.calls = 0

    def execute(self, change=None, **kwargs):
        def connect(host,timeout):
            self.calls += 1; result = deepcopy(self.values[self.calls])
            raw = {"model":run.MODEL,"status":"completed","usage":usage_fixture("gemini"),
                   "steps":[{"type":"model_output","content":[{"type":"text","text":json.dumps(result)}]}]}
            return Connection(change(self.calls,raw,result) if change else Response(json.dumps(raw).encode()))
        return run.execute(ROOT,self.path,"FIXTURE","S50-FAKE-KEY",connect,"offline_fixture",**kwargs)

    def replay(self,**kwargs): return run.replay(ROOT,self.path,"FIXTURE",**kwargs)

    def test_full_fixture_run_replays_without_prose_or_secret(self):
        result = self.execute()
        self.assertEqual((self.calls,result["attempts"]),(56,56)); self.assertEqual(result,self.replay())
        self.assertEqual(result["terminal"],"schedule_complete"); self.assertTrue(result["analysis"]["author_boundary_gate"])
        self.assertNotIn("S50-FAKE-KEY",json.dumps(result)); self.assertNotIn("response_evidence",json.dumps(result))

    def test_valid_disagreement_does_not_trigger_retry_or_stop(self):
        def change(i,raw,value):
            if i==1:
                value["criterion_assessments"][0]["status"] = "missed"
                raw["steps"][0]["content"][0]["text"] = json.dumps(value)
            return Response(json.dumps(raw).encode())
        result = self.execute(change)
        self.assertEqual(result["attempts"],56); self.assertTrue(result["analysis"]["complete"])

    def test_403_stops_without_retry_and_charge_is_unknown(self):
        result = self.execute(lambda *a: Response(b"Forbidden",403))
        self.assertEqual(self.calls,1); self.assertEqual(result["terminal"],"unknown_charge")
        self.assertEqual(result["accounting"]["unknown_charge_attempts"],1)
        self.assertFalse(result["analysis"]["complete"])

    def test_incomplete_response_stops_but_keeps_usage(self):
        def change(i,raw,value):
            raw["status"] = "incomplete"; return Response(json.dumps(raw).encode())
        result = self.execute(change)
        self.assertEqual(result["terminal"],"response_validation"); self.assertEqual(self.calls,1)
        self.assertGreater(float(result["monitoring_known_subtotal_usd"]),0)

    def test_missing_usage_stops(self):
        def change(i,raw,value):
            raw.pop("usage"); return Response(json.dumps(raw).encode())
        self.assertEqual(self.execute(change)["terminal"],"unknown_charge"); self.assertEqual(self.calls,1)

    def test_wrong_model_and_invalid_quote_rejected(self):
        for kind in ("model","quote"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                self.path=Path(temp); self.calls=0
                def change(i,raw,value):
                    if kind=="model": raw["model"]="other"
                    else:
                        value["criterion_assessments"][0]["response_evidence"]="NOT PRESENT"
                        raw["steps"][0]["content"][0]["text"]=json.dumps(value)
                    return Response(json.dumps(raw).encode())
                result=self.execute(change)
                self.assertEqual(result["analysis"]["valid_judgments"],0); self.assertEqual(self.calls,1)

    def test_threshold_stops_with_possible_final_call_overrun(self):
        result=self.execute(threshold=1)
        self.assertEqual(result["attempts"],1); self.assertEqual(result["terminal"],"spend_threshold_reached")
        self.assertEqual(result,self.replay(threshold=1)); self.assertFalse(result["hard_ceiling"])

    def test_same_directory_cannot_resume(self):
        self.execute(threshold=1)
        with self.assertRaises(FileExistsError): self.execute()
        self.assertEqual(self.calls,1)

    def test_replay_rejects_dispatch_after_stop(self):
        self.execute()
        with self.assertRaisesRegex(ValueError,"Dispatch after stop"): self.replay(threshold=1)

    def test_tampered_payload_raw_acceptance_and_account_rejected(self):
        self.execute(threshold=1)
        for suffix in ("payload.json","raw.bin","accepted.json","accounting.json"):
            path=self.path/"capture"/("0001."+suffix); original=path.read_bytes()
            if suffix in {"payload.json","raw.bin"}: path.write_bytes(original+b" ")
            else:
                value=json.loads(original)
                if suffix=="accepted.json": value["raw_sha256"]="changed"
                else: value["undiscounted_token_estimate_microusd"]+=1
                path.write_text(json.dumps(value))
            with self.subTest(suffix=suffix), self.assertRaises(ValueError): self.replay(threshold=1)
            path.write_bytes(original)

    def test_orphan_capture_rejected(self):
        self.execute(threshold=1); (self.path/"capture"/"0002.raw.bin").write_bytes(b"orphan")
        with self.assertRaises(ValueError): self.replay(threshold=1)

    def test_reserved_without_payload_is_unknown(self):
        original=run.guard._write_exclusive
        def fail(path,value):
            if path.name.endswith(".payload.json"): raise OSError("fixture")
            original(path,value)
        with patch.object(run.guard,"_write_exclusive",side_effect=fail):
            with self.assertRaises(OSError): self.execute()
        result=self.replay(); self.assertEqual(result["terminal"],"interrupted_unknown_delivery_or_charge")
        self.assertEqual(result["accounting"]["unknown_charge_attempts"],1); self.assertEqual(self.calls,0)

    def test_report_failure_retains_captures(self):
        original=run.write_json
        def fail(path,value):
            if path.name=="report.json": raise OSError("fixture")
            original(path,value)
        with patch.object(run,"write_json",side_effect=fail):
            with self.assertRaises(OSError): self.execute(threshold=1)
        self.assertEqual(self.replay(threshold=1)["analysis"]["valid_judgments"],1)


if __name__ == "__main__": unittest.main()
