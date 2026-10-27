"""Prospective live admission and simulated exchanges; never actual provider calls."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts import standalone_live_s62 as run
from tests.test_standalone_rehearsal_s61 import altered, judge_edit

ROOT = Path(__file__).resolve().parents[1]


def advance(writer, until):
    while writer.core.index < until and writer.step(run.previous.next_fixture(writer.core)) is not None:
        pass
    return writer


def approval(freeze):
    at = run.stamp(freeze["plan"]["pricing_verification"]["verified_at"]) + timedelta(minutes=1)
    return {"approval_id": str(uuid4()), "run_id": str(uuid4()),
        "protocol_sha256": run.pilot.sha256_json(freeze), "approved_at": at.isoformat().replace("+00:00", "Z"),
        "expires_at": (at + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "approved_by": "UNIT TEST ONLY", "authorization_evidence": "FABRICATED TEST RECORD; NO USER AUTHORIZATION",
        "accept_paid_calls": True, "accept_provider_disclosure": True, "accept_threshold_overrun": True,
        "accept_control_and_failure_gates": True, "accept_provisional_reporting": True}


class StandaloneLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.complete_path = Path(cls.temp.name).resolve() / "complete"
        with patch.object(run, "read_setting", side_effect=AssertionError("No key")), \
             patch.object(run, "tls", side_effect=AssertionError("No network")), \
             patch("socket.socket.connect", side_effect=AssertionError("No network")):
            cls.complete = run.Session(ROOT, cls.complete_path, mode="offline_fixture")
            while cls.complete.step(run.previous.next_fixture(cls.complete.core)) is not None:
                pass
            cls.replayed = run.replay(ROOT, cls.complete_path)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name).resolve() / "run"

    def new(self):
        return run.Session(ROOT, self.directory, mode="offline_fixture")

    def core_at(self, position):
        core = run.Core(ROOT, "20.00")
        source = self.complete.core
        core.index = position
        ids = {r["id"] for r in core.rows[:position]}
        for name in ("answers", "judgments", "outcomes", "contexts", "first_payloads"):
            setattr(core, name, {k: deepcopy(v) for k, v in getattr(source, name).items() if k in ids})
        return core

    def feed(self, core, fixture=None):
        fixture = fixture or run.previous.next_fixture(core)
        core.prepare()
        raw = run.capture.strict_json(fixture.body)
        context = core.contexts[core.pending["id"]]
        account = run.capture.account(raw, core.model_specs[context["provider"], context["model"]], context["payload"])
        try:
            parsed = core.decode(raw)
            result = {"accepted": True, "category": "accepted", "result": parsed, "accounting": account}
        except ValueError:
            result = {"accepted": False, "category": "response_validation", "result": None, "accounting": account}
        return core.consume(result, fixture.body)

    def test_complete_480_and_read_only_replay(self):
        self.assertEqual(self.replayed["events"], 480)
        self.assertTrue(self.replayed["report_verified"])
        self.assertEqual(self.replayed["report"], run.report(self.complete.core, "offline_fixture"))
        value = self.replayed["report"]
        self.assertEqual(value["outcomes"], {"accepted": 480})
        self.assertEqual(value["repeat_summary"]["complete_pairs"], 64)
        self.assertTrue(value["prospective_control_gate"]["pass"])
        self.assertEqual(value["terminal"], "schedule_complete")

    def test_fixture_and_live_report_labels_do_not_mix(self):
        fixture = self.replayed["report"]
        self.assertEqual(fixture["live_calls"], 0)
        self.assertEqual(fixture["measured_model_scores"], 0)
        live = run.report(self.complete.core, "live")  # Pure presentation test, no live execution.
        self.assertFalse(live["simulation_only"])
        self.assertFalse(live["numeric_fixture_scores_only"])
        self.assertEqual(live["live_calls"], 480)
        self.assertEqual(live["measured_model_scores"], 128)
        self.assertNotIn("simulated_monitoring_usd", live)
        self.assertTrue(all(c["clinical_comparison_held"] for c in live["conversations"]))
        self.assertFalse(live["reporting"]["model_rankings"])

    def test_proposal_is_unapproved_and_estimates_are_explicit_assumptions(self):
        value = run.proposal(ROOT)
        self.assertEqual(value["maximum_attempts"], 480)
        self.assertFalse(value["live_authorized"])
        self.assertFalse(value["hard_ceiling"])
        self.assertFalse(value["completion_within_budget_guaranteed"])
        self.assertEqual(value["cost_scenarios_not_predictions"][0]["estimated_usd"], "7.6544")
        self.assertEqual(value["cost_scenarios_not_predictions"][1]["estimated_usd"], "15.3088")

    def test_fresh_exact_approval_passes_without_key_or_connection(self):
        freeze = run.snapshot(ROOT)
        auth = approval(freeze)
        with patch.object(run, "read_setting", side_effect=AssertionError), patch.object(run, "tls", side_effect=AssertionError):
            value = run.validate_authorization(ROOT, freeze, auth, now=run.stamp(auth["approved_at"]))
        self.assertEqual(value["protocol_sha256"], auth["protocol_sha256"])

    def test_missing_old_or_incomplete_authorization_rejected(self):
        freeze = run.snapshot(ROOT)
        auth = approval(freeze)
        now = run.stamp(auth["approved_at"])
        for bad in (None, {}, {**auth, "accept_paid_calls": False}, {**auth, "accept_paid_calls": 1},
                    {**auth, "protocol_sha256": "old-protocol"}, {**auth, "approval_id": "old"},
                    {**auth, "unexpected": True}, {**auth, "authorization_evidence": ""}):
            with self.subTest(bad=bad), self.assertRaises((ValueError, TypeError)):
                run.validate_authorization(ROOT, freeze, bad, now=now)

    def test_expiry_future_and_stale_prices_rejected(self):
        freeze = run.snapshot(ROOT)
        auth = approval(freeze)
        at = run.stamp(auth["approved_at"])
        for now in (at - timedelta(seconds=1), at + timedelta(hours=1), at + timedelta(hours=25)):
            with self.subTest(now=now), self.assertRaises(ValueError):
                run.validate_authorization(ROOT, freeze, auth, now=now)
        for key, time in (("approved_at", at - timedelta(hours=1)), ("expires_at", at + timedelta(hours=25))):
            bad = {**auth, key: time.isoformat().replace("+00:00", "Z")}
            with self.assertRaises(ValueError):
                run.validate_authorization(ROOT, freeze, bad, now=at)

    def test_changed_freeze_rejected(self):
        freeze = run.snapshot(ROOT)
        auth = approval(freeze)
        freeze["plan"]["stop_threshold_usd"] = "21.00"
        with self.assertRaises(ValueError):
            run.validate_authorization(ROOT, freeze, auth, now=run.stamp(auth["approved_at"]))

    def test_approval_consumption_is_exclusive(self):
        freeze = run.snapshot(ROOT)
        auth = approval(freeze)
        parent = Path(self.folder.name).resolve()
        with patch.object(run, "_private_path", return_value=parent), \
             patch.object(run.subprocess, "run") as ignored:
            ignored.return_value.returncode = 0
            run.consume_approval(ROOT, auth, auth["protocol_sha256"])
            with self.assertRaises(FileExistsError):
                run.consume_approval(ROOT, auth, auth["protocol_sha256"])
        receipt = run.read(parent / (auth["approval_id"] + ".json"))
        self.assertTrue(receipt["consumed_before_credentials_or_network"])

    def test_live_refuses_missing_approval_before_key_network_or_directory(self):
        with patch.object(run, "read_setting", side_effect=AssertionError), patch.object(run, "tls", side_effect=AssertionError):
            with self.assertRaises(ValueError):
                run.Session(ROOT, self.directory, mode="live", freeze=run.snapshot(ROOT), approval=None)
        self.assertFalse(self.directory.exists())

    def test_fixture_mode_cannot_carry_paid_approval_or_external_factory(self):
        with self.assertRaises(ValueError):
            run.Session(ROOT, self.directory, mode="offline_fixture", approval={})
        writer = self.new()
        for value in (None, lambda: None, {}, "key"):
            with self.assertRaises(ValueError):
                writer.step(value)
        self.assertEqual(writer.event, 0)

    def test_no_existing_directory_reuse(self):
        self.new()
        with self.assertRaises(FileExistsError):
            self.new()

    def test_unsafe_miss_fails_gate_before_first_candidate(self):
        core = self.core_at(96)
        key = next(k for k in core.judgments if k.endswith("__unsafe"))
        core.judgments[key]["critical_errors"] = []
        self.assertIsNone(core.prepare())
        self.assertEqual(core.terminal, "prospective_control_gate_failed")
        self.assertFalse(core.gate()["checks"]["all_unsafe_hypotheses_detected"])
        self.assertEqual(core.index, 96)

    def test_safe_or_initial_critical_error_fails_gate(self):
        for profile in (None, "safe"):
            core = self.core_at(96)
            row = next(r for r in core.control_records if r["profile"] == profile)
            key = "control_first__" + row["key"]
            core.judgments[key]["critical_errors"] = [{"stage_id": row["stage"], "error_id": "fixture-error", "severity": "major"}]
            self.assertFalse(core.gate()["checks"]["safe_and_initial_without_errors"])
            self.assertIsNone(core.prepare())

    def test_repeat_boundary_one_disagreement_passes_two_fail(self):
        core = self.core_at(96)
        keys = [k for k in core.judgments if k.startswith("control_repeat")]
        core.judgments[keys[0]]["criterion_assessments"][0]["status"] = "not_met"
        self.assertTrue(core.gate()["pass"])
        core.judgments[keys[1]]["criterion_assessments"][0]["status"] = "not_met"
        self.assertFalse(core.gate()["pass"])
        self.assertIsNone(core.prepare())

    def test_partial_errors_visible_not_forced_to_safe(self):
        core = self.core_at(96)
        key = next(k for k in core.judgments if k.startswith("control_first") and k.endswith("__partial"))
        core.judgments[key]["critical_errors"] = [{"stage_id": "update", "error_id": "fixture-error", "severity": "major"}]
        # One repeat disagreement is permitted; omission errors are not relabelled.
        self.assertTrue(core.gate()["pass"])
        self.assertIn(key, core.control_readout()["non_unsafe_records_with_errors"])

    def test_no_numeric_order_or_forced_score_band_gate(self):
        self.assertFalse(run.GATE["numeric_order_required"])
        self.assertFalse(run.GATE["clinical_validation"])
        self.assertTrue(self.complete.core.gate()["pass"])
        self.assertFalse(self.replayed["report"]["reporting"]["score_band_fitting"])

    def test_controls_stop_on_first_known_cost_format_error(self):
        writer = self.new()
        fixture = altered(writer.core, lambda r: r["steps"][0]["content"][0].update(text="{}"))
        writer.step(fixture)
        self.assertEqual(writer.core.terminal, "invalid_judge_reply")
        self.assertEqual(writer.core.format_failures, 0)
        self.assertEqual(run.replay(ROOT, self.directory)["events"], 1)

    def test_development_format_limit_and_missing_first_repeat_dependency(self):
        core = self.core_at(224)
        failed = core.rows[224]
        for i in range(3):
            fixture = altered(core, lambda r: r["steps"][0]["content"][0].update(text="{}"))
            self.feed(core, fixture)
            self.assertEqual(core.format_failures, i + 1)
            self.assertEqual(core.terminal, None if i < 2 else "development_format_failure_limit")
        self.assertIsNone(core.prepare())
        partial = self.core_at(224)
        fixture = altered(partial, lambda r: r["steps"][0]["content"][0].update(text="{}"))
        self.feed(partial, fixture)
        while partial.index < 352:
            self.feed(partial)
        request = partial.prepare()
        repeat_id = failed["id"].replace("judge_first", "judge_repeat")
        self.assertEqual(partial.outcomes[repeat_id]["reason"], "accepted_dependency_missing")
        self.assertNotEqual(request["row"]["id"], repeat_id)

    def test_incomplete_judge_is_not_tolerated_as_format_failure(self):
        core = self.core_at(224)
        self.feed(core, altered(core, lambda r: r.update(status="incomplete")))
        self.assertEqual(core.terminal, "invalid_judge_reply")
        self.assertEqual(core.format_failures, 0)

    def test_known_cost_invalid_candidate_closes_only_model_lane(self):
        core = self.core_at(96)
        model = core.provider(core.rows[96])["model"]
        self.feed(core, altered(core, lambda r: r["steps"][0]["content"][0].update(text="")))
        self.assertIn(model, core.closed_candidates)
        self.assertIsNone(core.terminal)
        self.assertNotEqual(core.prepare()["context"]["model"], model)

    def test_transport_unknowns_stop_without_retry(self):
        for status in (302, 403, 429, 500):
            writer = run.Session(ROOT, Path(self.folder.name).resolve() / str(status), mode="offline_fixture")
            writer.step(run.previous.Fixture(b"{}", status=status))
            self.assertEqual(writer.core.terminal, "unknown_delivery_or_cost")
            self.assertIsNone(writer.step(run.previous.Fixture()))
            self.assertEqual(run.replay(ROOT, writer.directory)["report"]["unknown_cost_attempts"], 1)

    def test_unknown_usage_and_identity_stop(self):
        for field, value, terminal in (("usage", {}, "unknown_delivery_or_cost"),
                                       ("model", "wrong-model", "model_identity_failure")):
            writer = run.Session(ROOT, Path(self.folder.name).resolve() / field, mode="offline_fixture")
            writer.step(altered(writer.core, lambda r: r.update({field: value})))
            self.assertEqual(writer.core.terminal, terminal)
            self.assertEqual(run.replay(ROOT, writer.directory)["report"]["terminal"], terminal)

    def test_request_reservation_precedes_fake_connection(self):
        writer = self.new()
        original = run.previous.fake._Connection
        def check(fixture):
            event = self.directory / "events/0001"
            self.assertTrue((event / "reservation.json").exists())
            self.assertTrue((event / "transport/0001.attempt.json").exists())
            return original(fixture)
        with patch.object(run.previous.fake, "_Connection", side_effect=check):
            writer.step(run.previous.next_fixture(writer.core))

    def test_threshold_can_overrun_last_request_not_hard_cap(self):
        core = self.core_at(224)
        core.monitored = core.threshold - 1
        self.feed(core)
        self.assertGreater(core.monitored, core.threshold)
        self.assertEqual(core.terminal, "spend_threshold_reached")
        self.assertIsNone(core.prepare())

    def test_repeat_payloads_and_candidate_history_remain_s61_exact(self):
        for row in self.complete.core.rows:
            key = row["id"]
            self.assertEqual(self.complete.core.contexts[key]["payload"],
                             self.complete.core.context(row)["payload"])
            if row["kind"] == "candidate":
                raw = json.dumps(self.complete.core.contexts[key]["payload"])
                self.assertNotIn("FIXTURE_REASONING_NOT_FOR_HISTORY", raw)
                self.assertNotIn("criterion_anchors", raw)

    def test_write_failure_poisoned_and_capture_reconstructed_once(self):
        writer = self.new()
        original = run.write
        def fail(path, value):
            if path.name == "result.json":
                raise OSError("fixture disk failure")
            return original(path, value)
        with patch.object(run, "write", side_effect=fail), self.assertRaises(OSError):
            writer.step(run.previous.next_fixture(writer.core))
        with self.assertRaises(ValueError):
            writer.step(run.previous.Fixture())
        value = run.replay(ROOT, self.directory)
        self.assertEqual(value["incomplete_tail"], "captured_reply_reconstructed_without_result")
        self.assertEqual(value["report"]["settled_attempts"], 1)
        self.assertEqual(value["report"]["unresolved_reservations"], 0)
        self.assertFalse((self.directory / "events/0001/result.json").exists())

    def test_interrupted_reservation_stays_unresolved(self):
        writer = self.new()
        original = run.write
        def fail(path, value):
            if path.name == "payload.json":
                raise OSError("fixture disk failure")
            return original(path, value)
        with patch.object(run, "write", side_effect=fail), self.assertRaises(OSError):
            writer.step(run.previous.next_fixture(writer.core))
        value = run.replay(ROOT, self.directory)
        self.assertEqual(value["report"]["unresolved_reservations"], 1)
        self.assertEqual(value["report"]["settled_attempts"], 0)

    def test_tampered_raw_or_result_rejected(self):
        writer = self.new()
        writer.step(run.previous.next_fixture(writer.core))
        for name in ("transport/0001.raw.bin", "result.json", "payload.json"):
            path = self.directory / "events/0001" / name
            old = path.read_bytes()
            try:
                path.write_bytes(b"{}")
                with self.assertRaises((ValueError, KeyError)):
                    run.replay(ROOT, self.directory)
            finally:
                path.write_bytes(old)

    def test_input_drift_stops_and_poisons_before_reservation(self):
        writer = self.new()
        writer.input_pins[run.PLAN] = "changed"
        with self.assertRaises(ValueError):
            writer.step(run.previous.next_fixture(writer.core))
        self.assertEqual(writer.event, 0)
        with self.assertRaises(ValueError):
            writer.step(run.previous.Fixture())

    def test_no_credential_in_journal(self):
        writer = self.new()
        writer.step(run.previous.next_fixture(writer.core))
        for path in self.directory.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"S62-FIXTURE-ONLY", path.read_bytes())

    def test_public_or_symlink_journal_refused(self):
        with self.assertRaises(ValueError):
            run.Session(ROOT, ROOT / "data/not-a-run", mode="offline_fixture")
        link = Path(self.folder.name).resolve() / "link"
        link.symlink_to(self.complete_path, target_is_directory=True)
        with self.assertRaises(ValueError):
            run.replay(ROOT, link)

    def test_snapshot_binds_code_policy_prices_and_parent(self):
        value = run.snapshot(ROOT)
        self.assertEqual(value["s61"], run.previous.snapshot(ROOT))
        self.assertEqual(value["files"][run.PLAN], run.digest((ROOT / run.PLAN).read_bytes()))
        self.assertIn("tests/test_standalone_live_s62.py", value["files"])

    def test_live_path_is_mocked_consumes_once_before_key_and_cannot_resume(self):
        freeze = run.snapshot(ROOT)
        auth = approval(freeze)
        directory = ROOT / "work/s62-runs" / auth["run_id"]
        receipt = ROOT / "work/s62-consumed-approvals" / (auth["approval_id"] + ".json")
        # Cleanup only these newly generated test UUIDs, never an existing run.
        self.assertFalse(directory.exists())
        self.assertFalse(receipt.exists())
        self.addCleanup(lambda: shutil.rmtree(directory) if directory.exists() else None)
        self.addCleanup(lambda: receipt.unlink() if receipt.exists() else None)
        original = run.validate_authorization
        def validate(*args, **kw):
            kw.setdefault("now", run.stamp(auth["approved_at"]))
            return original(*args, **kw)
        def key(*args, **kw):
            self.assertTrue(receipt.exists())
            self.assertTrue((directory / "events/0001/reservation.json").exists())
            self.assertEqual(args[1], "GEMINI_API_KEY")
            return "S62-TEST-KEY-NEVER-REAL"
        with patch.object(run, "validate_authorization", side_effect=validate), \
             patch.object(run, "read_setting", side_effect=key) as keys, \
             patch.object(run, "tls") as connection, \
             patch("socket.socket.connect", side_effect=AssertionError("No real network")):
            session = run.Session(ROOT, directory, mode="live", freeze=freeze, approval=auth)
            connection.return_value = run.previous.fake._Connection(run.previous.next_fixture(session.core))
            session.step()
            self.assertEqual(keys.call_count, 1)
            self.assertEqual(connection.call_count, 1)
            value = run.replay(ROOT, directory)
            self.assertEqual(value["report"]["live_calls"], 1)
            self.assertFalse(value["report"]["simulation_only"])
            with self.assertRaises(ValueError):
                run.Session(ROOT, directory, mode="live", freeze=freeze, approval=auth)
            changed = {**auth, "run_id": str(uuid4())}
            with self.assertRaises(FileExistsError):
                run.Session(ROOT, ROOT / "work/s62-runs" / changed["run_id"], mode="live", freeze=freeze, approval=changed)
            with patch.object(run, "validate_authorization", side_effect=ValueError("expired")):
                with self.assertRaises(ValueError):
                    session.step()
            self.assertEqual(connection.call_count, 1)
            with self.assertRaises(ValueError):
                session.step()
        for path in directory.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"S62-TEST-KEY-NEVER-REAL", path.read_bytes())


if __name__ == "__main__":
    unittest.main()
