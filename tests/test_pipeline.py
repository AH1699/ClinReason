import tempfile
import unittest
from pathlib import Path

from benchmark.config import load_json
from benchmark.pipeline import (
    bootstrap,
    create_run,
    generate_responses,
    judge_responses,
    report_run,
    score_run,
)
from benchmark.providers.mock import MockCandidateProvider, MockJudgeProvider


class PipelineTests(unittest.TestCase):
    def test_end_to_end_offline_pipeline(self):
        root = Path(__file__).resolve().parents[1]
        config = load_json(root / "config" / "benchmark.json")
        rubric = load_json(root / "config" / "rubric.json")
        cases = root / "data" / "examples" / "healthcare_cases.jsonl"

        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite3"
            self.assertEqual(bootstrap(db_path, cases), 6)
            run_id = create_run(db_path, config)
            self.assertEqual(
                generate_responses(db_path, run_id, MockCandidateProvider(), "test-prompt"),
                6,
            )
            self.assertEqual(
                judge_responses(
                    db_path,
                    run_id,
                    [MockJudgeProvider(0), MockJudgeProvider(1)],
                    rubric,
                    "test-judge-prompt",
                ),
                12,
            )
            self.assertEqual(score_run(db_path, run_id, rubric, config["scoring"]), 6)
            report = report_run(db_path, run_id)
            self.assertEqual(report["count"], 6)
            self.assertEqual(len(report["cases"]), 6)

    def test_run_uses_its_dataset_snapshot_after_active_dataset_changes(self):
        root = Path(__file__).resolve().parents[1]
        config = load_json(root / "config" / "benchmark.json")
        examples = root / "data" / "examples" / "healthcare_cases.jsonl"
        alpha = root / "data" / "alpha" / "global_core_cases.jsonl"

        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.sqlite3"
            self.assertEqual(bootstrap(db_path, examples), 6)
            examples_run = create_run(db_path, config)
            self.assertEqual(bootstrap(db_path, alpha), 24)
            alpha_run = create_run(db_path, config)

            self.assertEqual(
                generate_responses(
                    db_path, examples_run, MockCandidateProvider(), "test-prompt"
                ),
                6,
            )
            self.assertEqual(
                generate_responses(
                    db_path, alpha_run, MockCandidateProvider(), "test-prompt"
                ),
                24,
            )


if __name__ == "__main__":
    unittest.main()
