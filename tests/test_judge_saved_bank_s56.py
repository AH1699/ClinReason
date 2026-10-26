"""Offline fixtures only. No source private text, credentials or network."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import judge_saved_bank_s56 as run
from tests.test_mixed_panel_s51 import imports, reply

ROOT = Path(__file__).resolve().parents[1]


def fixture_bank():
    catalog, controls = run.workflow.families(ROOT), run.score.controls(ROOT)
    rows = run.panel.candidate_rows(ROOT)
    answers = {run.workflow.answer_key(r): {"text": f"Fixture {r['model']} {r['family_id']} {r['language']} {r['stage']}."} for r in rows}
    records = []
    for row in rows:
        family = catalog[row["family_id"]][0]
        result = answers[run.workflow.answer_key(row)]
        payload = run.workflow.request_context(ROOT, row, catalog, controls, answers)["payload"]
        records.append({"row": row, "result": result,
            "binding": {"case_version": family["version"],
                "case_content_hash": run.workflow.variant_hash(family, row["language"]),
                "answer_sha256": run.panel.sha256_json(result), "raw_sha256": "a" * 64,
                "payload_sha256": run.digest(run.guard._json_bytes(payload))},
            "origin": {"kind": "upstream_import" if row["family_id"] == run.panel.HOLD else "s54_candidate"}})
    return {"version": run.VERSION, "mode": "offline_fixture", "source_protocol_sha256": "b" * 64,
            "source_tree_sha256": "c" * 64, "answers": records}


class BankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = fixture_bank()
        cls.answers = run.validate_records(ROOT, cls.bank["answers"])
        cls.catalog, cls.controls = run.workflow.families(ROOT), run.score.controls(ROOT)

    def test_all_144_unique_stages_and_72_conversations(self):
        self.assertEqual(len(self.answers), 144)
        self.assertEqual(len({k[:3] for k in self.answers}), 72)
        self.assertEqual(sum(r["origin"]["kind"] == "upstream_import" for r in self.bank["answers"]), 16)

    def test_missing_extra_reordered_and_duplicate_stages_rejected(self):
        records = self.bank["answers"]
        for changed in (records[:-1], records + records[:1], list(reversed(records)), records[:1] + records[:-1]):
            with self.assertRaises(ValueError): run.validate_records(ROOT, changed)

    def test_model_language_stage_case_and_hash_tampering(self):
        for field, key, value in (("row", "model", "other"), ("row", "language", "fr"),
                ("row", "stage", "update"), ("binding", "case_version", "changed"),
                ("binding", "case_content_hash", "a" * 64), ("binding", "answer_sha256", "a" * 64),
                ("binding", "raw_sha256", "not-a-hash"), ("binding", "payload_sha256", "a" * 64)):
            records = deepcopy(self.bank["answers"])
            records[0][field][key] = value
            with self.assertRaises(ValueError): run.validate_records(ROOT, records)

    def test_changed_initial_answer_cannot_keep_old_followup_payload(self):
        records = deepcopy(self.bank["answers"])
        records[0]["result"]["text"] += " changed history"
        records[0]["binding"]["answer_sha256"] = run.panel.sha256_json(records[0]["result"])
        with self.assertRaisesRegex(ValueError, "history"): run.validate_records(ROOT, records)

    def test_reasoning_or_extra_result_fields_rejected(self):
        for change in ({"text": "<think>private</think>answer"}, {"text": "answer", "reasoning": "private"}, {"text": " "}):
            records = deepcopy(self.bank["answers"]); records[0]["result"] = change
            with self.assertRaises(ValueError): run.validate_records(ROOT, records)

    def test_self_rehashed_tampering_and_changed_provenance_not_trusted(self):
        for field in ("result", "origin", "binding"):
            changed = deepcopy(self.bank)
            if field == "result":
                changed["answers"][0]["result"]["text"] += " tampered"
                changed["answers"][0]["binding"]["answer_sha256"] = run.panel.sha256_json(changed["answers"][0]["result"])
            elif field == "origin": changed["answers"][0]["origin"]["kind"] = "upstream_import"
            else: changed["answers"][0]["binding"]["raw_sha256"] = "f" * 64
            with patch.object(run, "verified_bank", return_value=self.bank) as actual:
                with self.assertRaisesRegex(ValueError, "raw-verified"): run.verify_bank(ROOT, changed)
                actual.assert_called_once_with(ROOT)

    def test_judge_only_schedule_has_fresh_controls_and_no_old_judgments(self):
        rows = run.schedule(ROOT)
        self.assertEqual(len(rows), 324)
        self.assertTrue(all(r["kind"] == "judge" for r in rows))
        self.assertTrue(all(r["block"] == "control" for r in rows[:36]))
        self.assertTrue(all(r["block"] == "development" and not r["repeat"] for r in rows[36:180]))
        self.assertTrue(all(r["repeat"] for r in rows[180:]))
        self.assertEqual([r["sequence"] for r in rows], list(range(1, 325)))

    def test_payloads_preserve_packets_settings_and_identical_repeats(self):
        first = {}
        for row in run.schedule(ROOT):
            context = run.request_context(ROOT, row, self.catalog, self.controls, self.answers)
            old = run.panel.request_context(ROOT, row, self.catalog, self.controls, self.answers)
            self.assertEqual(context["packet"], old["packet"])
            payload = deepcopy(context["payload"])
            payload["system_instruction"] = old["payload"]["system_instruction"]
            payload["response_format"]["schema"] = old["payload"]["response_format"]["schema"]
            self.assertEqual(payload, old["payload"])
            key = run.workflow.judgment_key({**row, "repeat": False})
            if row["repeat"]: self.assertEqual(context["payload"], first[key])
            first[key] = context["payload"]
            if row["stage"] == "initial": self.assertEqual(len(context["packet"]["transcript"]), 2)

    def test_candidate_or_modified_judge_row_is_not_supported(self):
        for row in (run.panel.candidate_rows(ROOT)[0], {**run.schedule(ROOT)[0], "model": "other"}):
            with self.assertRaises(ValueError): run.request_context(ROOT, row, self.catalog, self.controls, self.answers)

    def test_public_metadata_no_text_no_live_authority_and_all_holds(self):
        with patch.object(run, "verified_bank", return_value=self.bank), \
                patch.object(run.panel.old.prior, "read_setting", side_effect=AssertionError("credential read")), \
                patch.object(run.panel.old.prior, "create_tls_connection", side_effect=AssertionError("network")):
            value = run.readiness(ROOT, self.bank)
        self.assertEqual(value["verified_answer_stages"], 144)
        self.assertEqual(value["review_held_conversations"], 8)
        self.assertTrue(value["fresh_control_gate_required"])
        self.assertFalse(value["historical_judgments_reused"])
        self.assertFalse(value["live_execution_available"])
        self.assertEqual(value["live_call_allowance"], 0)
        self.assertIsNone(value["live_budget_usd"])
        for forbidden in ("Fixture ", "response_evidence", "rationale", '"result"', "point_score"):
            self.assertNotIn(forbidden, json.dumps(value))

    def test_tree_hash_changes_and_linked_files_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve()
            initial = run.tree_hash(path)
            (path / "empty").touch()
            self.assertNotEqual(run.tree_hash(path), initial)
            os.symlink(path / "empty", path / "link")
            with self.assertRaises(ValueError): run.tree_hash(path)

    def test_source_pin_mismatch_rejected_before_replay(self):
        with patch.object(run, "tree_hash", return_value="bad"), patch.object(run.source, "restore") as replay:
            with self.assertRaisesRegex(ValueError, "Source pin"): run.verified_bank(ROOT)
            replay.assert_not_called()

    def test_no_live_cli(self):
        result = subprocess.run([sys.executable, "-m", "scripts.judge_saved_bank_s56", "run"], cwd=ROOT, capture_output=True)
        self.assertNotEqual(result.returncode, 0)


class SealedFixtureTests(unittest.TestCase):
    def test_extract_128_new_and_16_imported_answers_from_frozen_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve() / "run"
            protocol = run.panel.sha256_json(run.live.snapshot(ROOT))
            writer = run.live.Session(ROOT, directory, imports(), protocol, "20.00", mode="offline_fixture")
            for _ in range(128):
                # Session prepares before asking the fixture connection for a response.
                def connection(host, *, timeout):
                    return run.live.rehearsal._Connection(run.live.rehearsal.Fixture(reply(writer.core), 200, {}, None))
                writer.step({"gemini": "FIXTURE", "minimax": "FIXTURE"}, connection)
            checked = run.live.replay(ROOT, directory, protocol)
            self.assertEqual(checked["answer_stages_present"], 144)
            self.assertTrue(checked["interrupted"])  # Test prefix only, never live bank admission.
            before = run.tree_hash(directory)
            records = run.records_from_verified_state(ROOT, directory, writer.core)
            self.assertEqual(len(records), 144)
            self.assertEqual(sum(r["origin"]["kind"] == "s54_candidate" for r in records), 128)
            self.assertEqual(run.tree_hash(directory), before)
            self.assertEqual(run.validate_records(ROOT, records), writer.core.answers)


if __name__ == "__main__":
    unittest.main()
