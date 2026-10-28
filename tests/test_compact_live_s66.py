"""All transport is fake, including explicitly mocked live-path tests."""

from copy import deepcopy
from contextlib import contextmanager, ExitStack
from datetime import timedelta
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts import compact_live_s66 as run

ROOT = Path(__file__).resolve().parents[1]


def portable_items():
    rows = run.previous.public_controls(ROOT)[2]
    for event, row in zip((223, 232, 278), list(rows)):
        rows.append({**deepcopy(row), "id": f"historical-source-{event}", "kind": "source_probe", "expected_error": None})
    return rows


def approval(frozen):
    at = run.stamp(frozen["plan"]["pricing_verified_at"]) + timedelta(minutes=1)
    return {"approval_id": str(uuid4()), "run_id": str(uuid4()),
        "protocol_sha256": run.pilot.sha256_json(frozen), "approved_at": at.isoformat().replace("+00:00", "Z"),
        "expires_at": (at + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "approved_by": "UNIT TEST ONLY", "authorization_evidence": "FABRICATED FIXTURE; NOT HUMAN CONSENT",
        "accept_paid_calls": True, "accept_provider_disclosure": True, "accept_threshold_overrun": True,
        "accept_no_retries_or_resume": True, "accept_failure_gates": True, "accept_provisional_reporting": True}


def alter(core, update):
    fixture = run.fixture_for(core)
    raw = run.capture.strict_json(fixture.body)
    update(raw)
    return run.old.previous.Fixture(run.guard._json_bytes(raw))


def judge_edit(raw, update):
    item = raw["steps"][0]["content"][0]
    value = json.loads(item["text"])
    update(value)
    item["text"] = json.dumps(value, ensure_ascii=False)


class CompactLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.complete_path = Path(cls.temp.name).resolve() / "complete"
        with patch.object(run, "read_setting", side_effect=AssertionError("No key")), \
             patch.object(run, "tls", side_effect=AssertionError("No real network")), \
             patch("socket.socket.connect", side_effect=AssertionError("No network")):
            cls.complete = run.Session(ROOT, cls.complete_path, mode="offline_fixture", fixture_items=portable_items())
            while cls.complete.step(run.fixture_for(cls.complete.core)) is not None: pass
            cls.replayed = run.replay(ROOT, cls.complete_path)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name).resolve() / "run"

    def new(self):
        return run.Session(ROOT, self.directory, mode="offline_fixture", fixture_items=portable_items())

    def advance(self, writer, until=16):
        while writer.core.index < until and writer.step(run.fixture_for(writer.core)) is not None: pass
        return writer

    @contextmanager
    def mocked_live(self):
        """Exercise real admission/capture, substituting only source loading and TLS."""
        frozen = run.snapshot(ROOT); auth = approval(frozen)
        path = ROOT / "work/s66-runs" / auth["run_id"]
        receipt = ROOT / "work/s66-consumed-approvals" / (auth["approval_id"] + ".json")
        self.assertFalse(path.exists()); self.assertFalse(receipt.exists())
        rows = portable_items(); spec, catalog, _ = run.previous.public_controls(ROOT)
        original = run.check_items
        def source_check(root, items, kind, freeze):
            # Actual source hashes are tested separately. First control requests
            # here still have to match the real frozen provider payload hashes.
            return original(root, items, "portable_fixture_substitutes", freeze)
        def key(*args, **kwargs):
            self.assertEqual(run.read(receipt), run.receipt_value(auth, auth["protocol_sha256"]))
            self.assertTrue((path / f"events/{writer.event:04d}/reservation.json").is_file())
            self.assertEqual(args[1], "GEMINI_API_KEY")
            return "S66-UNIT-TEST-KEY-NEVER-REAL"
        def fake_tls(host, *, timeout):
            self.assertEqual((host, timeout), (run.capture.ENDPOINTS["gemini"][0], 900))
            fixture = run.old.previous.Fixture(run.guard._json_bytes(run.previous.next_fixture(writer.core)))
            return run.old.previous.fake._Connection(fixture)
        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(run.previous, "source_inputs", return_value=(spec, catalog, rows)))
                stack.enter_context(patch.object(run, "check_items", side_effect=source_check))
                clock = stack.enter_context(patch.object(run, "datetime", wraps=run.datetime))
                clock.now.return_value = run.stamp(auth["approved_at"])
                keys = stack.enter_context(patch.object(run, "read_setting", side_effect=key))
                network = stack.enter_context(patch.object(run, "tls", side_effect=fake_tls))
                stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("No real network")))
                writer = run.Session(ROOT, path, mode="live", source_directory=self.directory,
                                     freeze=frozen, approval=auth)
                yield writer, auth, clock, keys, network
        finally:
            # Only these freshly generated, asserted-absent unit-test UUIDs.
            if path.exists(): shutil.rmtree(path)
            if receipt.exists(): receipt.unlink()

    def test_mocked_live_admission_capture_and_read_only_replay(self):
        with self.mocked_live() as (writer, auth, clock, keys, network):
            keys.assert_not_called(); network.assert_not_called()
            writer.step(); writer.step()
            self.assertEqual((keys.call_count, network.call_count), (2, 2))
            clock.now.return_value = run.stamp(auth["expires_at"]) + timedelta(days=1)
            r = run.replay(ROOT, writer.directory)
            self.assertEqual((r["report"]["settled_attempts"], r["report"]["live_calls"]), (2, 2))
            self.assertFalse(r["report"]["simulation_only"])
            self.assertFalse(r["report"]["technical_gate"]["pass"])
            for path in writer.directory.rglob("*"):
                if path.is_file(): self.assertNotIn(b"S66-UNIT-TEST-KEY-NEVER-REAL", path.read_bytes())

    def test_live_expiry_stops_before_second_reservation_or_key(self):
        with self.mocked_live() as (writer, auth, clock, keys, network):
            writer.step()
            clock.now.return_value = run.stamp(auth["expires_at"])
            with self.assertRaises(ValueError): writer.step()
            with self.assertRaises(ValueError): writer.step()
            self.assertEqual((writer.event, keys.call_count, network.call_count), (1, 1, 1))
            self.assertEqual(run.replay(ROOT, writer.directory)["events"], 1)

    def test_consumed_live_permission_cannot_authorize_new_run(self):
        with self.mocked_live() as (writer, auth, clock, keys, network):
            changed = {**auth, "run_id": str(uuid4())}
            path = ROOT / "work/s66-runs" / changed["run_id"]
            with self.assertRaises(FileExistsError):
                run.Session(ROOT, path, mode="live", source_directory=self.directory,
                            freeze=writer.freeze, approval=changed)
            self.assertFalse(path.exists()); keys.assert_not_called(); network.assert_not_called()

    def test_live_replay_rejects_dispatch_outside_approval_window(self):
        with self.mocked_live() as (writer, auth, clock, keys, network):
            writer.step()
            path = writer.directory / "events/0001/reservation.json"
            value = run.read(path); value["reserved_at"] = auth["expires_at"]
            path.write_bytes(run.guard._json_bytes(value))
            with self.assertRaises(ValueError): run.replay(ROOT, writer.directory)

    def test_input_serialization_order_is_bound_not_just_object_equality(self):
        writer = self.new(); writer.step(run.fixture_for(writer.core))
        path = writer.directory / "inputs.json"
        original = run.read(path)
        sorted_text = json.dumps(json.loads(original), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(json.loads(original), json.loads(sorted_text))
        self.assertNotEqual(original, sorted_text)
        path.write_bytes(run.guard._json_bytes(sorted_text))
        with self.assertRaises(ValueError): run.replay(ROOT, self.directory)
        with self.assertRaises(ValueError): writer.step(run.fixture_for(writer.core))

    def test_complete_16_capture_and_independent_replay(self):
        r = self.replayed
        self.assertEqual(r["events"], 16)
        self.assertTrue(r["report_verified"])
        self.assertIsNone(r["incomplete_tail"])
        self.assertEqual(r["report"], run.report(self.complete.core, "offline_fixture"))
        self.assertTrue(r["report"]["technical_gate"]["pass"])
        self.assertFalse(r["report"]["overall_feasibility_passed"])
        self.assertEqual(r["report"]["live_calls"], 0)
        self.assertEqual(r["report"]["measured_model_scores"], 0)

    def test_public_report_no_answer_judge_text_approval_or_scores(self):
        value = json.dumps(self.replayed)
        for forbidden in ("response_evidence", "rationale", "reasoning_content", "authorization_evidence", "point_score"):
            self.assertNotIn(forbidden, value)
        self.assertFalse(self.replayed["report"]["clinical_validation"])
        self.assertFalse(self.replayed["report"]["broader_run_authorized"])

    def test_snapshot_freezes_parent_source_request_hashes_and_adapter(self):
        frozen = run.snapshot(ROOT)
        self.assertEqual(frozen, run.read(ROOT / run.FREEZE))
        self.assertEqual(len(frozen["selected_packet_sha256"]), 6)
        self.assertEqual(len(frozen["judge_payload_sha256"]), 12)
        self.assertEqual(frozen["s65"], run.previous.snapshot(ROOT))
        self.assertIn("tests/test_compact_live_s66.py", frozen["files"])

    def test_fresh_approval_validates_without_key_or_network(self):
        frozen = run.snapshot(ROOT); auth = approval(frozen)
        with patch.object(run, "read_setting", side_effect=AssertionError), patch.object(run, "tls", side_effect=AssertionError):
            value = run.validate_authorization(ROOT, frozen, auth, now=run.stamp(auth["approved_at"]))
        self.assertEqual(value["maximum_attempts"], 16)
        self.assertEqual(value["stop_threshold_usd"], "3.00")
        self.assertFalse(value["hard_ceiling"])

    def test_old_missing_malformed_and_partial_approvals_fail(self):
        frozen = run.snapshot(ROOT); auth = approval(frozen); now = run.stamp(auth["approved_at"])
        bads = (None, {}, {**auth, "protocol_sha256": "s62"}, {**auth, "accept_paid_calls": False},
                {**auth, "accept_provider_disclosure": 1}, {**auth, "accept_no_retries_or_resume": False},
                {**auth, "approval_id": "../old"}, {**auth, "authorization_evidence": ""}, {**auth, "extra": True})
        for bad in bads:
            with self.assertRaises((ValueError, TypeError)): run.validate_authorization(ROOT, frozen, bad, now=now)

    def test_approval_expiry_future_and_stale_prices_fail(self):
        frozen = run.snapshot(ROOT); auth = approval(frozen); at = run.stamp(auth["approved_at"])
        for now in (at-timedelta(seconds=1), at+timedelta(hours=1), at+timedelta(hours=25)):
            with self.assertRaises(ValueError): run.validate_authorization(ROOT, frozen, auth, now=now)
        bad = {**auth, "expires_at": (at+timedelta(hours=25)).isoformat().replace("+00:00", "Z")}
        with self.assertRaises(ValueError): run.validate_authorization(ROOT, frozen, bad, now=at)

    def test_changed_freeze_fails(self):
        frozen = run.snapshot(ROOT); auth = approval(frozen)
        frozen["plan"]["stop_threshold_usd"] = "4.00"
        with self.assertRaises(ValueError): run.validate_authorization(ROOT, frozen, auth, now=run.stamp(auth["approved_at"]))

    def test_exclusive_receipt_consumed_only_once(self):
        frozen = run.snapshot(ROOT); auth = approval(frozen)
        parent = Path(self.folder.name).resolve()
        with patch.object(run, "_private_path", return_value=parent), patch.object(run.subprocess, "run") as ignored:
            ignored.return_value.returncode = 0
            run.consume_approval(ROOT, auth, auth["protocol_sha256"])
            with self.assertRaises(FileExistsError): run.consume_approval(ROOT, auth, auth["protocol_sha256"])

    def test_no_live_source_substitution_or_missing_approval(self):
        with patch.object(run, "read_setting", side_effect=AssertionError), patch.object(run, "tls", side_effect=AssertionError):
            with self.assertRaises(ValueError):
                run.Session(ROOT, self.directory, mode="live", freeze=run.snapshot(ROOT), approval=None)
            with self.assertRaises(ValueError):
                run.Session(ROOT, self.directory, mode="live", fixture_items=portable_items())
        self.assertFalse(self.directory.exists())
        with self.assertRaises(ValueError): run.check_items(ROOT, portable_items(), "verified_s62_packets", run.snapshot(ROOT))

    def test_wrong_source_order_control_or_extra_metadata_rejected(self):
        for change in (lambda x:x.reverse(), lambda x:x[0].update(expected_error="invented"),
                       lambda x:x[3].update(extra="unapproved")):
            rows = portable_items(); change(rows)
            with self.assertRaises(ValueError): run.check_items(ROOT, rows, "portable_fixture_substitutes", run.snapshot(ROOT))

    def test_fixture_mode_has_no_paid_approval_or_external_factory(self):
        with self.assertRaises(ValueError):
            run.Session(ROOT, self.directory, mode="offline_fixture", fixture_items=portable_items(), approval={})
        writer = self.new()
        for arg in (None, {}, "key", lambda:None):
            with self.assertRaises(ValueError): writer.step(arg)
        self.assertEqual(writer.event, 0)

    def test_no_directory_reuse_or_resume(self):
        self.new()
        with self.assertRaises(FileExistsError): self.new()

    def test_reservation_and_attempt_saved_before_connection(self):
        writer = self.new(); original = run.old.previous.fake._Connection
        def check(fixture):
            event = self.directory / "events/0001"
            self.assertTrue((event/"reservation.json").exists())
            self.assertTrue((event/"transport/0001.attempt.json").exists())
            return original(fixture)
        with patch.object(run.old.previous.fake, "_Connection", side_effect=check):
            writer.step(run.fixture_for(writer.core))

    def test_known_cost_bad_reference_closes_judge_only_and_replays(self):
        writer = self.new()
        fixture = alter(writer.core, lambda r:judge_edit(r, lambda v:v["criterion_assessments"][0].update(response_evidence_ref={"first":"bad","last":"bad"})))
        writer.step(fixture)
        self.assertEqual(writer.core.closed, {"judge"})
        self.assertGreater(writer.core.monitored, 0)
        self.advance(writer); writer.step(run.fixture_for(writer.core))
        r = run.replay(ROOT, self.directory)["report"]
        self.assertEqual((r["settled_attempts"],r["skipped"],r["accepted_candidate_turns"]),(5,11,4))
        self.assertFalse(r["technical_gate"]["pass"])

    def test_known_cost_candidate_length_closes_one_model_only(self):
        writer = self.advance(self.new(),12)
        writer.step(alter(writer.core,lambda r:r["choices"][0].update(finish_reason="length")))
        self.assertEqual(writer.core.closed,{"MiniMax-M3.1-Flash"})
        self.advance(writer); writer.step(run.fixture_for(writer.core))
        r=run.replay(ROOT,self.directory)["report"]
        self.assertEqual((r["settled_attempts"],r["accepted_candidate_turns"],r["skipped"]),(15,2,1))

    def test_http_unknowns_stop_globally_without_retry(self):
        for status in (302,403,429,500):
            writer=run.Session(ROOT,Path(self.folder.name).resolve()/str(status),mode="offline_fixture",fixture_items=portable_items())
            writer.step(run.old.previous.Fixture(b"{}",status=status))
            self.assertIsNone(writer.step(run.old.previous.Fixture()))
            r=run.replay(ROOT,writer.directory)["report"]
            self.assertEqual(r["unknown_cost_attempts"],1)
            self.assertEqual(r["terminal"],"unknown_delivery_or_cost")

    def test_unknown_usage_model_and_input_scope_fail(self):
        for name, update in (("usage",lambda r:r.pop("usage")),("model",lambda r:r.update(model="other")),
                             ("input",lambda r:r["usage"].update(total_input_tokens=16001,total_tokens=16401))):
            writer=run.Session(ROOT,Path(self.folder.name).resolve()/name,mode="offline_fixture",fixture_items=portable_items())
            writer.step(alter(writer.core,update))
            r=run.replay(ROOT,writer.directory)["report"]
            self.assertEqual(r["unknown_cost_attempts"],1)
            self.assertFalse(r["technical_gate"]["pass"])

    def test_connection_timeout_no_body_is_auditable_unknown(self):
        writer=self.new(); writer.step(run.old.previous.Fixture(fault="connect_timeout"))
        r=run.replay(ROOT,self.directory)
        self.assertTrue(r["report_verified"])
        self.assertEqual(r["report"]["unknown_cost_attempts"],1)

    def test_accounting_is_recorded_before_invalid_answer(self):
        writer=self.new()
        writer.step(alter(writer.core,lambda r:r["steps"][0]["content"][0].update(text="{}")))
        account=run.read(self.directory/"events/0001/transport/0001.accounting.json")
        self.assertEqual(account["status"],"token_estimate_only")
        self.assertGreater(account["undiscounted_token_estimate_microusd"],0)

    def test_threshold_can_overrun_and_never_claims_hard_ceiling(self):
        core=deepcopy(self.complete.core)
        core.index=0; core.stop=None; core.pending=None; core.accounts=[]; core.judgments={}; core.answers={}; core.contexts={}; core.outcomes={}
        core.monitored=3*run.previous.TICKS_PER_USD-1
        core.prepare(); raw=run.previous.next_fixture(core)
        context=core.contexts[core.pending["id"]]
        account=run.capture.account(raw,core.model_specs["gemini",context["model"]],context["payload"])
        core.consume({"accepted":True,"category":"accepted","result":core.decode(raw),"accounting":account},run.guard._json_bytes(raw))
        self.assertGreater(core.monitored,3*run.previous.TICKS_PER_USD)
        self.assertEqual(core.stop,"spend_threshold_reached")
        self.assertIsNone(core.prepare())

    def test_repeat_payload_and_actual_initial_history_binding(self):
        core=self.complete.core
        for key in core.items:
            self.assertEqual(core.contexts["first__"+key]["payload"],core.contexts["repeat__"+key]["payload"])
        for model in ("MiniMax-M3.1-Flash","MiniMax-M3"):
            p=core.contexts[model+"__update"]["payload"]
            self.assertEqual(p["messages"][2]["content"],core.answers[model+"__initial"]["text"])
            self.assertNotIn("FIXTURE_REASONING",json.dumps(p))
            self.assertNotIn("criterion_anchors",json.dumps(p))
            self.assertEqual(p["max_completion_tokens"],32768)
            self.assertNotIn("max_tokens",p)

    def test_semantic_disagreement_retained_without_relabeling(self):
        core=deepcopy(self.complete.core)
        key=core.rows[6]["id"]
        core.judgments[key]["criterion_assessments"][0]["status"]="partial"
        r=run.report(core,"live")
        self.assertEqual(r["matching_repeat_vectors"],5)
        self.assertFalse(r["technical_gate"]["pass"])
        self.assertEqual(r["measured_model_scores"],0)
        self.assertEqual(r["live_calls"],16)

    def test_write_failure_poisoned_but_captured_reply_reconstructed(self):
        writer=self.new(); original=run.write
        def fail(path,value):
            if path.name=="result.json":raise OSError("Fixture disk failure")
            return original(path,value)
        with patch.object(run,"write",side_effect=fail),self.assertRaises(OSError):writer.step(run.fixture_for(writer.core))
        with self.assertRaises(ValueError):writer.step(run.old.previous.Fixture())
        r=run.replay(ROOT,self.directory)
        self.assertEqual(r["incomplete_tail"],"captured_reply_reconstructed_without_result")
        self.assertEqual(r["report"]["settled_attempts"],1)
        self.assertFalse((self.directory/"events/0001/result.json").exists())

    def test_interrupted_reservation_remains_unknown_not_unreached(self):
        writer=self.new(); original=run.write
        def fail(path,value):
            if path.name=="payload.json":raise OSError("Fixture disk failure")
            return original(path,value)
        with patch.object(run,"write",side_effect=fail),self.assertRaises(OSError):writer.step(run.fixture_for(writer.core))
        r=run.replay(ROOT,self.directory)
        self.assertEqual(r["report"]["unsettled_attempts"],1)
        self.assertEqual(r["report"]["unreached"],15)
        self.assertEqual(r["report"]["settled_attempts"],0)

    def test_raw_parsed_accounting_payload_or_inputs_tamper_rejected(self):
        writer=self.new(); writer.step(run.fixture_for(writer.core))
        for name in ("inputs.json","events/0001/payload.json","events/0001/result.json",
                     "events/0001/transport/0001.raw.bin","events/0001/transport/0001.accepted.json",
                     "events/0001/transport/0001.accounting.json"):
            path=self.directory/name; before=path.read_bytes()
            try:
                path.write_bytes(b"{}")
                with self.assertRaises((ValueError,KeyError,TypeError)):run.replay(ROOT,self.directory)
            finally:path.write_bytes(before)

    def test_orphan_event_and_event_after_stop_rejected(self):
        writer=self.new(); writer.step(run.old.previous.Fixture(b"{}",status=403))
        (self.directory/"events/0002").mkdir()
        with self.assertRaises(ValueError):run.replay(ROOT,self.directory)

    def test_input_drift_poisoned_before_request(self):
        writer=self.new(); writer.input_pins[run.PLAN]="changed"
        with self.assertRaises(ValueError):writer.step(run.fixture_for(writer.core))
        self.assertEqual(writer.event,0)
        with self.assertRaises(ValueError):writer.step(run.old.previous.Fixture())

    def test_public_or_linked_journals_refused(self):
        with self.assertRaises(ValueError):run.Session(ROOT,ROOT/"data/not-a-run",mode="offline_fixture",fixture_items=portable_items())
        link=Path(self.folder.name)/"link"; link.symlink_to(self.complete_path,target_is_directory=True)
        with self.assertRaises(ValueError):run.replay(ROOT,link)

    def test_no_fixture_credential_saved(self):
        writer=self.new();writer.step(run.fixture_for(writer.core))
        for path in self.directory.rglob("*"):
            if path.is_file():self.assertNotIn(b"S66-FIXTURE-ONLY",path.read_bytes())

    def test_fixture_preview_has_no_state_effect(self):
        writer=self.new(); before=deepcopy(writer.core.__dict__)
        run.fixture_for(writer.core)
        self.assertEqual(before,writer.core.__dict__)


if __name__=="__main__":unittest.main()
