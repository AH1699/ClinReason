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
from benchmark.criterion_anchors import attach_anchors, validate_anchor_set
from benchmark.model_matrix import (assemble_matrix_artifacts, audit_matrix_report, compare_matrix_reports,
                                    judge_saved_matrix_answer, prepare_matrix, run_anchored_contrast, run_matrix)
from benchmark.multiturn import build_judge_packet, merge_multiturn_datasets, variant_id
from benchmark.multiturn_judging import score_judgment, validate_judgment
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


class FixtureCriterionJudge(FixtureJudge):
    def evaluate(self, packet):
        result = super().evaluate(packet)
        partial = self.model_id == "grok-4.7"
        result["criterion_assessments"] = [
            {"stage_id": anchor["stage_id"], "requirement_index": anchor["requirement_index"],
             "status": "partial" if partial and index == 0 else "met",
             "response_evidence": "Fixture answer", "rationale": "Fixture evidence."}
            for index, anchor in enumerate(packet["criterion_anchors"])
        ]
        if partial:
            result["stage_scores"][0]["requirements"] = 3
        return result


class FixtureContrastCriterionJudge(FixtureCriterionJudge):
    def evaluate(self, packet):
        result = FixtureJudge.evaluate(self, packet)
        update = packet["transcript"][3]["content"]
        variant = "unsafe" if "definitively rules out" in update else (
            "partial" if "Discuss it with your clinician" in update else "safe"
        )
        result["criterion_assessments"] = []
        for anchor in packet["criterion_anchors"]:
            stage = anchor["stage_id"]
            status = "met" if stage == "initial" or variant == "safe" else (
                "partial" if variant == "partial" else "missed"
            )
            text = packet["transcript"][1 if stage == "initial" else 3]["content"]
            result["criterion_assessments"].append({
                "stage_id": stage, "requirement_index": anchor["requirement_index"],
                "status": status, "response_evidence": text[:10] if status in {"met", "partial"} else "",
                "rationale": "Fixture only.",
            })
        if variant == "partial":
            result["stage_scores"][1]["requirements"] = 2
            result["revision_score"] = 3
        elif variant == "unsafe":
            result["stage_scores"][1]["requirements"] = 0
            result["stage_scores"][1]["safety"] = 0
            result["revision_score"] = 0
            error = packet["turn_labels"][1]["critical_errors"][0]
            result["critical_errors"] = [{"stage_id": "update", "error_id": error["id"],
                                          "severity": error["severity"], "rationale": "Fixture unsafe."}]
        return result


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
        cls.anchors = load_json(root / "config/multiturn_criterion_anchors_v1.json")

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
        output = io.StringIO()
        with patch("benchmark.model_matrix.read_setting", side_effect=AssertionError("key read")):
            with redirect_stdout(output):
                status = main(["judge-anchored-contrast", "--output-dir", "work/not-created-by-dry-run"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["judge_calls"], 6)

    def test_minimax_adapter_sends_visible_history_only(self):
        payloads = []

        def transport(endpoint, payload, **kwargs):
            payloads.append(payload)
            self.assertEqual(endpoint, "https://api.minimax.io/v1/chat/completions")
            self.assertEqual(kwargs["auth_header"], "Authorization")
            self.assertEqual(kwargs["retries"], 0)
            self.assertTrue(payload["reasoning_split"])
            self.assertEqual(payload["max_completion_tokens"], 8192)
            self.assertEqual(provider.request_parameters["max_completion_tokens"], 8192)
            self.assertNotIn("critical_requirements", json.dumps(payload))
            return ({"model": "MiniMax-M2.7", "choices": [
                {"message": {"content": "Synthetic answer", "reasoning_content": "Hidden reasoning"}, "finish_reason": "stop"}
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
        self.assertEqual(first["text"], "Synthetic answer")
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
        with self.assertRaisesRegex(ProviderRequestError, "completion-token limit"):
            provider.reply([{"role": "user", "content": "Question"}])

    def test_minimax_rejects_embedded_thinking_in_answer_content(self):
        provider = MiniMaxConversationProvider(
            model="MiniMax-M2.7", api_key="fixture-secret", instruction="Respond.",
            transport=lambda *_args, **_kwargs: ({
                "model": "MiniMax-M2.7", "choices": [
                    {"message": {"content": "<think>internal</think> Final answer"}, "finish_reason": "stop"}
                ]}, 1),
        )
        with self.assertRaises(ProviderRequestError):
            provider.reply([{"role": "user", "content": "Question"}])

    def test_saved_answer_with_embedded_thinking_cannot_reach_judge(self):
        family = next(f for f in self.dataset["families"] if f["family_id"] == "HC-MT-TRIAGE-005")
        from benchmark.multiturn import play_variant
        candidate = FixtureCandidate(model="MiniMax-M2.7", api_key="fixture-secret",
                                     instruction="Respond.", timeout=10, retries=0)
        answer = play_variant(family, "en", candidate)
        answer["transcript"][1]["content"] = "<think>hidden</think>Patient-facing text"
        answer["turn_outputs"][0]["text"] = answer["transcript"][1]["content"]
        with self.assertRaises(ValueError):
            build_judge_packet(family, "en", answer)

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

    def test_anchor_bindings_and_criterion_evidence_are_strict(self):
        self.assertEqual(validate_anchor_set(self.anchors, self.dataset)["variant_count"], 8)
        family = next(f for f in self.dataset["families"] if f["family_id"] == "HC-MT-REASON-009")
        for language in ("en", "zh-Hans"):
            turns = family["variants"][language]["turns"]
            answer = {
                "case_id": variant_id(family, language), "case_version": family["version"],
                "case_content_hash": self.anchors["families"][0]["case_hashes"][language],
                "transcript": [message for turn in turns for message in (
                    {"role": "user", "content": turn["user"]},
                    {"role": "assistant", "content": "Fixture answer"})],
                "turn_outputs": [{"stage_id": turn["stage_id"], "text": "Fixture answer"} for turn in turns],
            }
            packet = attach_anchors(build_judge_packet(family, language, answer), self.anchors)
            judge = FixtureCriterionJudge(model="gemini-3.8-flash", api_key="fixture-secret",
                                          instruction="Judge.", timeout=10, retries=0)
            judgment = judge.evaluate(packet)
            self.assertEqual(score_judgment(judgment, packet, self.rubric)["gated_score"], 100)
            corrupted = deepcopy(judgment)
            corrupted["criterion_assessments"][0]["response_evidence"] = "Not in the answer"
            with self.assertRaises(ProviderRequestError):
                validate_judgment(corrupted, packet)
            corrupted = deepcopy(judgment)
            corrupted["criterion_assessments"][0]["status"] = "missed"
            with self.assertRaises(ProviderRequestError):
                validate_judgment(corrupted, packet)
            formatted = deepcopy(packet)
            formatted["transcript"][1]["content"] = "Fixture **answer**"
            formatting_judgment = deepcopy(judgment)
            for item in formatting_judgment["criterion_assessments"]:
                if item["stage_id"] == "initial":
                    item["response_evidence"] = "Fixture answer"
            validate_judgment(formatting_judgment, formatted)
            formatted["transcript"][1]["content"] = "Fixture *answer*"
            validate_judgment(formatting_judgment, formatted)
            formatted["transcript"][1]["content"] = "Fixture _answer_"
            validate_judgment(formatting_judgment, formatted)
            formatted["transcript"][1]["content"] = "- Fixture\n   - answer"
            validate_judgment(formatting_judgment, formatted)
            absence = deepcopy(judgment)
            absence["criterion_assessments"][2]["response_evidence"] = ""
            validate_judgment(absence, packet)
            absence["criterion_assessments"][0]["response_evidence"] = ""
            with self.assertRaises(ProviderRequestError):
                validate_judgment(absence, packet)
        stale = deepcopy(self.anchors)
        stale["families"][0]["case_hashes"]["en"] = "stale"
        with self.assertRaises(ValueError):
            validate_anchor_set(stale, self.dataset)

    def test_judge_only_recovery_and_audit_without_candidate_replay(self):
        plan, selected, candidates, judges = prepare_matrix(
            self.roster, self.dataset, candidate_id="minimax-m27", case_id="HC-MT-TRIAGE-005-EN"
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            target = Path(directory) / "recovered"
            with patch("benchmark.model_matrix.read_setting", return_value="fixture-secret"), \
                 patch.dict("benchmark.model_matrix.CANDIDATES", {"minimax": FixtureCandidate}), \
                 patch.dict("benchmark.model_matrix.JUDGES", {"gemini": FixtureJudge, "grok": FixtureJudge}):
                run_matrix(plan, selected, candidates, judges, self.dataset, self.rubric,
                           output_dir=source, env_file="ignored", candidate_instruction="Respond.",
                           judge_instruction="Judge.", max_api_calls=4)
            with patch("benchmark.model_matrix.read_setting", return_value="fixture-secret"), \
                 patch.dict("benchmark.model_matrix.CANDIDATES", {}), \
                 patch.dict("benchmark.model_matrix.JUDGES",
                            {"gemini": FixtureCriterionJudge, "grok": FixtureCriterionJudge}):
                with self.assertRaises(ValueError):
                    judge_saved_matrix_answer(source, self.roster, self.dataset, self.rubric,
                                              output_dir=target, env_file="ignored",
                                              candidate_instruction="Changed.", judge_instruction="Judge v2.",
                                              max_api_calls=2, anchor_set=self.anchors)
                self.assertFalse(target.exists())
                result = judge_saved_matrix_answer(source, self.roster, self.dataset, self.rubric,
                                                   output_dir=target, env_file="ignored",
                                                   candidate_instruction="Respond.", judge_instruction="Judge v2.",
                                                   max_api_calls=2, anchor_set=self.anchors)
            self.assertEqual((result["candidate_calls"], result["judge_calls"]), (0, 2))
            report = load_json(result["report"])
            audit = audit_matrix_report(report, target)
            self.assertEqual(audit["criterion_disagreement_count"], 1)
            self.assertEqual(audit["full_score_counts"], {"gemini": 1, "grok": 0})
            self.assertEqual(audit["language_summary"]["en"]["candidate_case_count"], 1)
            self.assertNotIn("fixture-secret", "".join(path.read_text() for path in target.iterdir()))
            with self.assertRaises(FileExistsError):
                judge_saved_matrix_answer(source, self.roster, self.dataset, self.rubric,
                                          output_dir=target, env_file="ignored",
                                          candidate_instruction="Respond.", judge_instruction="Judge v2.",
                                          max_api_calls=2, anchor_set=self.anchors)

    def test_strong_partial_and_unsafe_v2_fixture_gates(self):
        family = next(f for f in self.dataset["families"] if f["family_id"] == "HC-MT-TRIAGE-010")
        candidate = FixtureCandidate(model="MiniMax-M2.7", api_key="fixture-secret",
                                     instruction="Respond.", timeout=10, retries=0)
        from benchmark.multiturn import play_variant
        packet = attach_anchors(build_judge_packet(
            family, "en", play_variant(family, "en", candidate)), self.anchors)
        judge = FixtureCriterionJudge(model="gemini-3.8-flash", api_key="fixture-secret",
                                      instruction="Judge.", timeout=10, retries=0)
        strong = judge.evaluate(packet)
        self.assertEqual(score_judgment(strong, packet, self.rubric)["gated_score"], 100)
        partial = deepcopy(strong)
        partial["criterion_assessments"][0]["status"] = "partial"
        partial["stage_scores"][0]["requirements"] = 3
        self.assertLess(score_judgment(partial, packet, self.rubric)["gated_score"], 100)
        omission = deepcopy(partial)
        omission["criterion_assessments"][0]["status"] = "missed"
        omission["criterion_assessments"][0]["response_evidence"] = ""
        self.assertLess(score_judgment(omission, packet, self.rubric)["gated_score"], 100)
        unsafe = deepcopy(omission)
        configured = packet["turn_labels"][0]["critical_errors"][0]
        unsafe["critical_errors"] = [{"stage_id": "initial", "error_id": configured["id"],
                                      "severity": configured["severity"], "rationale": "Fixture unsafe advice."}]
        gated = score_judgment(unsafe, packet, self.rubric)
        self.assertEqual(gated["gated_score"], 20)
        self.assertTrue(gated["hard_fail"])

    def test_two_judge_synthetic_contrast_is_bounded_and_ordered(self):
        root = Path(__file__).resolve().parents[1]
        probe = load_json(root / "data/multiturn/criterion_contrast_v1.json")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "contrast"
            with patch("benchmark.model_matrix.read_setting", return_value="fixture-secret"), \
                 patch.dict("benchmark.model_matrix.JUDGES", {
                     "gemini": FixtureContrastCriterionJudge,
                     "grok": FixtureContrastCriterionJudge,
                 }):
                with self.assertRaises(ValueError):
                    run_anchored_contrast(probe, self.roster, self.dataset, self.rubric,
                                          self.anchors, output_dir=target, env_file="ignored",
                                          judge_instruction="Judge v2.", max_api_calls=5)
                self.assertFalse(target.exists())
                result = run_anchored_contrast(probe, self.roster, self.dataset, self.rubric,
                                               self.anchors, output_dir=target, env_file="ignored",
                                               judge_instruction="Judge v2.", max_api_calls=6)
            report = load_json(result["report"])
            self.assertEqual((report["candidate_calls"], report["judge_calls"]), (0, 6))
            self.assertTrue(all(row["ordered_scores"] and row["unsafe_error_detected"]
                                and not row["unsafe_false_pass"] for row in report["results"].values()))

    def test_judge_only_can_select_one_saved_answer_from_partial_multicase_run(self):
        plan, selected, candidates, judges = prepare_matrix(
            self.roster, self.dataset, candidate_id="minimax-m27",
            selected_case_ids=["HC-MT-TRIAGE-005-EN", "HC-MT-TRIAGE-005-ZH-HANS"],
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            target = Path(directory) / "recovered"
            with patch("benchmark.model_matrix.read_setting", return_value="fixture-secret"), \
                 patch.dict("benchmark.model_matrix.CANDIDATES", {"minimax": FixtureCandidate}), \
                 patch.dict("benchmark.model_matrix.JUDGES", {"gemini": FixtureJudge, "grok": FixtureJudge}):
                run_matrix(plan, selected, candidates, judges, self.dataset, self.rubric,
                           output_dir=source, env_file="ignored", candidate_instruction="Respond.",
                           judge_instruction="Judge.", max_api_calls=8)
            with patch("benchmark.model_matrix.read_setting", return_value="fixture-secret"), \
                 patch.dict("benchmark.model_matrix.JUDGES", {
                     "gemini": FixtureCriterionJudge, "grok": FixtureCriterionJudge,
                 }):
                with self.assertRaises(ValueError):
                    judge_saved_matrix_answer(source, self.roster, self.dataset, self.rubric,
                                              output_dir=target, env_file="ignored",
                                              candidate_instruction="Respond.", judge_instruction="Judge v2.",
                                              max_api_calls=2, anchor_set=self.anchors)
                result = judge_saved_matrix_answer(source, self.roster, self.dataset, self.rubric,
                                                   output_dir=target, env_file="ignored",
                                                   candidate_instruction="Respond.", judge_instruction="Judge v2.",
                                                   max_api_calls=2, anchor_set=self.anchors,
                                                   case_id="HC-MT-TRIAGE-005-ZH-HANS")
            self.assertEqual(load_json(result["report"])["results"][0]["case_id"],
                             "HC-MT-TRIAGE-005-ZH-HANS")

    def test_offline_assembly_checks_all_saved_scores_and_hashes(self):
        case_ids = ["HC-MT-TRIAGE-005-EN", "HC-MT-TRIAGE-005-ZH-HANS"]
        plan, selected, candidates, judges = prepare_matrix(
            self.roster, self.dataset, candidate_id="minimax-m27", selected_case_ids=case_ids,
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            target = Path(directory) / "assembled"
            with patch("benchmark.model_matrix.read_setting", return_value="fixture-secret"), \
                 patch.dict("benchmark.model_matrix.CANDIDATES", {"minimax": FixtureCandidate}), \
                 patch.dict("benchmark.model_matrix.JUDGES", {
                     "gemini": FixtureCriterionJudge, "grok": FixtureCriterionJudge,
                 }):
                run_matrix(plan, selected, candidates, judges, self.dataset, self.rubric,
                           output_dir=source, env_file="ignored", candidate_instruction="Respond.",
                           judge_instruction="Judge v2.", max_api_calls=8, anchor_set=self.anchors)
            with self.assertRaises(ValueError):
                assemble_matrix_artifacts([source], self.roster, self.dataset, self.rubric,
                                          self.anchors, candidate_id="minimax-m27", case_ids=case_ids,
                                          output_dir=target, candidate_instruction="Changed.",
                                          judge_instruction="Judge v2.")
            self.assertFalse(target.exists())
            result = assemble_matrix_artifacts([source], self.roster, self.dataset, self.rubric,
                                               self.anchors, candidate_id="minimax-m27", case_ids=case_ids,
                                               output_dir=target, candidate_instruction="Respond.",
                                               judge_instruction="Judge v2.")
            report = load_json(result["report"])
            audit = audit_matrix_report(report, target)
            self.assertEqual((report["actual_api_calls"], report["logical_calls_included"]), (None, 8))
            self.assertEqual(len(audit["bilingual_pairs"]), 1)
            self.assertNotIn("fixture-secret", "".join(path.read_text() for path in target.iterdir()))


if __name__ == "__main__":
    unittest.main()
