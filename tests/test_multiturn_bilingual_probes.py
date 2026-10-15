import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path

from benchmark.cli import main
from benchmark.config import load_json
from benchmark.multiturn import merge_multiturn_datasets
from benchmark.multiturn_bilingual_probes import (
    probe_packet, run_bilingual_probes, validate_probe_set,
)
from benchmark.providers.grok_multiturn_judge import GrokMultiturnJudge
from benchmark.providers.http_json import ProviderRequestError


class FixtureJudge:
    provider_name = "fixture"
    model_id = "fixture-model"
    model_version = "fixture-model"

    def __init__(self, baselines):
        self.baselines = baselines

    def evaluate(self, packet):
        initial = packet["transcript"][1]["content"]
        is_baseline = initial in self.baselines
        return {
            "stage_scores": [
                {"stage_id": "initial", "safety": 4,
                 "requirements": 4 if is_baseline else 3, "rationale": "Fixture only."},
                {"stage_id": "update", "safety": 4, "requirements": 4,
                 "rationale": "Fixture only."},
            ],
            "revision_score": 4, "critical_errors": [], "confidence": 0.8,
            "requires_human_review": False, "overall_rationale": "Fixture only.",
        }


class BilingualProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.dataset = merge_multiturn_datasets([
            load_json(cls.root / "data/multiturn/pilot_cases.json"),
            load_json(cls.root / "data/multiturn/batch_c_cases.json"),
            load_json(cls.root / "data/multiturn/batch_d_cases.json"),
        ])
        cls.probes = load_json(cls.root / "data/multiturn/bilingual_judge_probes.json")
        cls.rubric = load_json(cls.root / "config/multiturn_rubric.json")

    def test_fixture_is_case_bound_bilingual_and_blinded(self):
        pairs = validate_probe_set(self.dataset, self.probes)
        self.assertEqual(len(pairs), 4)
        family = next(f for f in self.dataset["families"] if f["family_id"] == pairs[0]["family_id"])
        packet = probe_packet(family, pairs[0], "challenge")
        self.assertNotIn("challenge", json.dumps(packet, ensure_ascii=False))
        self.assertNotIn(pairs[0]["hypothesis"], json.dumps(packet, ensure_ascii=False))
        bad = deepcopy(self.probes)
        bad["pairs"][0]["case_content_hash"] = "stale"
        with self.assertRaises(ValueError):
            validate_probe_set(self.dataset, bad)

    def test_fixture_judge_detects_both_language_gaps(self):
        judge = FixtureJudge({pair["baseline_initial"] for pair in self.probes["pairs"]})
        result = run_bilingual_probes(self.dataset, self.probes, judge, self.rubric)
        self.assertEqual(result["probe_count"], 8)
        self.assertEqual(result["positive_gap_count"], 4)
        self.assertTrue(all(row["score_gap_baseline_minus_challenge"] == 3
                            for row in result["results"]))

    def test_grok_judge_is_structured_and_model_blind(self):
        pairs = self.probes["pairs"]
        family = next(f for f in self.dataset["families"] if f["family_id"] == pairs[0]["family_id"])
        packet = probe_packet(family, pairs[0], "baseline")
        judgment = FixtureJudge({pairs[0]["baseline_initial"]}).evaluate(packet)

        def transport(_endpoint, payload, **kwargs):
            self.assertFalse(payload["store"])
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertNotIn("baseline", json.dumps(payload, ensure_ascii=False))
            self.assertEqual(kwargs["auth_header"], "Authorization")
            return ({"status": "completed", "model": "grok-fixture", "output": [
                {"type": "message", "content": [
                    {"type": "output_text", "text": json.dumps(judgment)}
                ]}
            ]}, 1)

        judge = GrokMultiturnJudge(model="grok-fixture", api_key="fixture-key",
                                   instruction="Judge the draft.", transport=transport)
        self.assertEqual(judge.evaluate(packet)["revision_score"], 4)
        self.assertEqual(judge.model_version, "grok-fixture")

    def test_grok_judge_rejects_wrong_model_identity(self):
        pair = self.probes["pairs"][0]
        family = next(f for f in self.dataset["families"] if f["family_id"] == pair["family_id"])
        packet = probe_packet(family, pair, "baseline")

        def transport(_endpoint, _payload, **_kwargs):
            return ({"status": "completed", "model": "other-model", "output": []}, 1)

        judge = GrokMultiturnJudge(model="grok-fixture", api_key="fixture-key",
                                   instruction="Judge the draft.", transport=transport)
        judge.model_version = "grok-fixture"
        with self.assertRaises(ProviderRequestError):
            judge.evaluate(packet)

    def test_cli_dry_run_needs_no_api_key_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "probe.json"
            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["judge-multiturn-bilingual-probes", "--provider", "grok",
                               "--model", "grok-fixture", "--output", str(target)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["planned_api_calls"], 8)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
