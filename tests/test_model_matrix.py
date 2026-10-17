import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmark.cli import main
from benchmark.config import load_json
from benchmark.model_matrix import compare_matrix_reports, prepare_matrix, run_matrix
from benchmark.multiturn import merge_multiturn_datasets
from benchmark.providers.http_json import ProviderRequestError
from benchmark.providers.minimax_conversation import MiniMaxConversationProvider


class FixtureCandidate:
    provider_name = "fixture"

    def __init__(self, *, model, api_key, instruction, timeout, retries):
        assert api_key == "fixture-secret"
        self.model_id = model
        self.model_version = model

    def reply(self, history):
        return {"text": f"Fixture answer for {len(history)} visible turns."}


class FixtureJudge:
    provider_name = "fixture"

    def __init__(self, *, model, api_key, instruction, timeout, retries):
        assert api_key == "fixture-secret"
        self.model_id = model
        self.model_version = model

    def evaluate(self, packet):
        assert "candidate_id" not in packet
        assert "model_id" not in packet
        return {
            "stage_scores": [
                {"stage_id": stage, "safety": 4, "requirements": 4, "rationale": "Fixture."}
                for stage in ("initial", "update")
            ],
            "revision_score": 4, "critical_errors": [], "confidence": 0.8,
            "requires_human_review": False, "overall_rationale": "Fixture only.",
        }


class ModelMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.roster = load_json(root / "config/model_matrix.json")
        cls.dataset = merge_multiturn_datasets([
            load_json(root / f"data/multiturn/{name}")
            for name in ("pilot_cases.json", "batch_c_cases.json", "batch_d_cases.json", "batch_e_cases.json")
        ])
        cls.rubric = load_json(root / "config/multiturn_rubric.json")

    def test_roster_plan_has_seven_candidates_two_judges_and_fixed_hashes(self):
        plan, selected, candidates, judges = prepare_matrix(self.roster, self.dataset)
        self.assertEqual((len(candidates), len(judges), len(selected)), (7, 2, 2))
        self.assertEqual((plan["candidate_calls"], plan["judge_calls"], plan["total_api_calls"]),
                         (28, 28, 56))
        self.assertEqual(len({item["case_content_hash"] for item in plan["case_revisions"]}), 2)
        one, _, candidates, _ = prepare_matrix(
            self.roster, self.dataset, candidate_id="minimax-m27", case_id="HC-MT-TRIAGE-008-EN"
        )
        self.assertEqual(one["total_api_calls"], 4)
        self.assertEqual(candidates[0]["model"], "MiniMax-M2.7")
        panel, _, _, _ = prepare_matrix(
            self.roster, self.dataset, candidate_id="minimax-m27",
            selected_case_ids=["HC-MT-TRIAGE-003-EN", "HC-MT-MEDSAFE-003-EN",
                               "HC-MT-REASON-004-EN"],
        )
        self.assertEqual(panel["total_api_calls"], 12)

    def test_invalid_roster_and_unknown_case_rejected(self):
        roster = deepcopy(self.roster)
        roster["judges"][1]["provider"] = "gemini"
        with self.assertRaises(ValueError):
            prepare_matrix(roster, self.dataset)
        with self.assertRaises(ValueError):
            prepare_matrix(self.roster, self.dataset, case_id="unknown")
        with self.assertRaises(ValueError):
            prepare_matrix(self.roster, self.dataset, selected_case_ids=["HC-MT-TRIAGE-008-EN"] * 2)

    def test_cli_dry_run_never_reads_keys_or_calls_network(self):
        output = io.StringIO()
        with patch("benchmark.model_matrix.read_setting", side_effect=AssertionError("key read")):
            with redirect_stdout(output):
                status = main(["model-matrix", "--candidate-id", "minimax-m3",
                               "--case-id", "HC-MT-TRIAGE-008-EN"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["total_api_calls"], 4)

    def test_minimax_adapter_sends_visible_history_only(self):
        payloads = []

        def transport(endpoint, payload, **kwargs):
            payloads.append(payload)
            self.assertEqual(endpoint, "https://api.minimax.io/v1/chat/completions")
            self.assertEqual(kwargs["auth_header"], "Authorization")
            self.assertEqual(kwargs["retries"], 0)
            self.assertNotIn("critical_requirements", json.dumps(payload))
            return ({"model": "MiniMax-M2.7", "choices": [
                {"message": {"content": "Synthetic answer"}, "finish_reason": "stop"}
            ], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                     "base_resp": {"status_code": 0}}, 7)

        provider = MiniMaxConversationProvider(
            model="MiniMax-M2.7", api_key="fixture-secret", instruction="Respond.",
            transport=transport,
        )
        first = provider.reply([{"role": "user", "content": "Question"}])
        second = provider.reply([
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": first["text"]},
            {"role": "user", "content": "Update"},
        ])
        self.assertEqual([len(item["messages"]) for item in payloads], [2, 4])
        self.assertEqual(second["token_usage"]["total_tokens"], 15)
        self.assertEqual(provider.model_version, "MiniMax-M2.7")
        with self.assertRaises(ValueError):
            provider.reply([{"role": "assistant", "content": "Not a first user turn"}])

    def test_mocked_live_run_has_separate_judges_and_no_secret(self):
        plan, selected, candidates, judges = prepare_matrix(
            self.roster, self.dataset, candidate_id="minimax-m27", case_id="HC-MT-TRIAGE-008-EN"
        )
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "matrix"
            with patch("benchmark.model_matrix.read_setting", return_value="fixture-secret"), \
                 patch.dict("benchmark.model_matrix.CANDIDATES", {"minimax": FixtureCandidate}), \
                 patch.dict("benchmark.model_matrix.JUDGES", {"gemini": FixtureJudge, "grok": FixtureJudge}):
                with self.assertRaises(ValueError):
                    run_matrix(plan, selected, candidates, judges, self.dataset, self.rubric,
                               output_dir=output_dir, env_file="ignored", candidate_instruction="Respond.",
                               judge_instruction="Judge.", max_api_calls=3)
                self.assertFalse(output_dir.exists())
                result = run_matrix(plan, selected, candidates, judges, self.dataset, self.rubric,
                                    output_dir=output_dir, env_file="ignored", candidate_instruction="Respond.",
                                    judge_instruction="Judge.", max_api_calls=4)
            report = load_json(result["report"])
            self.assertEqual(result["api_calls"], 4)
            self.assertEqual(len(report["results"][0]["judges"]), 2)
            self.assertEqual(report["results"][0]["judge_score_gap"], 0)
            self.assertTrue(all(judge["review_required"] for judge in report["results"][0]["judges"]))
            self.assertNotIn("fixture-secret", "".join(path.read_text() for path in output_dir.iterdir()))
            with self.assertRaises(FileExistsError):
                run_matrix(plan, selected, candidates, judges, self.dataset, self.rubric,
                           output_dir=output_dir, env_file="ignored", candidate_instruction="Respond.",
                           judge_instruction="Judge.", max_api_calls=4)

    def test_minimax_rejects_unreadable_provider_response(self):
        provider = MiniMaxConversationProvider(
            model="MiniMax-M2.7", api_key="fixture-secret", instruction="Respond.",
            transport=lambda *_args, **_kwargs: ({"model": "MiniMax-M2.7", "choices": []}, 1),
        )
        with self.assertRaises(ProviderRequestError):
            provider.reply([{"role": "user", "content": "Question"}])

    def test_minimax_rejects_truncated_response(self):
        provider = MiniMaxConversationProvider(
            model="MiniMax-M2.7", api_key="fixture-secret", instruction="Respond.",
            transport=lambda *_args, **_kwargs: ({
                "model": "MiniMax-M2.7", "choices": [
                    {"message": {"content": "Partial"}, "finish_reason": "length"}
                ]}, 1),
        )
        with self.assertRaises(ProviderRequestError):
            provider.reply([{"role": "user", "content": "Question"}])

    def test_comparison_requires_identical_cases_and_judges(self):
        base = {
            "status": "experimental_unvalidated_two_ai_judges_not_clinical_ranking",
            "roster_sha256": "roster", "dataset_sha256": "dataset",
            "candidate_instruction_sha256": "candidate-prompt",
            "judge_instruction_sha256": "judge-prompt", "rubric_sha256": "rubric",
            "results": [{
                "candidate_id": "one", "candidate_provider": "grok",
                "candidate_model_requested": "grok-one", "candidate_model_returned": "grok-one",
                "case_id": "case-one", "case_content_hash": "case-hash",
                "judge_score_gap": 10,
                "judges": [
                    {"provider": "gemini", "model_requested": "gemini-judge",
                     "model_returned": "gemini-judge", "gated_score": 90},
                    {"provider": "grok", "model_requested": "grok-judge",
                     "model_returned": "grok-judge", "gated_score": 100},
                ],
            }],
        }
        second = deepcopy(base)
        second["results"][0]["candidate_id"] = "two"
        second["results"][0]["candidate_model_requested"] = "grok-two"
        second["results"][0]["candidate_model_returned"] = "grok-two"
        result = compare_matrix_reports([base, second])
        self.assertEqual(len(result["candidate_results"]), 2)
        self.assertEqual(result["candidate_results"][0]["cases"][0]["judge_scores"],
                         {"gemini": 90, "grok": 100})
        corrupted = deepcopy(second)
        corrupted["results"][0]["case_content_hash"] = "stale"
        with self.assertRaises(ValueError):
            compare_matrix_reports([base, corrupted])
        corrupted = deepcopy(second)
        corrupted["results"][0]["judges"][1]["model_returned"] = "moving-alias"
        with self.assertRaises(ValueError):
            compare_matrix_reports([base, corrupted])
        with self.assertRaises(ValueError):
            compare_matrix_reports([base, base])


if __name__ == "__main__":
    unittest.main()
