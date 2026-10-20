import json
import random
import tempfile
import unittest
from pathlib import Path

from benchmark.calibration_review_packets import (
    build_calibration_review_handoff,
    export_calibration_review_handoff,
)
from benchmark.provenance import sha256_json, sha256_text


class CalibrationReviewPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_blind_phase_hides_author_intent_and_key_is_separate(self):
        handoff = build_calibration_review_handoff(self.root, rng=random.Random(17))
        phase_a = handoff["phase_a_files"]
        phase_b = handoff["phase_b_files"]
        key = json.loads(handoff["internal_files"]["blinding_key.json"])
        self.assertEqual(handoff["phase_a_manifest"]["item_count"], 10)
        self.assertEqual(handoff["phase_a_manifest"]["language_variant_count"], 20)
        self.assertEqual(len([name for name in phase_a if name.endswith(".md") and name != "README.md"]), 10)
        self.assertEqual(len([name for name in phase_b if name.endswith(".md") and name != "README.md"]), 10)
        self.assertEqual(len(key["items"]), 10)
        self.assertEqual(key["phase_a_manifest_sha256"], sha256_json(handoff["phase_a_manifest"]))
        blind_text = "\n".join(phase_a.values())
        for forbidden in (
            "HC-MT-", "https://", "case_content_hash", "critical_requirements",
            "critical_errors", "strong_update_response", "partial_update_response",
            "unsafe_update_response", "option_roles_author_intended_not_ground_truth",
        ):
            self.assertNotIn(forbidden, blind_text)
        self.assertIn("HC-MT-", "\n".join(phase_b.values()))
        for item in key["items"]:
            self.assertEqual(set(item["option_roles_author_intended_not_ground_truth"].values()),
                             {"strong", "partial", "unsafe"})
            packet = phase_a[item["item_id"] + ".md"]
            self.assertEqual(packet.count("### Update option A"), 2)
            self.assertEqual(packet.count("### Update option B"), 2)
            self.assertEqual(packet.count("### Update option C"), 2)
        for entry in handoff["phase_a_manifest"]["items"]:
            self.assertEqual(entry["sha256"], sha256_text(phase_a[entry["file"]]))

    def test_export_is_local_separate_and_refuses_overwrite_or_nested_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            phase_a = base / "phase_a"
            phase_b = base / "phase_b"
            internal = base / "internal"
            result = export_calibration_review_handoff(
                self.root, phase_a, phase_b, internal, rng=random.Random(4)
            )
            self.assertEqual((result["item_count"], result["language_variant_count"]), (10, 20))
            self.assertTrue((phase_a / "rating_template.json").exists())
            self.assertTrue((phase_b / "criterion_template.json").exists())
            self.assertFalse((phase_a / "blinding_key.json").exists())
            self.assertFalse((phase_b / "blinding_key.json").exists())
            self.assertTrue((internal / "blinding_key.json").exists())
            self.assertEqual(phase_a.stat().st_mode & 0o777, 0o700)
            self.assertEqual(phase_b.stat().st_mode & 0o777, 0o700)
            self.assertEqual(internal.stat().st_mode & 0o777, 0o700)
            self.assertEqual((phase_a / "manifest.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((phase_b / "criterion_template.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((internal / "blinding_key.json").stat().st_mode & 0o777, 0o600)
            rating = json.loads((phase_a / "rating_template.json").read_text(encoding="utf-8"))
            self.assertEqual(rating["status"], "blank_not_submitted_not_approval")
            self.assertIsNone(rating["reviewer"]["conflict_disclosed"])
            self.assertIsNone(rating["locked_at_utc"])
            self.assertEqual(len(rating["items"]), 10)
            criteria = json.loads((phase_b / "criterion_template.json").read_text(encoding="utf-8"))
            self.assertEqual(criteria["status"], "blank_not_submitted_not_approval")
            self.assertEqual(set(criteria["items"][0]["criteria_decisions"]), {"en", "zh-Hans"})
            self.assertEqual(set(criteria["items"][0]["critical_error_decisions"]), {"en", "zh-Hans"})
            for language in ("en", "zh-Hans"):
                for stage in ("initial", "update"):
                    self.assertTrue(criteria["items"][0]["criteria_decisions"][language][stage])
                    self.assertTrue(criteria["items"][0]["critical_error_decisions"][language][stage])
            with self.assertRaises(FileExistsError):
                export_calibration_review_handoff(self.root, phase_a, phase_b, internal)
            with self.assertRaisesRegex(ValueError, "separate, non-nested"):
                export_calibration_review_handoff(
                    self.root, base / "new_phase_a", base / "new_phase_a/phase_b", base / "new_key"
                )

    def test_refuses_tracked_repository_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with self.assertRaisesRegex(ValueError, "ignored work"):
                export_calibration_review_handoff(
                    self.root, self.root / "data/calibration/packet_output",
                    base / "phase_b", base / "internal",
                )


if __name__ == "__main__":
    unittest.main()
