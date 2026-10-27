"""Simulated integration only; no credentials, external connections or clinical truth."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import standalone_rehearsal_s61 as run

ROOT = Path(__file__).resolve().parents[1]


def altered(core, transform):
    fixture = run.next_fixture(core)
    raw = json.loads(fixture.body)
    transform(raw)
    return run.Fixture(run.guard._json_bytes(raw))


def judge_edit(raw, transform):
    text = raw["steps"][0]["content"][0]
    value = json.loads(text["text"])
    transform(value)
    text["text"] = json.dumps(value, ensure_ascii=False)


def advance(writer, until):
    while writer.core.index < until and writer.step(run.next_fixture(writer.core)) is not None:
        pass
    return writer


class StandaloneRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.complete_path = Path(cls.temp.name).resolve() / "complete"
        with patch("socket.socket.connect", side_effect=AssertionError("No network")), \
             patch("os.getenv", side_effect=AssertionError("No credential access")):
            cls.complete = run.Rehearsal(ROOT, cls.complete_path, mode="offline_transport_fixture")
            while cls.complete.step(run.next_fixture(cls.complete.core)) is not None:
                pass
            cls.replayed = run.replay(ROOT, cls.complete_path)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name).resolve() / "run"

    def new(self, **kw):
        return run.Rehearsal(ROOT, self.directory, mode="offline_transport_fixture", **kw)

    def test_complete_480_request_rehearsal_and_replay(self):
        value = self.replayed
        self.assertEqual(value["events"], 480)
        self.assertTrue(value["report_verified"])
        self.assertIsNone(value["incomplete_tail"])
        self.assertEqual(value["report"], self.complete.core.report())
        report = value["report"]
        self.assertEqual(report["outcomes"], {"accepted": 480})
        self.assertEqual(report["terminal"], "schedule_complete")
        self.assertEqual(report["repeat_summary"]["complete_pairs"], 64)
        self.assertEqual(report["repeat_summary"]["matching_criterion_error_vectors"], 128)
        self.assertTrue(all(len(c["answer_stages_present"]) == 2 for c in report["conversations"]))

    def test_simulated_scores_cannot_look_like_measurements(self):
        summary = run.public_summary(self.replayed)
        self.assertTrue(summary["simulation_only"])
        self.assertEqual(summary["measured_model_scores"], 0)
        self.assertEqual(summary["live_calls"], 0)
        self.assertEqual(summary["complete_fixture_first_conversations"], 64)
        self.assertEqual(summary["complete_fixture_repeat_conversations"], 64)
        self.assertNotIn("point_score", json.dumps(summary))
        self.assertNotIn("response_evidence", json.dumps(summary))
        self.assertNotIn("rationale", json.dumps(summary))

    def test_saved_public_summary_reproduces(self):
        expected = run.read(ROOT / "data/audit/s61_standalone_rehearsal.json")
        self.assertEqual(run.public_summary(self.replayed), expected)

    def test_semantic_disagreement_remains_visible_without_relabelling(self):
        core = self.complete.core
        key = next(k for k in core.judgments if k.startswith("control_first") and k.endswith("__unsafe"))
        old = core.judgments[key]
        try:
            core.judgments[key] = {**deepcopy(old), "critical_errors": []}
            result = core.control_readout()
            self.assertTrue(result["structurally_complete"])
            self.assertEqual(result["observed_unsafe_error_matches"], 15)
            self.assertEqual(result["unsafe_hypothesis_mismatches"], [key.removeprefix("control_first__")])
            self.assertEqual(result["clinical_gate"], "not_selected")
        finally:
            core.judgments[key] = old

    def test_all_cells_review_held_and_no_pooled_mean(self):
        report = self.replayed["report"]
        self.assertEqual(len(report["conversations"]), 64)
        self.assertTrue(all(c["clinical_comparison_held"] for c in report["conversations"]))
        self.assertFalse(report["reporting"]["pooled_model_means"])
        self.assertFalse(report["reporting"]["model_rankings"])

    def test_fixture_admission_is_not_clinical_gate_or_forced_order(self):
        value = self.replayed["report"]["control_readout"]
        self.assertTrue(value["structurally_complete"])
        self.assertEqual(value["accepted_records"], 96)
        self.assertEqual(value["observed_unsafe_error_matches"], 16)
        self.assertEqual(value["clinical_gate"], "not_selected")
        self.assertFalse(value["numeric_order_gate"])
        self.assertEqual(len(value["stage_results"]), 96)
        self.assertEqual(value["non_unsafe_records_with_errors"], [])

    def test_non_unsafe_control_errors_are_visible_not_overridden(self):
        writer = self.new()
        packet = writer.core.controls[writer.core.rows[0]["control_key"]]
        error = packet["turn_labels"][0]["critical_errors"][0]
        def add_error(value):
            value["critical_errors"] = [{"stage_id": "initial", "error_id": error["id"],
                                         "severity": error["severity"], "rationale": "Fixture discrepancy"}]
        writer.step(altered(writer.core, lambda raw: judge_edit(raw, add_error)))
        readout = run.replay(ROOT, self.directory)["report"]["control_readout"]
        self.assertEqual(readout["non_unsafe_records_with_errors"], [writer.core.rows[0]["id"]])
        self.assertEqual(readout["stage_results"][0]["critical_errors"][0]["error_id"], error["id"])

    def test_no_live_mode_key_factory_or_reuse(self):
        with self.assertRaises(ValueError):
            run.Rehearsal(ROOT, self.directory, mode="live")
        writer = self.new()
        with self.assertRaises(FileExistsError): self.new()
        with self.assertRaises(ValueError): writer.step(lambda: b"{}")
        with self.assertRaises(TypeError): writer.step(run.Fixture(), credential="not-a-key")
        with self.assertRaises(TypeError): writer.step(run.Fixture(), connection_factory=lambda: None)
        self.assertEqual(writer._event, 0)

    def test_request_is_saved_before_simulated_connection(self):
        writer = self.new()
        original = run.fake._Connection
        def connect(fixture):
            event = self.directory / "events/0001"
            self.assertTrue((event / "reservation.json").is_file())
            self.assertTrue((event / "payload.json").is_file())
            self.assertTrue((event / "transport/0001.payload.json").is_file())
            return original(fixture)
        with patch.object(run.fake, "_Connection", side_effect=connect):
            writer.step(run.next_fixture(writer.core))
        self.assertEqual(len(writer.last_connection.requests), 1)
        self.assertTrue(writer.last_connection.closed)

    def test_initial_judge_visibility_and_four_criterion_updates(self):
        for row in self.complete.core.rows:
            context = self.complete.core.contexts[row["id"]]
            packet = context["packet"]
            if packet is None:
                continue
            stage = packet["scoring_stage"]
            self.assertEqual(len(packet["transcript"]), 2 if stage == "initial" else 4)
            self.assertEqual({a["stage_id"] for a in packet["criterion_anchors"]}, {stage})
            self.assertEqual({t["stage_id"] for t in packet["turn_labels"]}, {stage})
        self.assertTrue(any(len(c["packet"]["criterion_anchors"]) == 4 for c in self.complete.core.contexts.values() if c["packet"]))

    def test_candidate_history_excludes_reasoning_and_author_metadata(self):
        for row in self.complete.core.rows:
            if row["kind"] != "candidate": continue
            context = self.complete.core.contexts[row["id"]]
            payload = json.dumps(context["payload"], ensure_ascii=False)
            self.assertNotIn("FIXTURE_REASONING_NOT_FOR_HISTORY", payload)
            for marker in ("critical_requirements", "criterion_anchors", "hypothesized_error_id", "review_issues"):
                self.assertNotIn(marker, payload)
            cell = self.complete.core.cells[row["cell_id"]]
            family = self.complete.core.catalog[cell["family_id"]]["family"]
            if row["stage"] == "initial":
                self.assertNotIn(family["variants"][cell["language"]]["turns"][1]["user"], payload)
            else:
                self.assertIn(self.complete.core.stage_answer(cell, "initial"), payload)

    def test_identical_repeat_payload_bytes(self):
        core = self.complete.core
        for row in core.rows:
            if row["kind"] not in ("control_repeat", "judge_repeat"): continue
            self.assertEqual(run.guard._json_bytes(core.contexts[row["id"]]["payload"]),
                             run.guard._json_bytes(core.contexts[run.engine.first_id(row)]["payload"]))

    def test_candidate_identity_binding_detects_cross_model_swap(self):
        core = self.complete.core
        keys = list(core.answers)
        a, b = keys[0], next(k for k in keys if core.answers[k]["binding"]["model"] != core.answers[keys[0]]["binding"]["model"])
        original = core.answers[a]
        try:
            core.answers[a] = deepcopy(core.answers[b])
            cell = core.cells[original["binding"]["cell_id"]]
            with self.assertRaises(ValueError): core.stage_answer(cell, "initial")
        finally:
            core.answers[a] = original

    def test_http_errors_never_score_valid_looking_body(self):
        for status in (302, 403, 429, 500):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp).resolve() / "run"
                writer = run.Rehearsal(ROOT, directory, mode="offline_transport_fixture")
                fixture = run.next_fixture(writer.core)
                writer.step(run.Fixture(fixture.body, status=status))
                report = run.replay(ROOT, directory)["report"]
                self.assertEqual(report["terminal"], "unknown_delivery_or_cost")
                self.assertEqual(report["unknown_simulated_cost_attempts"], 1)
                self.assertEqual(len(writer.core.judgments), 0)
                self.assertIsNone(writer.step(fixture))

    def test_transport_faults_capture_prefix_and_stop(self):
        for fault in ("connect_timeout", "response_timeout", "read_timeout", "incomplete_read"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp).resolve() / "run"
                writer = run.Rehearsal(ROOT, directory, mode="offline_transport_fixture")
                writer.step(run.Fixture(b"prefix", fault=fault))
                value = run.replay(ROOT, directory)
                self.assertEqual(value["report"]["settled_fixture_attempts"], 1)
                self.assertEqual(value["report"]["unknown_simulated_cost_attempts"], 1)
                self.assertEqual(value["report"]["unresolved_reservations"], 0)

    def test_unknown_usage_and_malformed_body_stop(self):
        for missing in (True, False):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp).resolve() / "run"
                writer = run.Rehearsal(ROOT, directory, mode="offline_transport_fixture")
                fixture = altered(writer.core, lambda raw: raw.pop("usage")) if missing else run.Fixture(b"not-json")
                writer.step(fixture)
                self.assertEqual(run.replay(ROOT, directory)["report"]["unknown_simulated_cost_attempts"], 1)

    def test_known_cost_invalid_judge_is_unscored_and_stops(self):
        writer = self.new()
        writer.step(altered(writer.core, lambda raw: raw.update(status="incomplete")))
        report = run.replay(ROOT, self.directory)["report"]
        self.assertEqual(report["terminal"], "invalid_judge_reply")
        self.assertEqual(report["unknown_simulated_cost_attempts"], 0)
        self.assertTrue(all(c["first"]["score"] is None for c in report["conversations"]))

    def test_invalid_candidate_closes_only_that_candidate_lane(self):
        writer = advance(self.new(), 96)
        row = writer.core.rows[96]
        model = writer.core.provider(row)["model"]
        writer.step(altered(writer.core, lambda raw: raw.update(status="incomplete")))
        writer.step(run.next_fixture(writer.core))
        report = run.replay(ROOT, self.directory)["report"]
        self.assertEqual(report["closed_candidate_models"], [model])
        self.assertIsNone(report["terminal"])
        self.assertEqual(len(report["conversations"]), 64)
        self.assertEqual(report["outcomes"]["skipped"], 1)
        self.assertEqual(report["outcomes"]["rejected"], 1)

    def test_missing_update_preserves_initial_judgment_and_all_cells(self):
        writer = advance(self.new(), 97)
        cid = writer.core.rows[97]["cell_id"]
        writer.step(altered(writer.core, lambda raw: raw.update(status="incomplete")))
        while writer.step(run.next_fixture(writer.core)) is not None:
            pass
        report = run.replay(ROOT, self.directory)["report"]
        cell = next(c for c in report["conversations"] if c["cell_id"] == cid)
        self.assertEqual(cell["answer_stages_present"], ["initial"])
        self.assertIsNotNone(cell["first"]["judgments"]["initial"])
        self.assertIsNone(cell["first"]["judgments"]["update"])
        self.assertIsNone(cell["first"]["score"])
        self.assertEqual(len(report["conversations"]), 64)

    def test_repeat_score_changes_preserved_not_averaged(self):
        writer = advance(self.new(), 352)
        cid = writer.core.rows[352]["cell_id"]
        def change(value):
            for row in value["criterion_assessments"]: row["status"] = "missed"
        writer.step(altered(writer.core, lambda raw: judge_edit(raw, change)))
        writer.step(altered(writer.core, lambda raw: judge_edit(raw, change)))
        report = run.replay(ROOT, self.directory)["report"]
        cell = next(c for c in report["conversations"] if c["cell_id"] == cid)
        self.assertEqual(cell["first"]["score"]["point_score"], 100)
        self.assertEqual(cell["repeat"]["score"]["point_score"], 0)
        self.assertIn(cid, report["repeat_summary"]["pass_changed_cells"])

    def test_unclear_remains_interval_not_zero_or_failure(self):
        writer = advance(self.new(), 224)
        cid = writer.core.rows[224]["cell_id"]
        writer.step(altered(writer.core, lambda raw: judge_edit(raw,
            lambda value: value["criterion_assessments"][0].update(status="unclear"))))
        writer.step(run.next_fixture(writer.core))
        cell = next(c for c in run.replay(ROOT, self.directory)["report"]["conversations"] if c["cell_id"] == cid)
        self.assertIsNone(cell["first"]["score"]["point_score"])
        self.assertEqual(cell["first"]["score"]["criterion_score_interval"], [90.0, 100.0])

    def test_threshold_overrun_stops_after_one_accounted_attempt(self):
        writer = self.new(fixture_threshold_usd="0.01")
        def usage(raw):
            raw["usage"].update(total_output_tokens=20000, total_tokens=20029)
        writer.step(altered(writer.core, usage))
        report = run.replay(ROOT, self.directory)["report"]
        self.assertEqual(report["terminal"], "simulated_spend_threshold_reached")
        self.assertGreater(float(report["simulated_monitoring_usd"]), .01)
        self.assertEqual(report["settled_fixture_attempts"], 1)

    def test_minimax_default_echo_uses_existing_conservative_fixture_accounting(self):
        writer = advance(self.new(), 102)
        self.assertEqual(writer.core.provider(writer.core.rows[102])["model"], "MiniMax-M3")
        writer.step(altered(writer.core, lambda raw: raw.update(service_tier="default")))
        self.assertEqual(writer.core.accounts[-1]["tier_status"], "unverified_default_response_to_explicit_standard_request")
        self.assertEqual(run.replay(ROOT, self.directory)["report"]["unknown_simulated_cost_attempts"], 0)

    def test_length_and_encoding_faults_stay_unscored(self):
        for headers in ({"Content-Length": "999"}, {"Content-Encoding": "gzip"}):
            with self.subTest(headers=headers), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp).resolve() / "run"
                writer = run.Rehearsal(ROOT, directory, mode="offline_transport_fixture")
                writer.step(run.Fixture(run.next_fixture(writer.core).body, headers=headers))
                self.assertEqual(run.replay(ROOT, directory)["report"]["unknown_simulated_cost_attempts"], 1)

    def test_interrupt_has_no_retry_or_double_counted_attempt(self):
        writer = self.new()
        with self.assertRaises(KeyboardInterrupt): writer.step(run.Fixture(b"prefix", fault="interrupt"))
        with self.assertRaises(ValueError): writer.step(run.Fixture())
        value = run.replay(ROOT, self.directory)
        self.assertEqual(value["incomplete_tail"], "captured_reply_reconstructed_without_result")
        self.assertEqual(value["report"]["settled_fixture_attempts"], 1)
        self.assertEqual(value["report"]["unresolved_reservations"], 0)
        self.assertFalse(value["resume_allowed"])

    def test_result_write_failure_replays_once_read_only(self):
        writer = self.new()
        original = run.write
        def fail(path, value):
            if path.name == "result.json": raise OSError("simulated disk failure")
            return original(path, value)
        with patch.object(run, "write", side_effect=fail), self.assertRaises(OSError):
            writer.step(run.next_fixture(writer.core))
        before = {str(p): run.digest(p.read_bytes()) for p in self.directory.rglob("*") if p.is_file()}
        value = run.replay(ROOT, self.directory)
        self.assertEqual(value["report"]["outcomes"], {"accepted": 1})
        self.assertEqual(value["report"]["unresolved_reservations"], 0)
        self.assertEqual(before, {str(p): run.digest(p.read_bytes()) for p in self.directory.rglob("*") if p.is_file()})
        with self.assertRaises(ValueError): writer.step(run.Fixture())

    def test_payload_write_failure_remains_unresolved(self):
        writer = self.new()
        original = run.write
        def fail(path, value):
            if path.name == "payload.json": raise OSError("simulated disk failure")
            return original(path, value)
        with patch.object(run, "write", side_effect=fail), self.assertRaises(OSError):
            writer.step(run.next_fixture(writer.core))
        value = run.replay(ROOT, self.directory)
        self.assertEqual(value["report"]["unresolved_reservations"], 1)
        self.assertEqual(value["report"]["settled_fixture_attempts"], 0)

    def test_tampered_payload_raw_result_and_report_rejected(self):
        for target in ("events/0001/payload.json", "events/0001/transport/0001.raw.bin", "events/0001/result.json", "report.json"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp).resolve() / "run"
                writer = run.Rehearsal(ROOT, directory, mode="offline_transport_fixture")
                writer.step(run.Fixture(b"error", status=403))
                (directory / target).write_bytes(b"{}")
                with self.assertRaises((ValueError, KeyError)):
                    run.replay(ROOT, directory)

    def test_secret_header_not_written_to_any_journal(self):
        writer = self.new()
        writer.step(run.next_fixture(writer.core))
        self.assertFalse(any(b"S61-FIXTURE-ONLY" in p.read_bytes() for p in self.directory.rglob("*") if p.is_file()))

    def test_public_output_path_and_linked_capture_rejected(self):
        with self.assertRaises(ValueError): run.safe_directory(ROOT, ROOT / "data/s61-output")
        writer = self.new()
        writer.step(run.next_fixture(writer.core))
        (self.directory / "events/0001/linked").symlink_to(ROOT / "README.md")
        with self.assertRaises(ValueError): run.replay(ROOT, self.directory)

    def test_stale_protocol_rejected(self):
        writer = self.new()
        writer.step(run.next_fixture(writer.core))
        with patch.object(run, "snapshot", return_value={"changed": True}), self.assertRaises(ValueError):
            run.replay(ROOT, self.directory)

    def test_midrun_input_change_poisoned_before_new_reservation(self):
        writer = self.new()
        writer.step(run.next_fixture(writer.core))
        writer.input_pins[run.engine.PLAN] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Inputs changed"):
            writer.step(run.next_fixture(writer.core))
        self.assertEqual(writer._event, 1)
        with self.assertRaisesRegex(ValueError, "Interrupted writer"):
            writer.step(run.Fixture())

    def test_duplicate_prepare_cannot_dispatch(self):
        core = run.engine.Engine(ROOT, mode="offline_transport_fixture")
        core.prepare()
        with self.assertRaises(ValueError): core.prepare()


if __name__ == "__main__":
    unittest.main()
