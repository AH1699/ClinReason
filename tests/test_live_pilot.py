import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.candidate_exchange import import_answers, validate_answers
from benchmark.cli import main
from benchmark.config import load_json, load_jsonl
from benchmark.live_judging import judge_imported_grok
from benchmark.local_settings import read_setting
from benchmark.providers.gemini_judge import validate_judgment
from benchmark.providers.grok import candidate_rows, run_grok
from benchmark.providers.http_json import ProviderRequestError


class LivePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.config = load_json(cls.root / "config/benchmark.json")
        cls.rubric = load_json(cls.root / "config/rubric.json")
        cls.cases_path = cls.root / "data/alpha/global_core_cases.jsonl"
        cls.cases = load_jsonl(cls.cases_path)
        cls.rows = candidate_rows(
            cls.cases_path, rubric=cls.rubric, authoring=cls.config["authoring"],
            instruction="Answer the synthetic case.",
            prompt_template_version=cls.config["prompt_template_version"],
        )

    def test_settings_support_two_keys_and_model_names_without_executing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.local"
            path.write_text(
                "GROK_API_KEY=grok-test-key\nGROK_MODEL=grok-test\n"
                "GEMINI_API_KEY=gemini-test-key\nGEMINI_JUDGE_MODEL=gemini-test\n",
                encoding="utf-8",
            )
            self.assertEqual(read_setting(path, "GROK_MODEL", environ={}), "grok-test")
            self.assertEqual(read_setting(path, "GEMINI_JUDGE_MODEL", environ={}), "gemini-test")
            self.assertEqual(read_setting(path, "GROK_API_KEY", environ={}, secret=True), "grok-test-key")
            path.write_text("GROK_MODEL=$(echo bad)\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_setting(path, "GROK_MODEL", environ={})

    def test_mocked_grok_to_gemini_to_score_workflow(self):
        grok_calls = []

        def grok_transport(endpoint, payload, **kwargs):
            grok_calls.append((endpoint, payload, kwargs))
            self.assertEqual(set(payload), {"model", "input", "store"})
            self.assertFalse(payload["store"])
            self.assertNotIn("reference_answer", json.dumps(payload))
            return ({"status": "completed", "model": "grok-test",
                     "output": [{"type": "message", "content": [
                         {"type": "output_text", "text": "Synthetic test response."}]}]}, 12)

        judge_calls = []

        def judge_transport(endpoint, payload, **kwargs):
            judge_calls.append((endpoint, payload, kwargs))
            self.assertFalse(payload["store"])
            self.assertIn("draft_reference_answer", payload["input"])
            self.assertNotIn("grok-test", payload["input"])
            case_view = json.loads(payload["input"])
            scores = {}
            for dimension in self.rubric["dimensions"]:
                name = dimension["id"]
                applicable = name in case_view["applicable_dimensions"]
                scores[name] = {"score": 2 if applicable else None,
                                "applicable": applicable, "rationale": "Provisional test judgment.",
                                "evidence": []}
            judgment = {"dimension_scores": scores, "critical_errors": [],
                        "overall_rationale": "Mocked transport, not clinical review.",
                        "confidence": 0.4, "requires_human_review": True}
            return ({"status": "completed", "model": "gemini-test",
                     "steps": [{"type": "model_output", "content": [
                         {"type": "text", "text": json.dumps(judgment)}]}]}, 20)

        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            answers_path = tmp / "candidate_grok_answers.jsonl"
            manifest = run_grok(
                self.rows, answers_path, model="grok-test", api_key="grok-test-key",
                limit=24, transport=grok_transport,
            )
            self.assertEqual(len(grok_calls), 24)
            self.assertEqual(len(validate_answers(answers_path, self.cases)), 24)
            self.assertEqual(manifest["returned_model"], "grok-test")
            db_path = tmp / "pilot.sqlite3"
            run_id = import_answers(
                db_path, self.cases_path, answers_path, config=self.config,
                rubric=self.rubric, provider="xai-grok", model_id="grok-test",
                model_version=manifest["returned_model"],
            )
            temp_config = dict(self.config)
            temp_config["database_path"] = str(db_path)
            temp_config["cases_path"] = str(self.cases_path)
            temp_config["rubric_path"] = str(self.root / "config/rubric.json")
            config_path = tmp / "benchmark.json"
            config_path.write_text(json.dumps(temp_config), encoding="utf-8")
            dry_output = io.StringIO()
            with redirect_stdout(dry_output):
                status = main(["--config", str(config_path), "judge-imported-gemini",
                               run_id, "--model", "gemini-test"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(dry_output.getvalue())["status"], "dry_run_no_api_calls")
            common = {
                "model": "gemini-test", "api_key": "gemini-test-key",
                "instruction": "Provisional AI judge.", "rubric": self.rubric,
                "judge_prompt_version": self.config["judge_prompt_version"],
                "scoring": self.config["scoring"], "transport": judge_transport,
            }
            smoke = judge_imported_grok(db_path, run_id, limit=1, **common)
            self.assertEqual(smoke["remaining_unjudged"], 23)
            self.assertNotIn("report", smoke)
            full = judge_imported_grok(db_path, run_id, limit=24, **common)
            self.assertEqual(len(judge_calls), 24)
            self.assertEqual(full["remaining_unjudged"], 0)
            self.assertEqual(full["report"]["count"], 24)
            self.assertEqual(full["report"]["report_status"], "experimental_unvalidated")

    def test_invalid_judgment_cannot_invent_critical_error(self):
        case = self.cases[0]
        output = {
            "dimension_scores": {
                dim["id"]: {"score": 2, "applicable": True,
                            "rationale": "Test", "evidence": []}
                for dim in self.rubric["dimensions"]
            },
            "critical_errors": [{"error_id": "INVENTED", "severity": 3,
                                 "rationale": "Test"}],
            "overall_rationale": "Test", "confidence": 0.5,
            "requires_human_review": False,
        }
        with self.assertRaises(ProviderRequestError):
            validate_judgment(output, case, self.rubric)


if __name__ == "__main__":
    unittest.main()
