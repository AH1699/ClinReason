from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from benchmark import spending_s40 as spending
from benchmark.config import load_json
from tests.test_transport_s39 import Connection, Response
from tests.test_usage_s39 import usage_fixture
from tests.test_workflow_s38 import reply_fixture

ROOT = Path(__file__).resolve().parents[1]


def accounting(provider, value=0):
    result = {"prospective_cap_proven": False, "usage": None,
        "provider_billed_usd_ticks": None, "undiscounted_token_estimate_microusd": None}
    if provider == "grok":
        result.update(status="provider_reported_charge", provider_billed_usd_ticks=value)
    else:
        result.update(status="token_estimate_only", undiscounted_token_estimate_microusd=value)
    return result


class ThresholdTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)/"monitor"
        self.monitor = spending.StopThreshold(ROOT, self.directory)

    def begin(self):
        row = self.monitor.rows[self.monitor.attempts]
        return self.monitor.begin(row, {"model": row["model"], "input": "Synthetic fixture"})

    def settle(self, value=0, accepted=True):
        return self.monitor.settle(accounting(self.monitor.pending["row"]["provider"], value), accepted)

    def test_policy_is_first_phase_only_not_live_approval(self):
        policy = spending.policy(ROOT)
        self.assertEqual(policy["threshold_usd_ticks"], 550000000000)
        self.assertEqual(policy["live_call_allowance"], 0)
        self.assertFalse(policy["confirmation_policy_selected"])
        self.assertEqual(policy["owner_choice"], "Accept a stop threshold with possible overrun")

    def test_live_entry_cannot_be_enabled_by_policy_or_flag(self):
        with self.assertRaises(spending.guard.AdmissionBlocked):
            spending.run_live(approved=True, policy=spending.policy(ROOT))

    def test_confirmation_not_inferred_from_first_phase_choice(self):
        with self.assertRaises(spending.guard.AdmissionBlocked):
            spending.StopThreshold(ROOT, Path(self.temp.name)/"confirm", "confirmation")
        self.assertFalse((Path(self.temp.name)/"confirm").exists())

    def test_begin_then_settle_one_in_flight(self):
        self.begin()
        self.assertFalse(self.monitor.can_dispatch())
        with self.assertRaises(spending.guard.AdmissionBlocked): self.begin()
        self.assertEqual(self.monitor.attempts, 1)
        self.settle(1)
        self.assertTrue(self.monitor.can_dispatch())

    def test_admission_persisted_and_payload_hash_bound(self):
        record = self.begin()
        self.assertEqual(load_json(self.directory/"0001.admission.json"), record)
        self.assertEqual(spending.hashlib.sha256((self.directory/"0001.payload.json").read_bytes()).hexdigest(),
                         record["payload_sha256"])
        self.assertIsNone(record["prospective_cost_bound_ticks"])

    def test_exact_threshold_stops(self):
        self.begin(); settled = self.settle(55_000_000)
        self.assertEqual(settled["stop_reason"], "spend_threshold_reached")
        self.assertEqual(self.monitor.report()["monitoring_amount_usd"], "55")
        self.assertFalse(self.monitor.can_dispatch())
        with self.assertRaises(spending.guard.AdmissionBlocked): self.begin()

    def test_one_tick_below_threshold_still_allows_next_attempt(self):
        self.begin(); self.settle(54_999_999)
        self.begin(); self.settle(9999)
        self.assertEqual(self.monitor.monitored, 55*spending.TICKS_PER_USD-1)
        self.assertTrue(self.monitor.can_dispatch())
        self.begin()
        self.assertFalse(self.monitor.can_dispatch())

    def test_last_request_overrun_is_counted_not_clamped(self):
        self.begin(); self.settle(54_000_000)
        self.begin(); record = self.settle(3*spending.TICKS_PER_USD)
        self.assertEqual(record["monitoring_after_ticks"], 57*spending.TICKS_PER_USD)
        self.assertEqual(self.monitor.report()["monitoring_overrun_ticks"], 2*spending.TICKS_PER_USD)
        self.assertEqual(self.monitor.report()["token_estimate_subtotal_microusd"], 54_000_000)
        self.assertEqual(self.monitor.report()["provider_reported_subtotal_ticks"], 3*spending.TICKS_PER_USD)
        self.assertFalse(self.monitor.can_dispatch())

    def test_known_zero_is_allowed_but_unknown_stops(self):
        self.begin(); self.settle(0)
        self.assertTrue(self.monitor.can_dispatch())
        self.begin(); record = self.monitor.settle({"status": "unknown", "prospective_cap_proven": False}, False)
        self.assertEqual(record["source"], "unknown")
        self.assertIsNone(record["delta_ticks"])
        self.assertEqual(self.monitor.report()["unknown_settled_charges"], 1)
        self.assertIsNone(self.monitor.report()["invoice_total_usd"])
        self.assertFalse(self.monitor.can_dispatch())

    def test_technical_failure_keeps_known_charge(self):
        self.begin(); self.settle(10, False)
        self.assertEqual(self.monitor.monitored, 100000)
        self.assertEqual(self.monitor.stop_reason, "technical_failure")
        self.assertFalse(self.monitor.can_dispatch())

    def test_technical_failure_and_threshold_both_recorded(self):
        self.begin(); result = self.settle(56_000_000, False)
        self.assertEqual(result["stop_reason"], "technical_failure")
        self.assertTrue(result["threshold_reached"])

    def test_settle_requires_pending_and_cannot_repeat(self):
        with self.assertRaises(spending.guard.AdmissionBlocked): self.monitor.settle(accounting("gemini"), True)
        self.begin(); self.settle()
        with self.assertRaises(spending.guard.AdmissionBlocked): self.monitor.settle(accounting("gemini"), True)

    def test_schedule_cannot_skip_reorder_or_switch_model(self):
        for row, payload in ((self.monitor.rows[1], {"model": self.monitor.rows[1]["model"]}),
                              (self.monitor.rows[0], {"model": "wrong"})):
            with self.assertRaises(spending.guard.AdmissionBlocked): self.monitor.begin(row, payload)
        self.assertEqual(self.monitor.attempts, 0)

    def test_negative_boolean_float_string_and_null_amounts_unknown(self):
        for provider in ("gemini", "grok", "minimax"):
            for value in (-1, True, 0.0, "1", None):
                self.assertIsNone(spending.monitoring_delta(accounting(provider, value), provider)["delta_ticks"])

    def test_wrong_provider_mixed_sources_and_cap_claim_rejected(self):
        a = accounting("grok", 5)
        self.assertIsNone(spending.monitoring_delta(a, "gemini")["delta_ticks"])
        a["undiscounted_token_estimate_microusd"] = 4
        self.assertIsNone(spending.monitoring_delta(a, "grok")["delta_ticks"])
        a = accounting("gemini", 3); a["prospective_cap_proven"] = True
        self.assertIsNone(spending.monitoring_delta(a, "gemini")["delta_ticks"])

    def test_non_boolean_acceptance_does_not_settle(self):
        self.begin()
        with self.assertRaises(ValueError): self.monitor.settle(accounting("gemini"), 1)
        self.assertIsNotNone(self.monitor.pending)

    def test_no_resume_after_unsettled_attempt(self):
        self.begin()
        self.assertEqual(self.monitor.report()["outstanding_attempts"], 1)
        with self.assertRaises(FileExistsError): spending.StopThreshold(ROOT, self.directory)

    def test_admission_disk_failure_cannot_dispatch(self):
        with patch.object(spending.guard, "_write_exclusive", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): self.begin()
        self.assertEqual(self.monitor.stop_reason, "journal_write_failure")
        self.assertFalse(self.monitor.can_dispatch())
        self.assertEqual(self.monitor.report()["outstanding_attempts"], 1)

    def test_settlement_disk_failure_cannot_continue_or_reclaim(self):
        self.begin()
        with patch.object(spending.guard, "_write_exclusive", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): self.settle(100)
        self.assertFalse(self.monitor.can_dispatch())
        self.assertEqual(self.monitor.report()["outstanding_attempts"], 1)

    def test_record_chain_binds_previous_settlement(self):
        first = self.begin(); settled = self.settle(1)
        second = self.begin()
        self.assertEqual(settled["admission_sha256"], spending.sha256_json(first))
        self.assertEqual(second["previous_record_sha256"], spending.sha256_json(settled))

    def test_returned_values_cannot_mutate_internal_ledger(self):
        result = self.begin(); result["row"]["model"] = "wrong"
        self.assertNotEqual(self.monitor.pending["row"]["model"], "wrong")
        result = self.settle(1); result["monitoring_after_ticks"] = 0
        self.assertEqual(self.monitor.records[0]["monitoring_after_ticks"], 10000)

    def test_full_exact_prefix_never_exceeds_816(self):
        for row in self.monitor.rows:
            self.monitor.begin(row, {"model": row["model"]})
            self.monitor.settle(accounting(row["provider"]), True)
        self.assertEqual(self.monitor.attempts, 816)
        self.assertFalse(self.monitor.can_dispatch())
        with self.assertRaises(spending.guard.AdmissionBlocked):
            self.monitor.begin(self.monitor.rows[-1], {"model": self.monitor.rows[-1]["model"]})

    def test_concurrent_admission_keeps_single_in_flight(self):
        row = self.monitor.rows[0]
        def attempt():
            try:
                self.monitor.begin(row, {"model": row["model"]})
                return True
            except spending.guard.AdmissionBlocked:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.monitor.attempts, 1)
        self.assertEqual(self.monitor.report()["outstanding_attempts"], 1)

    def test_private_permissions(self):
        self.begin(); self.settle(1)
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in self.directory.iterdir()))

    def test_scope_is_not_an_approval_and_excludes_confirmation(self):
        scope = spending.approval_scope(ROOT)
        self.assertFalse(scope["paid_calls_approved"])
        self.assertFalse(scope["data_export_approved"])
        self.assertFalse(scope["confirmation_authorized"])
        self.assertNotIn("HC-MT-TRIAGE-022", scope["family_ids"])
        self.assertEqual((scope["candidate_attempts"], scope["judge_attempts"]), (216, 600))
        self.assertEqual(len(scope["candidate_models"]), 6)

    def test_invalid_policy_cannot_enable_live_or_change_threshold(self):
        original = spending.policy(ROOT)
        for key, value in (("live_call_allowance", 816), ("threshold_usd_ticks", 560000000000),
                           ("confirmation_policy_selected", True), ("max_in_flight", 2)):
            changed = {**original, key: value}
            with patch.object(spending, "load_json", return_value=changed):
                with self.assertRaises(ValueError): spending.policy(ROOT)

    def test_frozen_snapshot_and_public_audit(self):
        self.assertEqual(spending.snapshot(ROOT), load_json(ROOT/spending.FREEZE))
        self.assertEqual(spending.audit(ROOT), load_json(ROOT/"data/audit/s40_threshold_summary.json"))


class IntegratedThresholdTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.run = spending.ThresholdRehearsal(ROOT, Path(self.temp.name)/"run")
        self.opens = 0

    def factory(self, host, timeout, grok_ticks=None, missing_usage=False, fail_unsafe=False):
        self.opens += 1
        row = self.run.session.pending
        admission = self.run.monitor.directory/f'{row["sequence"]:04d}.admission.json'
        self.assertTrue(admission.exists())
        self.assertEqual(self.run.monitor.report()["outstanding_attempts"], 1)
        raw = json.loads(reply_fixture(self.run.session)); raw["usage"] = usage_fixture(row["provider"])
        if grok_ticks is not None and row["provider"] == "grok": raw["usage"]["cost_in_usd_ticks"] = grok_ticks
        if missing_usage: del raw["usage"]
        if fail_unsafe and row["profile"] == "unsafe":
            if row["provider"] == "grok": content = raw["output"][0]["content"][0]
            else: content = raw["steps"][0]["content"][0]
            judgment = json.loads(content["text"]); judgment["critical_errors"] = []
            content["text"] = json.dumps(judgment)
        return Connection(Response(json.dumps(raw).encode()))

    def test_full_first_phase_with_accounting_and_threshold(self):
        while self.run.step(connection_factory=self.factory) is not None: pass
        result = self.run.report()
        self.assertEqual(self.opens, 816)
        self.assertEqual(result["terminal"], "schedule_complete")
        self.assertTrue(result["workflow"]["complete"])
        self.assertTrue(result["workflow"]["control_gate"]["pass"])
        self.assertEqual(result["workflow"]["repeat_conversation_judge_records"], 48)
        self.assertEqual(result["spending"]["settled_attempts"], 816)
        self.assertFalse(result["spending"]["threshold_reached"])
        self.assertFalse(result["spending"]["hard_ceiling"])
        self.assertEqual(result["live_calls"], 0)

    def test_crossing_threshold_retains_last_judgment_and_blocks_next(self):
        self.run.step(connection_factory=self.factory)
        result = self.run.step(connection_factory=lambda *a, **k: self.factory(*a, **k, grok_ticks=56*spending.TICKS_PER_USD))
        self.assertTrue(result["accepted"])
        self.assertEqual(result["terminal"], "spend_threshold_reached")
        self.assertEqual(len(self.run.session.judgments), 2)
        self.assertIsNone(self.run.step(connection_factory=lambda *a, **k: self.fail()))
        self.assertEqual(self.opens, 2)
        self.assertFalse(self.run.report()["workflow"]["complete"])

    def test_unknown_charge_stops_without_new_request(self):
        result = self.run.step(connection_factory=lambda *a, **k: self.factory(*a, **k, missing_usage=True))
        self.assertFalse(result["accepted"])
        self.assertEqual(self.run.monitor.stop_reason, "unknown_charge")
        self.assertEqual(self.run.monitor.report()["unknown_settled_charges"], 1)
        self.assertIsNone(self.run.step(connection_factory=lambda *a, **k: self.fail()))

    def test_control_failure_blocks_candidate_despite_remaining_budget(self):
        for _ in range(72):
            result = self.run.step(connection_factory=lambda *a, **k: self.factory(*a, **k, fail_unsafe=True))
            self.assertTrue(result["accepted"])
        self.assertIsNone(self.run.step(connection_factory=lambda *a, **k: self.fail()))
        self.assertEqual(self.run.terminal, "control_gate_failed")
        self.assertEqual(self.opens, 72)
        self.assertEqual(self.run.session.answers, {})

    def test_interrupt_settles_unknown_and_keeps_raw_prefix(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run.step(connection_factory=lambda *a, **k: Connection(Response(chunks=[b"prefix", KeyboardInterrupt()])))
        self.assertEqual(self.run.monitor.stop_reason, "unknown_charge")
        self.assertEqual((self.run.capture.directory/"0001.raw.bin").read_bytes(), b"prefix")
        self.assertIsNone(self.run.step(connection_factory=lambda *a, **k: self.fail()))

    def test_capture_local_failure_keeps_known_charge(self):
        def fail_after_capture(*args, **kwargs):
            raise OSError("local workflow write failed")
        with patch.object(self.run.session, "accept_reply", side_effect=fail_after_capture):
            with self.assertRaises(OSError): self.run.step(connection_factory=self.factory)
        self.assertGreater(self.run.monitor.monitored, 0)
        self.assertEqual(self.run.monitor.stop_reason, "technical_failure")
        self.assertEqual(self.run.monitor.report()["unknown_settled_charges"], 0)


if __name__ == "__main__":
    unittest.main()
