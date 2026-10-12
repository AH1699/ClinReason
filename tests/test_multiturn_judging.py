import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json
from benchmark.multiturn import build_judge_packet, play_variant, write_batch, ordered_variants
from benchmark.multiturn_judging import (
    GeminiMultiturnJudge, score_judgment, validate_judgment,
)
from benchmark.providers.http_json import ProviderRequestError


class FixtureCandidate:
    provider_name = "fixture"
    model_id = "MODEL_SECRET_MARKER"
    model_version = "1"

    def reply(self, _history):
        return {"text": "Synthetic fixture answer."}


class MultiturnJudgingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.dataset = load_json(root / "data/multiturn/pilot_cases.json")
        cls.rubric = load_json(root / "config/multiturn_rubric.json")
        cls.family = next(f for f in cls.dataset["families"] if f["family_id"] == "HC-MT-MEDSAFE-001")
        cls.response = play_variant(cls.family, "en", FixtureCandidate())
        cls.packet = build_judge_packet(cls.family, "en", cls.response)

    def _judgment(self, errors=None):
        return {
            "stage_scores": [
                {"stage_id": stage, "safety": 4, "requirements": 4, "rationale": "Fixture."}
                for stage in ("initial", "update")
            ],
            "revision_score": 4,
            "critical_errors": errors or [],
            "confidence": 0.8,
            "requires_human_review": False,
            "overall_rationale": "Fixture only.",
        }

    def test_perfect_fixture_is_still_marked_unvalidated(self):
        score = score_judgment(self._judgment(), self.packet, self.rubric)
        self.assertEqual(score["gated_score"], 100)
        self.assertTrue(score["pass"])
        self.assertEqual(score["review_status"], "required")
        self.assertEqual(score["status"], "experimental_unvalidated_single_ai_judge")

    def test_unsafe_initial_turn_cannot_be_erased_by_perfect_update(self):
        packet = self.packet
        error = packet["turn_labels"][0]["critical_errors"][0]
        judgment = self._judgment([{
            "stage_id": "initial", "error_id": error["id"],
            "severity": error["severity"], "rationale": "Fixture error.",
        }])
        # This family has a severity-2 first-stage error, so it still caps the aggregate.
        score = score_judgment(judgment, packet, self.rubric)
        self.assertEqual(score["gated_score"], 50)
        self.assertFalse(score["pass"])
        emergency = next(f for f in self.dataset["families"] if f["family_id"] == "HC-MT-TRIAGE-002")
        emergency_packet = build_judge_packet(emergency, "en", play_variant(emergency, "en", FixtureCandidate()))
        severe = emergency_packet["turn_labels"][1]["critical_errors"][0]
        judgment = self._judgment([{
            "stage_id": "update", "error_id": severe["id"],
            "severity": 3, "rationale": "Fixture error.",
        }])
        score = score_judgment(judgment, emergency_packet, self.rubric)
        self.assertEqual(score["gated_score"], 20)
        self.assertTrue(score["hard_fail"])
        self.assertFalse(score["pass"])

    def test_invented_or_wrong_stage_error_rejected(self):
        judgment = self._judgment([{
            "stage_id": "update", "error_id": "INVENTED", "severity": 3,
            "rationale": "Fixture error.",
        }])
        with self.assertRaises(ProviderRequestError):
            validate_judgment(judgment, self.packet)

    def test_gemini_payload_is_structured_and_model_blind(self):
        seen = []

        def transport(_endpoint, payload, **kwargs):
            seen.append(payload)
            self.assertFalse(payload["store"])
            self.assertEqual(payload["response_format"]["mime_type"], "application/json")
            self.assertNotIn("MODEL_SECRET_MARKER", payload["input"])
            self.assertEqual(kwargs["auth_header"], "x-goog-api-key")
            return ({"status": "completed", "model": "gemini-fixture",
                     "steps": [{"type": "model_output", "content": [
                         {"type": "text", "text": json.dumps(self._judgment())}]}]}, 3)

        judge = GeminiMultiturnJudge(model="gemini-fixture", api_key="fixture-key",
                                     instruction="Judge this draft.", transport=transport)
        output = judge.evaluate(self.packet)
        self.assertEqual(output["revision_score"], 4)
        self.assertEqual(judge.model_version, "gemini-fixture")
        self.assertEqual(len(seen), 1)

    def test_cli_dry_run_requires_no_key(self):
        with tempfile.TemporaryDirectory() as directory:
            answers_path = Path(directory) / "answers.jsonl"
            write_batch(self.dataset, ordered_variants(self.dataset)[:1],
                        FixtureCandidate(), answers_path, instruction="Fixture.")
            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["judge-multiturn-gemini", "--answers", str(answers_path),
                               "--model", "gemini-fixture", "--output", str(Path(directory) / "judge.jsonl")])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["planned_judgments"], 1)


if __name__ == "__main__":
    unittest.main()
