import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from benchmark.judge_evidence_panel_s22 import head_check, plan, run_first, run_repeat


ROOT = Path(__file__).resolve().parents[1]


class JudgeEvidencePanelS22Tests(unittest.TestCase):
    def test_new_authorization_is_frozen_and_tracks_unknown_previous_delivery(self):
        frozen = plan(ROOT)
        self.assertEqual(frozen["maximum_additional_judge_calls"], 32)
        self.assertEqual((frozen["new_first_judge_calls"], frozen["new_partial_repeat_calls"]), (24, 8))
        self.assertEqual(frozen["prior_attempt"]["provider_receipt_or_billing"], "unknown")
        self.assertEqual(len(frozen["packets"]), 12)

    def test_keyless_head_accepts_http_reply_but_not_transport_failure(self):
        def http_404(_request, *, timeout):
            raise HTTPError("https://api.x.ai/", 404, "Not Found", {}, None)

        result = head_check("https://api.x.ai/", opener=http_404)
        self.assertEqual(result["http_status"], 404)

        def no_dns(_request, *, timeout):
            raise URLError("name resolution failed")

        with self.assertRaisesRegex(ValueError, "keyless host preflight failed"):
            head_check("https://api.x.ai/", opener=no_dns)

    def test_preflight_failure_stops_before_any_scored_call_or_output(self):
        with TemporaryDirectory(dir=ROOT / "work") as directory:
            target = Path(directory) / "s22"
            def fail_check(_url, *, timeout):
                raise ValueError("offline")
            with patch("benchmark.judge_evidence_panel_s22.base.run_first") as scored:
                with self.assertRaisesRegex(ValueError, "offline"):
                    run_first(ROOT, target, env_file=ROOT / ".env.local",
                              max_api_calls=24, timeout=60, checker=fail_check)
                scored.assert_not_called()
            self.assertFalse(target.exists())

    def test_call_caps_reject_before_preflight(self):
        with TemporaryDirectory(dir=ROOT / "work") as directory:
            target = Path(directory) / "s22"
            with self.assertRaisesRegex(ValueError, "exactly 24"):
                run_first(ROOT, target, env_file=ROOT / ".env.local",
                          max_api_calls=25, timeout=60)
            with self.assertRaisesRegex(ValueError, "exactly 8"):
                run_repeat(ROOT, target, env_file=ROOT / ".env.local",
                           max_api_calls=9, timeout=60)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
