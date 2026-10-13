import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json
from benchmark.difficulty_audit import audit_multiturn_difficulty, compare_multiturn_judge_passes
from benchmark.multiturn import build_judge_packet, merge_multiturn_datasets, play_variant
from benchmark.multiturn_judging import score_judgment
from benchmark.provenance import sha256_json


class FixtureCandidate:
    provider_name = "fixture"
    model_id = "fixture-candidate"
    model_version = "1"

    def reply(self, _history):
        return {"text": "Synthetic fixture answer."}


class DifficultyAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.dataset = merge_multiturn_datasets([
            load_json(root / "data/multiturn/pilot_cases.json"),
            load_json(root / "data/multiturn/batch_c_cases.json"),
        ])
        cls.rubric = load_json(root / "config/multiturn_rubric.json")

    def fixtures(self):
        family = self.dataset["families"][0]
        answers = [play_variant(family, language, FixtureCandidate()) for language in ("en", "zh-Hans")]
        judgments = []
        for language, answer in zip(("en", "zh-Hans"), answers):
            packet = build_judge_packet(family, language, answer)
            level = 4 if language == "en" else 3
            judgment = {
                "stage_scores": [
                    {"stage_id": stage, "safety": level, "requirements": level, "rationale": "Fixture."}
                    for stage in ("initial", "update")
                ],
                "revision_score": level, "critical_errors": [], "confidence": 1,
                "requires_human_review": False, "overall_rationale": "Fixture only.",
            }
            judgments.append({
                "case_id": answer["case_id"],
                "case_content_hash": answer["case_content_hash"],
                "judgment": judgment,
                "score": score_judgment(judgment, packet, self.rubric),
            })
        candidate_manifest = {
            "status": "draft_multiturn_candidate_run_no_clinical_score",
            "case_count": len(answers), "dataset_sha256": sha256_json(self.dataset),
            "provider": "fixture", "requested_model": "fixture-candidate", "returned_model": "1",
            "case_revisions": [
                {"case_id": answer["case_id"], "case_content_hash": answer["case_content_hash"]}
                for answer in answers
            ],
        }
        judge_manifest = {
            "status": "experimental_unvalidated_single_ai_judge",
            "case_count": len(judgments), "rubric_sha256": sha256_json(self.rubric),
            "provider": "fixture", "requested_model": "fixture-judge", "returned_model": "1",
            "judge_instruction_sha256": "a" * 64,
            "generated_at": "2026-10-12T01:00:00+00:00",
            "case_revisions": [
                {"case_id": row["case_id"], "case_content_hash": row["case_content_hash"]}
                for row in judgments
            ],
        }
        return answers, judgments, candidate_manifest, judge_manifest

    def test_paired_report_is_descriptive_and_contains_no_transcript(self):
        report = audit_multiturn_difficulty(self.dataset, *self.fixtures(), self.rubric)
        self.assertEqual(report["family_count"], 1)
        self.assertEqual(report["conversation_count"], 2)
        self.assertEqual(report["perfect_100_count"], 1)
        self.assertEqual(report["at_least_90_count"], 1)
        self.assertEqual(report["paired_families"][0]["absolute_gap"], 25)
        self.assertEqual(report["critical_error_counts_by_stage"], {"initial": 0, "update": 0})
        self.assertNotIn("Synthetic fixture answer", json.dumps(report))

    def test_missing_language_or_judgment_is_rejected(self):
        answers, judgments, candidate_manifest, judge_manifest = self.fixtures()
        with self.assertRaisesRegex(ValueError, "both language variants"):
            audit_multiturn_difficulty(
                self.dataset, answers[:1], judgments[:1],
                {**candidate_manifest, "case_count": 1, "case_revisions": candidate_manifest["case_revisions"][:1]},
                {**judge_manifest, "case_count": 1, "case_revisions": judge_manifest["case_revisions"][:1]},
                self.rubric,
            )
        with self.assertRaisesRegex(ValueError, "case sets differ"):
            audit_multiturn_difficulty(
                self.dataset, answers, judgments[:1], candidate_manifest, judge_manifest, self.rubric
            )

    def test_tampered_score_and_revision_are_rejected(self):
        answers, judgments, candidate_manifest, judge_manifest = self.fixtures()
        altered = deepcopy(judgments)
        altered[0]["score"]["gated_score"] = 73
        with self.assertRaisesRegex(ValueError, "recomputed score"):
            audit_multiturn_difficulty(
                self.dataset, answers, altered, candidate_manifest, judge_manifest, self.rubric
            )
        bad_manifest = {**candidate_manifest, "dataset_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "different dataset revision"):
            audit_multiturn_difficulty(
                self.dataset, answers, judgments, bad_manifest, judge_manifest, self.rubric
            )

    def test_duplicate_case_and_dry_run_selection(self):
        answers, judgments, candidate_manifest, judge_manifest = self.fixtures()
        with self.assertRaisesRegex(ValueError, "duplicate case IDs"):
            audit_multiturn_difficulty(
                self.dataset, answers + answers[:1], judgments,
                candidate_manifest, judge_manifest, self.rubric,
            )
        output = io.StringIO()
        with redirect_stdout(output):
            status = main([
                "generate-grok-multiturn", "--model", "grok-test", "--limit", "4",
                "--family-ids", "HC-MT-TRIAGE-003,HC-MT-REASON-004",
            ])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["planned_api_calls"], 8)

    def test_repeat_comparison_detects_score_change_and_rejects_prompt_change(self):
        answers, first, candidate_manifest, first_manifest = self.fixtures()
        second = deepcopy(first)
        second[0]["judgment"]["stage_scores"][0]["safety"] = 3
        family = self.dataset["families"][0]
        packet = build_judge_packet(family, "en", answers[0])
        second[0]["score"] = score_judgment(second[0]["judgment"], packet, self.rubric)
        second_manifest = {**first_manifest, "generated_at": "2026-10-12T02:00:00+00:00"}
        report = compare_multiturn_judge_passes(
            self.dataset, answers, candidate_manifest,
            first, first_manifest, second, second_manifest, self.rubric,
        )
        self.assertEqual(report["conversation_count"], 2)
        self.assertEqual(report["changed_gated_score_count"], 1)
        self.assertEqual(report["changed_initial_count"], 1)
        self.assertEqual(report["changed_update_count"], 0)
        with self.assertRaisesRegex(ValueError, "different model, instruction, or rubric"):
            compare_multiturn_judge_passes(
                self.dataset, answers, candidate_manifest,
                first, first_manifest, second,
                {**second_manifest, "judge_instruction_sha256": "b" * 64}, self.rubric,
            )

    def test_cli_can_reopen_historical_batches_after_configured_expansion(self):
        answers, first, candidate_manifest, first_manifest = self.fixtures()
        second_manifest = {**first_manifest, "generated_at": "2026-10-12T02:00:00+00:00"}
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("answers.jsonl", "first.jsonl", "second.jsonl")]
            for path, rows, manifest in zip(
                paths, (answers, first, first),
                (candidate_manifest, first_manifest, second_manifest),
            ):
                path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
                path.with_suffix(".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                status = main([
                    "compare-multiturn-judges",
                    "--cases-path", "data/multiturn/pilot_cases.json",
                    "--cases-path", "data/multiturn/batch_c_cases.json",
                    "--answers", str(paths[0]), "--first", str(paths[1]), "--second", str(paths[2]),
                ])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["changed_gated_score_count"], 0)


if __name__ == "__main__":
    unittest.main()
