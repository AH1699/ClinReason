"""Offline input isolation, version selection and finite pilot proposal checks."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark.provenance import sha256_json
from scripts import standalone_pilot_s60 as pilot

ROOT = Path(__file__).resolve().parents[1]


class StandalonePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.catalog, cls.supplement, cls.files = pilot.inputs(ROOT)
        cls.packets, cls.records = pilot.controls(ROOT, cls.catalog)
        cls.cells, cls.jobs = pilot.schedule(cls.spec, cls.records)

    def test_scope_and_counts(self):
        value = pilot.snapshot(ROOT)
        self.assertEqual(value["counts"], {"families": 8, "language_variants": 16,
            "criterion_positions": 52, "bilingual_criterion_positions": 104,
            "candidate_conversations": 64, "control_conversations": 48,
            "unique_control_stage_packets": 64,
            "proposed_requests_by_kind": {"control_first": 64, "control_repeat": 32,
                "candidate": 128, "judge_first": 128, "judge_repeat": 128},
            "proposed_total_requests": 480})
        self.assertEqual(value["strata"], {"diagnostic_restraint": 3, "competing_treatment_risks": 3,
                                          "escalation_under_uncertainty": 2})
        self.assertEqual(value["categories"], {"clinical_reasoning": 4, "triage": 2, "medication_safety": 2})
        self.assertFalse(value["execution_ready"])
        self.assertIsNone(value["paid_authorization"])
        self.assertEqual(value["numeric_scores"], 0)

    def test_newer_o_only_changes_declared_requirement(self):
        for entry in self.catalog.values():
            actual, old = deepcopy(entry["family"]), entry["original"]
            if entry["batch"] != "o":
                self.assertEqual(actual, old)
                continue
            self.assertEqual(actual["version"], "0.2.0")
            actual["version"] = old["version"]
            for lang in self.spec["languages"]:
                current = actual["variants"][lang]["turns"][1]["critical_requirements"]
                original = old["variants"][lang]["turns"][1]["critical_requirements"]
                self.assertNotEqual(current[2], original[2])
                current[2] = original[2]
            self.assertEqual(actual, old)

    def test_source_mapping_marks_two_unrevalidated_wordings(self):
        value = pilot.snapshot(ROOT)
        changed = [(f["family_id"], m["stage"], m["index"]) for f in value["families"]
                   for m in f["source_mapping"] if m["binding"].startswith("original_source")]
        self.assertEqual(set(changed), {("HC-MT-REASON-024", "update", 3), ("HC-MT-MEDSAFE-020", "update", 3)})
        self.assertEqual(len(changed), 2)
        self.assertTrue(all(not m["clinical_approval"] for f in value["families"] for m in f["source_mapping"]))

    def test_all_review_holds_retained(self):
        self.assertEqual(len(self.cells), 64)
        self.assertTrue(all(c["clinical_comparison_held"] and c["review_issues"] for c in self.cells))
        self.assertEqual({m["model"] for m in self.spec["candidate_roster_proposal"] if m["provider"] == "minimax"},
                         {"MiniMax-M3", "MiniMax-M3.1-Flash"})

    def test_no_leakage_of_future_initial_labels_or_author_fields(self):
        allowed = {"case_id", "case_content_hash", "language", "scoring_stage", "transcript", "turn_labels",
                   "criterion_anchors", "level_definitions"}
        for key, packet in self.packets.items():
            self.assertEqual(set(packet), allowed)
            stage = packet["scoring_stage"]
            self.assertEqual(len(packet["transcript"]), 2 if stage == "initial" else 4)
            self.assertEqual({t["stage_id"] for t in packet["turn_labels"]}, {stage})
            self.assertEqual({a["stage_id"] for a in packet["criterion_anchors"]}, {stage})
            if stage == "initial":
                family = self.catalog[key.split("__")[0]]["family"]
                future = family["variants"][packet["language"]]["turns"][1]
                self.assertNotIn(future["user"], json.dumps(packet, ensure_ascii=False))
                self.assertTrue(all(e["id"] not in json.dumps(packet) for e in future["critical_errors"]))
            exported = pilot.judge_input(ROOT, packet)
            self.assertEqual(set(exported), {"packet", "instruction", "schema"})
            self.assertNotIn("author_expectations", json.dumps(exported))
            self.assertNotIn("hypothesized_error_id", json.dumps(exported))
            self.assertNotIn(key, json.dumps(exported))

    def test_four_update_requirements_are_not_truncated(self):
        for key, packet in self.packets.items():
            fid = key.split("__")[0]
            expected = 4 if self.catalog[fid]["batch"] == "q" and packet["scoring_stage"] == "update" else 3
            self.assertEqual(len(packet["criterion_anchors"]), expected)
            schema = pilot.judge_input(ROOT, packet)["schema"]
            self.assertEqual(schema["properties"]["criterion_assessments"]["items"]["properties"]["requirement_index"]["maximum"], expected)

    def test_candidate_sees_visible_messages_only(self):
        for entry in self.catalog.values():
            family = entry["family"]
            for lang in self.spec["languages"]:
                turns = family["variants"][lang]["turns"]
                initial = pilot.candidate_history(family, lang, "initial")
                self.assertEqual(initial, [{"role": "user", "content": turns[0]["user"]}])
                followup = pilot.candidate_history(family, lang, "update", "validated answer supplied by this candidate")
                self.assertEqual(followup, initial + [{"role": "assistant", "content": "validated answer supplied by this candidate"},
                                                     {"role": "user", "content": turns[1]["user"]}])

    def test_candidate_update_never_fills_missing_answer_with_reference(self):
        family = next(iter(self.catalog.values()))["family"]
        for answer in (None, "", " ", 1, []):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                pilot.candidate_history(family, "en", "update", answer)
        with self.assertRaises(ValueError):
            pilot.candidate_history(family, "en", "initial", "extra answer")
        with self.assertRaises(ValueError):
            pilot.candidate_history(family, "en", "later")

    def test_repeat_control_inputs_identical(self):
        first = {r["control_key"]: r["judge_input_sha256"] for r in self.jobs if r["kind"] == "control_first"}
        repeats = [r for r in self.jobs if r["kind"] == "control_repeat"]
        self.assertEqual(len(repeats), 32)
        for row in repeats:
            self.assertEqual(row["judge_input_sha256"], first[row["control_key"]])
            self.assertTrue(row["control_key"].endswith(("__shared", "__partial")))

    def test_unique_jobs_and_same_cell_dependencies(self):
        self.assertEqual(len({r["id"] for r in self.jobs}), 480)
        seen = set()
        for row in self.jobs:
            self.assertTrue(set(row["dependencies"]).issubset(seen))
            for dependency in row["dependencies"]:
                self.assertIn(row["cell_id"], dependency)
            seen.add(row["id"])
        update = next(r for r in self.jobs if r["kind"] == "candidate" and r["stage"] == "update")
        self.assertEqual(update["dependencies"], ["candidate__" + update["cell_id"] + "__initial"])

    def test_author_status_and_numeric_targets_unset(self):
        self.assertEqual(sum(r["hypothesized_error_id"] is not None for r in self.records), 16)
        self.assertEqual(sum(r["omitted_component"] is not None for r in self.records), 16)
        self.assertTrue(all(r["expected_status"] is None and r["expected_score"] is None for r in self.records))
        self.assertFalse(self.spec["controls"]["strict_order_expected"])

    def test_supplement_is_not_counted_as_new_cases_or_paid_jobs(self):
        self.assertEqual(self.supplement["unique_blinded_packets"], 58)
        self.assertEqual(self.supplement["total_targeted_control_records"], 72)
        self.assertEqual(self.supplement["exploratory_unlabelled_records"], 8)
        self.assertEqual(self.supplement["new_families"], 0)
        self.assertEqual(len(self.records), 64)

    def test_deterministic_snapshot_with_no_network_or_credentials(self):
        with patch("socket.socket.connect", side_effect=AssertionError("No network")), \
             patch("os.getenv", side_effect=AssertionError("No environment settings")):
            first = pilot.snapshot(ROOT)
            second = pilot.snapshot(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(first["proposed_schedule_sha256"], sha256_json(self.jobs))
        self.assertFalse(any(".env" in p or p.startswith(("work/", "purchasedAssets/")) for p in first["files"]))

    def test_rejects_offline_scope_and_hold_changes(self):
        for key, value in (("live_call_allowance", 1), ("default_registry_changes", True),
                           ("private_records_included", True), ("batch_o_label_version", "original")):
            changed = deepcopy(self.spec)
            changed[key] = value
            with self.subTest(key=key), patch.object(pilot, "load_json", return_value=changed), self.assertRaises(ValueError):
                pilot.plan(ROOT)
        changed = deepcopy(self.spec)
        changed["selection"][0]["review_issues"] = []
        with patch.object(pilot, "load_json", return_value=changed), self.assertRaises(ValueError):
            pilot.plan(ROOT)

    def test_rejects_paid_budget_or_old_approval(self):
        for key, value in (("recorded_spending_stop_threshold_usd", "20"), ("approval", "old_approval"),
                           ("current_price_evidence", "old_prices"), ("automatic_retries", 1)):
            changed = deepcopy(self.spec)
            changed["prospective_cost_policy"][key] = value
            with self.subTest(key=key), patch.object(pilot, "load_json", return_value=changed), self.assertRaises(ValueError):
                pilot.plan(ROOT)

    def test_source_or_snapshot_drift_is_rejected(self):
        actual = pilot.snapshot(ROOT)
        self.assertEqual(pilot.verify(ROOT), actual)
        changed = deepcopy(actual)
        changed["families"][0]["family_sha256"] = "0" * 64
        with patch.object(pilot, "snapshot", return_value=actual), \
             patch.object(pilot, "load_json", return_value=changed), self.assertRaisesRegex(ValueError, "manifest is stale"):
            pilot.verify(ROOT)

    def test_unsafe_paths_and_links_rejected(self):
        for relative in (".env.local", "work/answers.json", "purchasedAssets/record.json", "../config/x", "/tmp/x"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                pilot.public_path(ROOT, relative)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").symlink_to(ROOT / "config", target_is_directory=True)
            with self.assertRaises(ValueError):
                pilot.public_path(root, "config/benchmark.json")

    def test_cli_has_no_live_or_write_mode(self):
        for argument in ("--live", "--approve", "--output", "--resume"):
            with self.subTest(argument=argument), patch("sys.argv", ["pilot", argument]), \
                 patch("sys.stderr"), self.assertRaises(SystemExit) as result:
                pilot.main()
            self.assertNotEqual(result.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
