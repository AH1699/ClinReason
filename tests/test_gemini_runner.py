import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from benchmark.candidate_exchange import validate_answers
from benchmark.cli import main
from benchmark.config import load_json, load_jsonl
from benchmark.providers.gemini import GeminiRunError, candidate_rows, local_api_key, run_gemini


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class GeminiRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        config = load_json(root / "config/benchmark.json")
        cls.cases = load_jsonl(root / "data/alpha/global_core_cases.jsonl")
        cls.rows = candidate_rows(
            root / "data/alpha/global_core_cases.jsonl",
            rubric=load_json(root / "config/rubric.json"),
            authoring=config["authoring"],
            instruction=(root / "config/candidate_prompt.txt").read_text(encoding="utf-8").strip(),
            prompt_template_version=config["prompt_template_version"],
        )

    def test_local_key_is_literal_and_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.local"
            path.write_text("# local only\nGEMINI_API_KEY='secret-test-value'\n", encoding="utf-8")
            self.assertEqual(local_api_key(path, {}), "secret-test-value")
            self.assertEqual(local_api_key(path, {"GEMINI_API_KEY": "environment-value"}), "environment-value")
            path.write_text("GEMINI_API_KEY=one\nGEMINI_API_KEY=two\n", encoding="utf-8")
            with self.assertRaises(GeminiRunError):
                local_api_key(path, {})
            path.write_text("GEMINI_API_KEY=$(echo danger)\nOTHER=1\n", encoding="utf-8")
            with self.assertRaises(GeminiRunError):
                local_api_key(path, {})

    def test_local_key_allows_spaces_around_equals_without_executing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.local"
            path.write_text("GEMINI_API_KEY = fixture-key\nMINIMAX_API_KEY = fixture-minimax\n",
                            encoding="utf-8")
            self.assertEqual(local_api_key(path, {}), "fixture-key")

    def test_request_contains_only_instruction_prompt_and_store_false(self):
        seen = []

        def opener(request, *, timeout):
            self.assertEqual(timeout, 17)
            payload = json.loads(request.data)
            seen.append(payload)
            self.assertEqual(set(payload), {"model", "system_instruction", "input", "store"})
            self.assertFalse(payload["store"])
            self.assertEqual(payload["system_instruction"], self.rows[0]["instruction"])
            self.assertEqual(payload["input"], self.rows[0]["prompt"])
            self.assertEqual(request.get_header("X-goog-api-key"), "secret-test-value")
            return _Response(json.dumps({
                "model": "gemini-test-snapshot", "status": "completed",
                "steps": [{"type": "model_output", "content": [{"type": "text", "text": "A real model answer."}]}],
                "usage": {"total_input_tokens": 15, "total_output_tokens": 7, "total_tokens": 22},
            }).encode())

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate_gemini_answers.jsonl"
            result = run_gemini(
                self.rows, output, model="gemini-test-snapshot", api_key="secret-test-value",
                limit=1, timeout=17, opener=opener,
            )
            answers = load_jsonl(output)
            self.assertEqual(len(seen), 1)
            self.assertEqual(len(answers), 1)
            self.assertEqual(answers[0]["case_content_hash"], self.rows[0]["case_content_hash"])
            self.assertEqual(answers[0]["text"], "A real model answer.")
            self.assertEqual(answers[0]["token_usage"]["total_tokens"], 22)
            self.assertEqual(result["returned_model"], "gemini-test-snapshot")
            self.assertEqual(result["actual_request_parameters"], {"store": False})
            self.assertEqual(result["sampling_policy"], "provider_default_unpinned")
            self.assertEqual(len(result["candidate_instruction_sha256"]), 64)
            self.assertEqual(len(result["candidate_visible_inputs_sha256"]), 64)
            self.assertNotIn("secret-test-value", output.read_text())
            self.assertNotIn("secret-test-value", Path(result["manifest"]).read_text())
            self.assertNotIn("reference_answer", json.dumps(seen))
            with self.assertRaises(FileExistsError):
                run_gemini(self.rows, output, model="gemini-test-snapshot", api_key="secret-test-value", opener=opener)

    def test_http_retry_and_failure_do_not_write_output_or_error_body(self):
        attempts = 0

        def opener(_request, *, timeout):
            nonlocal attempts
            attempts += 1
            raise HTTPError("https://example.invalid", 429, "secret-test-value", {}, io.BytesIO(b"secret-test-value"))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate_gemini_answers.jsonl"
            with self.assertRaises(GeminiRunError) as raised:
                run_gemini(self.rows, output, model="gemini-test", api_key="secret-test-value",
                           opener=opener, sleeper=lambda _seconds: None)
            self.assertEqual(attempts, 3)
            self.assertNotIn("secret-test-value", str(raised.exception))
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".manifest.json").exists())

    def test_incomplete_response_fails_without_output(self):
        def opener(_request, *, timeout):
            return _Response(json.dumps({"status": "incomplete", "model": "gemini-test"}).encode())

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate_gemini_answers.jsonl"
            with self.assertRaises(GeminiRunError):
                run_gemini(self.rows, output, model="gemini-test", api_key="secret", opener=opener)
            self.assertFalse(output.exists())

    def test_full_mocked_run_has_all_case_revisions_for_import(self):
        def opener(_request, *, timeout):
            return _Response(json.dumps({
                "status": "completed", "model": "gemini-test-snapshot",
                "steps": [{"type": "model_output", "content": [{"type": "text", "text": "A test answer."}]}],
            }).encode())

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate_gemini_answers.jsonl"
            result = run_gemini(
                self.rows, output, model="gemini-test-snapshot", api_key="test-key",
                limit=len(self.rows), opener=opener,
            )
            answers = load_jsonl(output)
            self.assertEqual(len(answers), 64)
            self.assertEqual(len(validate_answers(output, self.cases)), 64)
            self.assertEqual({row["case_id"] for row in answers}, {row["case_id"] for row in self.rows})
            self.assertEqual(result["case_count"], 64)
            self.assertEqual(len(result["case_revisions"]), 64)

    def test_cli_dry_run_makes_no_network_call_or_key_read(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate_gemini_answers.jsonl"
            stdout = io.StringIO()
            with patch("benchmark.providers.gemini.urlopen", side_effect=AssertionError("network called")):
                with redirect_stdout(stdout):
                    status = main(["generate-gemini", "--model", "gemini-test", "--output", str(output)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "dry_run_no_api_calls")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
