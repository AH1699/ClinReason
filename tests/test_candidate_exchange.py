import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.candidate_exchange import export_prompts, import_answers, validate_answers
from benchmark.cli import main
from benchmark.config import load_json, load_jsonl
from benchmark.db import connect
from benchmark.pipeline import bootstrap, create_run, judge_responses, report_run, score_run
from benchmark.providers.mock import MockJudgeProvider


class CandidateExchangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.config = load_json(cls.root / "config/benchmark.json")
        cls.rubric = load_json(cls.root / "config/rubric.json")
        cls.cases_path = cls.root / "data/alpha/global_core_cases.jsonl"
        cls.cases = load_jsonl(cls.cases_path)

    def _export(self, directory):
        path = Path(directory) / "prompts.jsonl"
        count = export_prompts(
            self.cases_path, path, rubric=self.rubric,
            authoring=self.config["authoring"], instruction="Answer the case only.",
            prompt_template_version=self.config["prompt_template_version"],
        )
        self.assertEqual(count, 24)
        return path

    @staticmethod
    def _write_answers(path, rows):
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )

    def test_export_is_prompt_only_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._export(directory)
            rows = load_jsonl(path)
            self.assertEqual({row["language"] for row in rows}, {"en", "zh-Hans"})
            self.assertEqual(len(rows), 24)
            self.assertEqual(
                set(rows[0]),
                {"exchange_version", "case_id", "case_version", "case_content_hash",
                 "language", "prompt_template_version", "instruction", "prompt"},
            )
            exported = path.read_text(encoding="utf-8")
            self.assertNotIn("reference_answer", exported)
            self.assertNotIn("critical_requirements", exported)
            self.assertNotIn("critical_errors", exported)
            for case in self.cases:
                self.assertNotIn(case["reference_answer"], exported)
            with self.assertRaises(FileExistsError):
                self._export(directory)

    def test_import_validates_completeness_revision_and_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [
                {key: row[key] for key in ("case_id", "case_version", "case_content_hash")}
                | {"text": "Provisional response."}
                for row in load_jsonl(self._export(directory))
            ]
            path = Path(directory) / "answers.jsonl"
            self._write_answers(path, rows)
            self.assertEqual(len(validate_answers(path, self.cases)), 24)
            for invalid in (
                rows[:-1],
                rows + [rows[0]],
                [{**rows[0], "case_content_hash": "0" * 64}] + rows[1:],
                [{**rows[0], "reference_answer": "leak"}] + rows[1:],
                [{**rows[0], "text": ""}] + rows[1:],
            ):
                self._write_answers(path, invalid)
                with self.assertRaises(ValueError):
                    validate_answers(path, self.cases)

    def test_import_and_mock_score_give_breakdowns_but_no_clinical_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt_rows = load_jsonl(self._export(directory))
            answers = [
                {
                    "case_id": row["case_id"], "case_version": row["case_version"],
                    "case_content_hash": row["case_content_hash"],
                    "text": "This is a synthetic integration-test response.",
                }
                for row in prompt_rows
            ]
            answers_path = Path(directory) / "answers.jsonl"
            self._write_answers(answers_path, answers)
            db_path = Path(directory) / "pilot.sqlite3"
            run_id = import_answers(
                db_path, self.cases_path, answers_path, config=self.config,
                rubric=self.rubric, provider="test", model_id="example-llm",
                model_version="snapshot-1",
            )
            with connect(db_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM model_responses WHERE run_id = ?", (run_id,)
                ).fetchone()[0]
            self.assertEqual(count, 24)
            self.assertEqual(
                judge_responses(db_path, run_id, [MockJudgeProvider(0), MockJudgeProvider(1)],
                                self.rubric, self.config["judge_prompt_version"]),
                48,
            )
            self.assertEqual(score_run(db_path, run_id, self.rubric, self.config["scoring"]), 24)
            report = report_run(db_path, run_id)
            self.assertEqual(report["report_status"], "experimental_unvalidated")
            self.assertEqual(report["count"], 24)
            self.assertEqual(len(report["by_model"]), 1)
            model = report["by_model"][0]
            self.assertEqual(len(model["by_category"]), 6)
            self.assertTrue(all(item["count"] == 4 for item in model["by_category"].values()))
            self.assertEqual(model["by_language"]["en"]["count"], 12)
            self.assertEqual(model["by_language"]["zh-Hans"]["count"], 12)
            self.assertIn("dimension_scores", report["cases"][0])

    def test_existing_case_version_cannot_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            original = self.cases[0]
            changed = json.loads(json.dumps(original))
            changed["prompt"] += " Meaning-changing edit."
            source = Path(directory) / "cases.jsonl"
            db_path = Path(directory) / "cases.sqlite3"
            self._write_answers(source, [original])
            bootstrap(db_path, source)
            self._write_answers(source, [changed])
            with self.assertRaises(ValueError):
                bootstrap(db_path, source)
            with connect(db_path) as conn:
                row = conn.execute("SELECT payload_json FROM cases").fetchone()
                self.assertEqual(json.loads(row["payload_json"])["prompt"], original["prompt"])
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM active_cases").fetchone()[0], 1)
            promoted = json.loads(json.dumps(original))
            promoted["status"] = "clinician_validated"
            promoted["metadata"]["clinician_validated"] = True
            self._write_answers(source, [promoted])
            run_id = create_run(db_path, self.config)
            bootstrap(db_path, source)
            with connect(db_path) as conn:
                row = conn.execute("SELECT payload_json FROM cases").fetchone()
                self.assertEqual(json.loads(row["payload_json"])["status"], "clinician_validated")
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM run_cases WHERE run_id = ?", (run_id,)).fetchone()[0],
                    1,
                )

    def test_cli_export_import_and_mock_score(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            config = dict(self.config)
            config["database_path"] = str(temporary / "cli.sqlite3")
            config["cases_path"] = str(self.cases_path)
            config["rubric_path"] = str(self.root / "config/rubric.json")
            config["candidate_prompt_path"] = str(self.root / "config/candidate_prompt.txt")
            config_path = temporary / "benchmark.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            prompts_path = temporary / "prompts.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["--config", str(config_path), "export-prompts", "--output", str(prompts_path)]),
                    0,
                )
            answers_path = temporary / "answers.jsonl"
            self._write_answers(
                answers_path,
                [
                    {
                        "case_id": row["case_id"], "case_version": row["case_version"],
                        "case_content_hash": row["case_content_hash"], "text": "Test output.",
                    }
                    for row in load_jsonl(prompts_path)
                ],
            )
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(["--config", str(config_path), "import-responses", "--input", str(answers_path),
                          "--provider", "local", "--model-id", "test", "--model-version", "1"]),
                    0,
                )
            run_id = json.loads(output.getvalue())["run_id"]
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--config", str(config_path), "score-imported-demo", run_id]), 0)
            self.assertEqual(json.loads(output.getvalue())["report_status"], "experimental_unvalidated")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--config", str(config_path), "score-imported-demo", run_id]), 2)


if __name__ == "__main__":
    unittest.main()
