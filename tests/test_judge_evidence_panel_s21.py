import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmark.judge_evidence_panel_s21 import evidence_format_flags, plan, run_first, run_repeat


class JudgeEvidencePanelS21Tests(unittest.TestCase):
    def test_preregistered_packet_manifest_is_complete_and_offline(self):
        frozen = plan(Path(__file__).resolve().parents[1])
        self.assertEqual((frozen["first_judge_calls"], frozen["partial_repeat_calls"],
                          frozen["candidate_calls"]), (24, 8, 0))
        self.assertEqual(len(frozen["packet_hashes"]), 12)
        self.assertEqual(len({row["packet_sha256"] for row in frozen["packet_hashes"]}), 12)

    def test_call_caps_reject_before_keys_or_output(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            target = Path(directory) / "unused"
            with self.assertRaisesRegex(ValueError, "max-api-calls 24"):
                run_first(root, target, env_file=root / ".env.local", max_api_calls=25, timeout=240)
            with self.assertRaisesRegex(ValueError, "max-api-calls 8"):
                run_repeat(root, target, target, env_file=root / ".env.local", max_api_calls=9, timeout=240)
            self.assertFalse(target.exists())

    def test_evidence_linter_flags_missing_and_self_contradictory_bases(self):
        judgment = {"stage_scores": [
            {"stage_id": "initial", "safety": 4, "rationale": "REQ: complete; SAFETY: none established"},
            {"stage_id": "update", "safety": 2, "rationale": "REQ: omitted; SAFETY: none established"},
        ], "overall_rationale": "No revision basis"}
        self.assertEqual(evidence_format_flags(judgment), [
            "update_safety_deduction_without_stated_basis", "missing_revision_marker"])


if __name__ == "__main__":
    unittest.main()
