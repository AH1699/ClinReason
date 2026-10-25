"""Offline failure/replay tests; fake keys/HTTP only, no model measurements."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import independent_eval_s45 as run
from tests.test_transport_s39 import Connection, Response
from tests.test_workflow_s38 import envelope, judgment_fixture
from tests.test_usage_s39 import usage_fixture

ROOT = Path(__file__).resolve().parents[1]
KEYS = {p: "S45-FAKE-KEY" for p in ("gemini", "grok", "minimax")}


def connection(session, change=None):
    def factory(host, timeout):
        row = session.pending
        context = session.contexts[row["sequence"]]
        if row["kind"] == "candidate":
            text = f'Fixture {row["stage"]} answer. Not clinical advice.'
        else:
            text = json.dumps(judgment_fixture(context["packet"], row["profile"]), ensure_ascii=False)
        raw = json.loads(envelope(row, text))
        raw["usage"] = usage_fixture(row["provider"])
        response = Response(json.dumps(raw, ensure_ascii=False).encode())
        return Connection(change(row, raw, response) if change else response)
    return factory


def finish(session, change=None, stop_at=None):
    while session.terminal is None and (stop_at is None or session.index < stop_at):
        session.step(KEYS, connection(session, change))
    return session


class IndependentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_all = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp_all.cleanup)
        cls.spec = run.plan(ROOT)
        cls.complete = finish(run.Session(ROOT, Path(cls.temp_all.name)/"complete", cls.spec,
                                           "OFFLINE-NOT-AUTHORIZATION", mode="offline_fixture"))
        cls.complete.seal_bank()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def new(self, spec=None, name="run", source_answers=None):
        return run.Session(ROOT, Path(self.temp.name)/name, spec or self.spec, "OFFLINE-NOT-AUTHORIZATION",
                           mode="offline_fixture", source_answers=source_answers)

    def test_pilot_saves_all_candidates_before_controls_and_scores(self):
        rows = self.complete.rows
        self.assertEqual(len(rows), 68)
        self.assertTrue(all(r["kind"] == "candidate" for r in rows[:16]))
        self.assertTrue(all(r["block"] == "control" for r in rows[16:52]))
        self.assertEqual({r["provider"] for r in rows}, {"gemini", "minimax"})
        self.assertEqual(len(self.complete.answers), 16)
        report = self.complete.report()
        self.assertTrue(report["complete"])
        self.assertTrue(report["controls"]["gemini-3.8-flash"]["pass"])
        self.assertEqual(len(report["score_records"]), 8)
        self.assertTrue(all(r["simulation_only"] for r in report["score_records"]))
        self.assertFalse(report["model_rankings_approved"])

    def test_replay_matches_raw_results_and_cannot_dispatch(self):
        replay = run.replay(ROOT, self.complete.directory)
        self.assertEqual(replay.report(), self.complete.report())
        self.assertEqual(replay.bank(), self.complete.bank())
        with self.assertRaises(run.guard.AdmissionBlocked):
            replay.step(KEYS, lambda *a, **k: self.fail("Replay performed network"))

    def test_judge_unknown_charge_keeps_all_answers_and_fixed_missing_denominator(self):
        def fail_judge(row, raw, response):
            return Response(b'Forbidden', 403) if row["kind"] == "judge" else response
        s = finish(self.new(), fail_judge)
        self.assertEqual(s.terminal, "unknown_charge")
        self.assertEqual(len(s.answers), 16)
        s.seal_bank()
        report = run.replay(ROOT, s.directory).report()
        self.assertEqual(report["attempts"], 17)
        self.assertEqual(report["accounting"]["unknown_charge_attempts"], 1)
        self.assertEqual(report["separate_judge_reports"]["gemini-3.8-flash"]["expected_cells"], 8)
        self.assertIsNone(report["separate_judge_reports"]["gemini-3.8-flash"]["point_mean"])
        self.assertEqual(report["separate_judge_reports"]["gemini-3.8-flash"]["full_denominator_interval"], [0, 100])
        self.assertIsNone(s.step(KEYS, lambda *a, **k: self.fail("Retry")))

    def test_known_cost_candidate_failure_closes_only_its_model(self):
        def fail_one(row, raw, response):
            if row["sequence"] == 1:
                raw["status"] = "incomplete"
                return Response(json.dumps(raw).encode())
            return response
        s = finish(self.new(), fail_one)
        self.assertEqual(s.terminal, "schedule_complete")
        self.assertEqual(len(s.answers), 12)
        self.assertEqual(list(s.closed_lanes), ["candidate:gemini-3.5-flash-lite"])
        self.assertEqual(len(s.report()["score_records"]), 6)
        self.assertIsNone(s.report()["separate_judge_reports"]["gemini-3.8-flash"]["point_mean"])
        self.assertEqual(run.replay(ROOT, s.directory).report(), s.report())

    def test_one_judge_validation_failure_does_not_block_another(self):
        spec = deepcopy(self.spec)
        spec["judge_models"].append("grok-4.7")
        spec["maximum_attempts"] = 120
        def fail_grok(row, raw, response):
            if row["provider"] == "grok":
                raw["status"] = "incomplete"  # Known cost; not a 403/unknown billing event.
                return Response(json.dumps(raw).encode())
            return response
        s = finish(self.new(spec), fail_grok)
        report = s.report()
        self.assertEqual(s.terminal, "schedule_complete")
        self.assertEqual(len(report["score_records"]), 8)
        self.assertEqual({r["judge"] for r in report["score_records"]}, {"gemini-3.8-flash"})
        self.assertFalse(report["controls"]["grok-4.7"]["pass"])
        self.assertIsNone(report["separate_judge_reports"]["grok-4.7"]["point_mean"])
        self.assertEqual(run.replay(ROOT, s.directory).report(), report)

    def test_failed_control_order_does_not_erase_candidate_answers_or_fake_pass(self):
        def all_safe(row, raw, response):
            if row["block"] == "control":
                text = json.dumps(judgment_fixture(s.contexts[row["sequence"]]["packet"]))
                raw = json.loads(envelope(row, text)); raw["usage"] = usage_fixture(row["provider"])
                return Response(json.dumps(raw).encode())
            return response
        s = self.new()
        finish(s, all_safe)
        report = s.report()
        self.assertEqual(report["attempts"], 52)
        self.assertEqual(report["accepted_answer_stages"], 16)
        self.assertTrue(report["controls"]["gemini-3.8-flash"]["complete"])
        self.assertFalse(report["controls"]["gemini-3.8-flash"]["pass"])
        self.assertEqual(report["score_records"], [])

    def test_update_uses_exact_saved_initial_without_labels_or_future_leak(self):
        s = finish(self.new(), stop_at=2)
        first, update = s.rows[:2]
        a = s.contexts[first["sequence"]]["payload"]
        b = s.contexts[update["sequence"]]["payload"]
        first_answer = s.answers[run.workflow.answer_key(first)]["text"]
        self.assertIn(first_answer, json.dumps(b))
        self.assertNotIn(first_answer, json.dumps(a))
        self.assertNotIn("critical_requirements", json.dumps(b))
        self.assertNotIn("criterion_anchors", json.dumps(a))
        family = s.catalog[first["family_id"]][0]
        self.assertNotIn(family["variants"][first["language"]]["turns"][1]["user"], json.dumps(a, ensure_ascii=False))

    def test_new_judge_consumes_saved_bank_without_candidate_dispatch(self):
        source = self.complete.bank()["answers"]
        spec = deepcopy(self.spec)
        spec.update(generate_candidates=False, maximum_attempts=52,
                    source_bank={"run_directory": "work/fixture", "sha256": run.sha256_json(self.complete.bank())})
        s = finish(self.new(spec, source_answers=source))
        self.assertTrue(all(r["kind"] == "judge" for r in s.rows))
        self.assertEqual(s.answers, self.complete.answers)
        self.assertTrue(s.report()["complete"])

    def test_tampered_answer_and_case_version_blocked(self):
        for field, value in (("answer_sha256", "wrong"), ("case_version", "wrong"), ("case_content_hash", "wrong")):
            source = deepcopy(self.complete.bank()["answers"])
            source[0]["binding"][field] = value
            spec = deepcopy(self.spec); spec.update(generate_candidates=False, maximum_attempts=52)
            with self.assertRaises(ValueError):
                self.new(spec, name=field, source_answers=source)

    def test_duplicate_answer_rejected(self):
        source = self.complete.bank()["answers"]
        spec = deepcopy(self.spec); spec.update(generate_candidates=False, maximum_attempts=52)
        with self.assertRaises(ValueError):
            self.new(spec, source_answers=source + source[:1])

    def test_threshold_is_shared_and_last_call_overrun_retained(self):
        spec = deepcopy(self.spec); spec["stop_threshold_usd"] = "0.01"
        def costly(row, raw, response):
            raw["usage"].update(total_input_tokens=1000, total_output_tokens=8000, total_thought_tokens=0, total_tokens=9000)
            return Response(json.dumps(raw).encode())
        s = finish(self.new(spec), costly)
        self.assertEqual(s.terminal, "spend_threshold_reached")
        self.assertEqual(len(s.accounts), 1)
        self.assertGreater(float(s.report()["monitoring_amount_usd"]), .01)
        self.assertEqual(len(s.answers), 1)

    def test_interruption_is_nonresumable_and_visible_as_outstanding(self):
        s = self.new()
        with patch.object(run.capture.CaptureJournal, "exchange", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                s.step(KEYS, lambda *a, **k: self.fail())
        self.assertEqual(s.terminal, "local_failure_or_interruption")
        self.assertEqual(s.report()["outstanding_attempts_unknown_delivery_or_charge"], 1)
        replay = run.replay(ROOT, s.directory)
        self.assertEqual(replay.terminal, "incomplete_local_attempt_unknown_delivery")
        self.assertEqual(replay.report()["outstanding_attempts_unknown_delivery_or_charge"], 1)
        with self.assertRaises(FileExistsError):
            self.new()

    def test_bank_sealed_before_any_judge_request(self):
        s = finish(self.new(), stop_at=16)
        original = connection(s)
        def inspect(host, timeout):
            self.assertEqual(run.read_json(s.directory / "answer-bank.json"), s.bank())
            return original(host, timeout)
        s.step(KEYS, inspect)

    def test_saved_capture_survives_result_write_interruption(self):
        s = self.new()
        original = run.write_json
        def fail_result(path, value):
            if Path(path).name == "result.json":
                raise OSError("Fixture disk failure")
            return original(path, value)
        with patch.object(run, "write_json", side_effect=fail_result):
            with self.assertRaises(OSError):
                s.step(KEYS, connection(s))
        before = s.report()
        self.assertEqual(before["attempts"], 1)
        self.assertEqual(before["accounting"]["token_estimate_count"], 1)
        self.assertGreater(float(before["monitoring_amount_usd"]), 0)
        replay = run.replay(ROOT, s.directory)
        self.assertEqual(replay.terminal, "interrupted_after_capture")
        self.assertEqual(len(replay.answers), 1)
        self.assertEqual(replay.report()["read_only_recovered_sequences"], [1])
        self.assertEqual(replay.report()["attempts"], 1)
        self.assertEqual(replay.report()["monitoring_amount_usd"], before["monitoring_amount_usd"])
        with self.assertRaises(run.guard.AdmissionBlocked):
            replay.step(KEYS, lambda *a, **k: self.fail("No resume"))

    def test_missing_prefix_cannot_hide_later_calls(self):
        s = finish(self.new(), stop_at=2)
        first = s.directory / "jobs" / run.job_id(s.rows[0])
        first.rename(Path(self.temp.name) / "displaced-first")
        with self.assertRaisesRegex(ValueError, "missing prefix"):
            run.replay(ROOT, s.directory)

    def test_replay_rejects_changed_raw_response(self):
        s = finish(self.new(), stop_at=1)
        raw_path = s.directory / "jobs" / run.job_id(s.rows[0]) / "capture" / "0001.raw.bin"
        original = Path.read_bytes
        with patch.object(Path, "read_bytes", lambda p: b"changed" if p == raw_path else original(p)):
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                run.replay(ROOT, s.directory)

    def test_cannot_turn_unknown_403_cost_into_zero(self):
        s = finish(self.new(), lambda row, raw, response: Response(b"Forbidden", 403))
        original = run.read_json
        known = run.usage.account({"model": s.rows[0]["model"], "usage": usage_fixture("gemini")},
                                  run.workflow.design(ROOT)["candidates"][0])
        def forged(path):
            value = original(path)
            if Path(path).name == "result.json":
                value["accounting"] = known
            elif Path(path).name == "0001.accounting.json":
                value = known
            return value
        with patch.object(run, "read_json", side_effect=forged):
            with self.assertRaisesRegex(ValueError, "Accounting"):
                run.replay(ROOT, s.directory)

    def test_import_checks_sealed_bank_raw_provenance_and_preserves_answers(self):
        with tempfile.TemporaryDirectory(prefix="s45-test-", dir=ROOT / "work") as directory:
            source = finish(run.Session(ROOT, Path(directory)/"source", self.spec, "OFFLINE-NOT-AUTHORIZATION",
                                        mode="offline_fixture"), stop_at=2)
            source.seal_bank()
            spec = deepcopy(self.spec)
            spec.update(generate_candidates=False, maximum_attempts=52,
                source_bank={"run_directory": source.directory.relative_to(ROOT).as_posix(), "sha256": run.sha256_json(source.bank())})
            imported = run.import_bank(ROOT, spec, "offline_fixture")
            self.assertEqual(imported, source.bank()["answers"])
            s = self.new(spec, source_answers=imported)
            self.assertEqual(run.replay(ROOT, s.directory).answers, source.answers)
            spec["source_bank"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                run.import_bank(ROOT, spec, "offline_fixture")
            with self.assertRaisesRegex(ValueError, "mode/hash mismatch"):
                run.import_bank(ROOT, {**spec, "source_bank": {**spec["source_bank"], "sha256": run.sha256_json(source.bank())}}, "live")

    def test_secrets_never_in_saved_metadata_or_banks(self):
        for path in self.complete.directory.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"S45-FAKE-KEY", path.read_bytes())
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_frozen_historical_workflow_unchanged(self):
        self.assertEqual(run.prior.snapshot(ROOT), run.read_json(ROOT / run.prior.FREEZE))

    def test_plan_is_keyless_and_offline(self):
        with patch.object(run.prior, "read_setting", side_effect=AssertionError("No key")), \
                patch.object(run.prior, "create_tls_connection", side_effect=AssertionError("No HTTP")):
            self.assertEqual(run.plan(ROOT)["maximum_attempts"], 68)
            self.assertEqual(len(run.schedule(ROOT, self.spec)), 68)


if __name__ == "__main__":
    unittest.main()
