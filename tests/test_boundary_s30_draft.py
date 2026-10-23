import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.boundary_s30_draft import audit, build_packets, inputs

ROOT = Path(__file__).resolve().parents[1]


class S30DraftTests(unittest.TestCase):
    def setUp(self):
        self.data, self.old, self.anchors, self.probes, self.fixtures = inputs(ROOT)

    def build(self):
        return build_packets(self.data, self.old, self.anchors, self.probes, self.fixtures)

    def test_offline_scope_and_blinding(self):
        report = audit(ROOT)
        self.assertEqual(report["packet_count"], 10)
        self.assertEqual(report["author_hypothesis_packets"], 8)
        self.assertEqual(report["exploratory_packets"], 2)
        self.assertEqual(report["prospective_first_calls"] + report["prospective_repeat_calls"], 24)
        self.assertEqual(report["judge_calls"], 0)
        self.assertFalse(report["live_runner_implemented"])
        packets, expected, repeats = self.build()
        self.assertEqual(len(repeats), 2)
        self.assertEqual(len(set(report["packet_hashes"].values())), 10)
        for key, packet in packets.items():
            self.assertEqual(set(packet), {"case_id", "case_content_hash", "language", "transcript",
                                           "target_requirements", "level_definitions"})
            self.assertEqual([r["requirement_index"] for r in packet["target_requirements"]], [1, 3])
            self.assertEqual(len(packet["transcript"]), 4)
            self.assertEqual(expected[key] is None, key.startswith("ambiguous_reference"))

    def test_only_two_declared_criterion_changes(self):
        before = deepcopy(self.old)
        self.build()
        self.assertEqual(self.old, before)
        self.anchors["families"][0]["stages"]["initial"][0]["met"] += " altered"
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            self.build()

    def test_exact_case_hash_and_historical_partial(self):
        self.data["families"][0]["variants"]["en"]["turns"][0]["user"] += " altered"
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.build()
        self.setUp()
        self.fixtures["fixtures"][1]["update_responses"]["en"] += " new warning"
        with self.assertRaisesRegex(ValueError, "Historical control"):
            self.build()

    def test_missing_language_duplicate_profile_and_scoped_repeats(self):
        self.fixtures["fixtures"][0]["update_responses"].pop("zh-Hans")
        with self.assertRaisesRegex(ValueError, "paired"):
            self.build()
        self.setUp()
        self.fixtures["fixtures"][-1] = deepcopy(self.fixtures["fixtures"][0])
        with self.assertRaisesRegex(ValueError, "scope"):
            self.build()
        self.setUp()
        self.fixtures["repeat_profiles"].append("complete")
        with self.assertRaisesRegex(ValueError, "scope"):
            self.build()

    def test_exploratory_answer_has_no_posthoc_expected_status(self):
        self.fixtures["fixtures"][-1]["expected_statuses"] = ["partial", "missed"]
        with self.assertRaisesRegex(ValueError, "hypothesis"):
            self.build()


if __name__ == "__main__":
    unittest.main()
