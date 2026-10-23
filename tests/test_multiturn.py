import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmark.cli import main
from benchmark.config import load_json, load_jsonl
from benchmark.multiturn import (
    build_judge_packet, judge_packets_from_answers, merge_multiturn_datasets,
    ordered_variants, play_variant, validate_multiturn_dataset,
    write_batch,
)
from benchmark.providers.grok_conversation import GrokConversationProvider
from benchmark.providers.gemini_conversation import GeminiConversationProvider


class InspectingConversationCandidate:
    provider_name = "fixture"
    model_id = "fixture-model"
    model_version = "1"

    def __init__(self):
        self.histories = []

    def reply(self, history):
        self.histories.append(deepcopy(history))
        return {"text": f"Fixture answer {len(self.histories)}"}


class MultiturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.dataset = load_json(cls.root / "data/multiturn/pilot_cases.json")

    def test_contract_and_coverage(self):
        status = validate_multiturn_dataset(self.dataset)
        self.assertEqual(status["family_count"], 4)
        self.assertEqual(status["variant_count"], 8)
        self.assertEqual(status["triage_transitions"], {
            "routine→emergency": 1, "self_care→emergency": 1,
        })
        self.assertEqual(len(ordered_variants(self.dataset)), 8)

    def test_batch_c_merges_without_changing_original_pilot(self):
        batch_c = load_json(self.root / "data/multiturn/batch_c_cases.json")
        combined = merge_multiturn_datasets([self.dataset, batch_c])
        status = validate_multiturn_dataset(combined)
        self.assertEqual(status["family_count"], 16)
        self.assertEqual(status["variant_count"], 32)
        self.assertEqual(status["category_counts"], {
            "clinical_reasoning": 5, "medication_safety": 5, "triage": 6,
        })
        self.assertEqual(self.dataset["families"][0]["family_id"], "HC-MT-TRIAGE-001")
        with self.assertRaises(ValueError):
            merge_multiturn_datasets([self.dataset, self.dataset])

    def test_cli_validates_all_configured_batches(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["validate-multiturn"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["family_count"], 51)

    def test_batch_f_adds_four_distinct_bilingual_draft_families(self):
        batches = [self.dataset] + [
            load_json(self.root / f"data/multiturn/batch_{batch}_cases.json")
            for batch in ("c", "d", "e", "f")
        ]
        status = validate_multiturn_dataset(merge_multiturn_datasets(batches))
        self.assertEqual((status["family_count"], status["variant_count"]), (34, 68))
        self.assertEqual(status["category_counts"], {
            "clinical_reasoning": 10, "medication_safety": 11, "triage": 13,
        })
        batch_f = batches[-1]
        ledger = load_json(self.root / "data/multiturn/batch_f_provenance.json")
        self.assertEqual({entry["family_id"] for entry in ledger["records"]},
                         {family["family_id"] for family in batch_f["families"]})
        for family in batch_f["families"]:
            record = next(entry for entry in ledger["records"]
                          if entry["family_id"] == family["family_id"])
            self.assertEqual(set(family["source_refs"]),
                             set(record["supporting_sources"]) |
                             ({record["published_case_or_series"]} if record["published_case_or_series"] else set()))
            self.assertTrue(record["source_to_label_limit"])

    def test_batch_g_adds_deescalation_controls_with_exact_provenance(self):
        config = load_json(self.root / "config/benchmark.json")
        historical_batches = {"pilot_cases.json", "batch_c_cases.json", "batch_d_cases.json",
                              "batch_e_cases.json", "batch_f_cases.json", "batch_g_cases.json"}
        batches = [load_json(self.root / path) for path in config["multiturn_cases_paths"]
                   if Path(path).name in historical_batches]
        status = validate_multiturn_dataset(merge_multiturn_datasets(batches))
        self.assertEqual((status["family_count"], status["variant_count"]), (38, 76))
        self.assertEqual(status["category_counts"], {
            "clinical_reasoning": 11, "medication_safety": 11, "triage": 16,
        })
        batch_g = batches[-1]
        ledger = load_json(self.root / "data/multiturn/batch_g_provenance.json")
        self.assertEqual(len(batch_g["families"]), 4)
        self.assertEqual({entry["family_id"] for entry in ledger["records"]},
                         {family["family_id"] for family in batch_g["families"]})
        self.assertEqual(status["triage_transitions"]["timely_nonemergency→self_care"], 2)
        self.assertEqual(status["triage_transitions"]["self_care→self_care"], 1)
        for family in batch_g["families"]:
            record = next(entry for entry in ledger["records"]
                          if entry["family_id"] == family["family_id"])
            self.assertIsNone(record["published_case_or_series"])
            self.assertEqual(set(family["source_refs"]), set(record["supporting_sources"]))
            self.assertTrue(record["source_to_label_limit"])

    def test_batch_e_reaches_thirty_distinct_families(self):
        batches = [self.dataset] + [
            load_json(self.root / f"data/multiturn/batch_{batch}_cases.json")
            for batch in ("c", "d", "e")
        ]
        status = validate_multiturn_dataset(merge_multiturn_datasets(batches))
        self.assertEqual((status["family_count"], status["variant_count"]), (30, 60))
        self.assertEqual(status["category_counts"], {
            "clinical_reasoning": 9, "medication_safety": 9, "triage": 12,
        })

    def test_batch_d_adds_distinct_bilingual_failure_modes(self):
        batch_c = load_json(self.root / "data/multiturn/batch_c_cases.json")
        batch_d = load_json(self.root / "data/multiturn/batch_d_cases.json")
        combined = merge_multiturn_datasets([self.dataset, batch_c, batch_d])
        status = validate_multiturn_dataset(combined)
        self.assertEqual(status["family_count"], 20)
        self.assertEqual(status["variant_count"], 40)
        self.assertEqual(status["category_counts"], {
            "clinical_reasoning": 7, "medication_safety": 6, "triage": 7,
        })
        self.assertEqual(status["triage_transitions"]["emergency→emergency"], 1)
        self.assertEqual({family["family_id"] for family in batch_d["families"]}, {
            "HC-MT-TRIAGE-007", "HC-MT-MEDSAFE-006",
            "HC-MT-REASON-006", "HC-MT-REASON-007",
        })

    def test_old_pilot_answer_remains_content_bound_after_batch_merge(self):
        combined = merge_multiturn_datasets([
            self.dataset, load_json(self.root / "data/multiturn/batch_c_cases.json")
        ])
        old_answer = play_variant(self.dataset["families"][0], "en", InspectingConversationCandidate())
        packets = judge_packets_from_answers(combined, [old_answer])
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["case_content_hash"], old_answer["case_content_hash"])

    def test_bilingual_error_mismatch_rejected(self):
        corrupted = deepcopy(self.dataset)
        corrupted["families"][0]["variants"]["zh-Hans"]["turns"][1]["critical_errors"][0]["severity"] = 1
        with self.assertRaises(ValueError):
            validate_multiturn_dataset(corrupted)

    def test_malformed_turn_or_empty_scope_rejected_cleanly(self):
        corrupted = deepcopy(self.dataset)
        corrupted["scope"] = " "
        with self.assertRaises(ValueError):
            validate_multiturn_dataset(corrupted)
        corrupted = deepcopy(self.dataset)
        corrupted["families"][0]["variants"]["en"]["turns"][1] = None
        with self.assertRaises(ValueError):
            validate_multiturn_dataset(corrupted)

    def test_future_turn_and_labels_never_reach_candidate(self):
        family = self.dataset["families"][0]
        candidate = InspectingConversationCandidate()
        response = play_variant(family, "en", candidate)
        self.assertEqual(len(candidate.histories), 2)
        self.assertEqual([item["role"] for item in candidate.histories[0]], ["user"])
        self.assertEqual([item["role"] for item in candidate.histories[1]], ["user", "assistant", "user"])
        self.assertEqual(candidate.histories[1][1]["content"], "Fixture answer 1")
        self.assertNotIn("short of breath at rest", json.dumps(candidate.histories[0]))
        self.assertNotIn("critical_requirements", json.dumps(candidate.histories))
        self.assertNotIn("source_refs", json.dumps(candidate.histories))
        packet = build_judge_packet(family, "en", response)
        self.assertEqual(len(packet["turn_labels"]), 2)
        self.assertNotIn("provider", packet)
        self.assertNotIn("model_id", packet)
        corrupted = deepcopy(response)
        corrupted["transcript"][2]["content"] = "Different prompt"
        with self.assertRaises(ValueError):
            build_judge_packet(family, "en", corrupted)

    def test_grok_adapter_resends_visible_history_with_store_false(self):
        payloads = []

        def transport(_endpoint, payload, **kwargs):
            payloads.append(payload)
            self.assertEqual(kwargs["auth_header"], "Authorization")
            self.assertFalse(payload["store"])
            self.assertNotIn("critical_requirements", json.dumps(payload))
            return ({"status": "completed", "model": "grok-test", "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "Synthetic answer"}]}
            ]}, 4)

        provider = GrokConversationProvider(
            model="grok-test", api_key="fixture-key", instruction="Answer the chat.",
            transport=transport,
        )
        response = play_variant(self.dataset["families"][0], "en", provider)
        self.assertEqual(len(payloads), 2)
        self.assertEqual([item["role"] for item in payloads[0]["input"]], ["system", "user"])
        self.assertEqual([item["role"] for item in payloads[1]["input"]],
                         ["system", "user", "assistant", "user"])
        self.assertEqual(response["model_version"], "grok-test")

    def test_gemini_adapter_resends_only_visible_history_with_store_false(self):
        payloads = []

        def transport(_endpoint, payload, **kwargs):
            payloads.append(payload)
            self.assertEqual(kwargs["auth_header"], "x-goog-api-key")
            self.assertFalse(payload["store"])
            self.assertNotIn("critical_requirements", json.dumps(payload))
            return ({"status": "completed", "model": "gemini-test", "steps": [
                {"type": "model_output", "content": [{"type": "text", "text": "Synthetic answer"}]}
            ]}, 4)

        provider = GeminiConversationProvider(
            model="gemini-test", api_key="fixture-key", instruction="Answer the chat.",
            transport=transport,
        )
        response = play_variant(self.dataset["families"][0], "en", provider)
        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["input"].count("<user"), 1)
        self.assertEqual(payloads[1]["input"].count("<user"), 2)
        self.assertEqual(payloads[1]["input"].count("<assistant"), 1)
        self.assertEqual(response["model_version"], "gemini-test")

    def test_batch_outputs_are_content_bound_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "answers.jsonl"
            result = write_batch(self.dataset, ordered_variants(self.dataset)[:2],
                                 InspectingConversationCandidate(), path,
                                 instruction="Answer the chat.")
            self.assertEqual(result["case_count"], 2)
            self.assertEqual(result["model_calls"], 4)
            self.assertEqual(len(load_jsonl(path)), 2)
            self.assertEqual(len(result["dataset_sha256"]), 64)
            with self.assertRaises(FileExistsError):
                write_batch(self.dataset, ordered_variants(self.dataset)[:1],
                            InspectingConversationCandidate(), path,
                            instruction="Answer the chat.")
            with self.assertRaises(ValueError):
                write_batch(self.dataset, ordered_variants(self.dataset)[:1] * 2,
                            InspectingConversationCandidate(), Path(directory) / "other.jsonl",
                            instruction="Answer the chat.")
            altered = deepcopy(ordered_variants(self.dataset)[0][0])
            altered["variants"]["en"]["turns"][0]["user"] = "Changed question"
            with self.assertRaises(ValueError):
                write_batch(self.dataset, [(altered, "en")], InspectingConversationCandidate(),
                            Path(directory) / "altered.jsonl", instruction="Answer the chat.")

    def test_all_variants_can_produce_draft_judge_packets_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "all_answers.jsonl"
            write_batch(self.dataset, ordered_variants(self.dataset),
                        InspectingConversationCandidate(), path,
                        instruction="Answer the chat.")
            answers = load_jsonl(path)
            self.assertEqual(len(answers), 8)
            packet_path = Path(directory) / "packets.jsonl"
            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["export-multiturn-judge-packets", "--answers", str(path),
                               "--output", str(packet_path)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["packet_count"], 8)
            packets = load_jsonl(packet_path)
            self.assertEqual(len(packets), 8)
            self.assertTrue(all(len(packet["transcript"]) == 4 for packet in packets))
            self.assertTrue(all(len(packet["turn_labels"]) == 2 for packet in packets))

    def test_cli_dry_run_is_no_network_and_plans_two_calls_per_variant(self):
        output = io.StringIO()
        with patch("benchmark.providers.grok_conversation.post_json", side_effect=AssertionError("network called")):
            with redirect_stdout(output):
                status = main(["generate-grok-multiturn", "--model", "grok-test", "--limit", "2"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["planned_api_calls"], 4)
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["generate-grok-multiturn", "--model", "grok-test",
                           "--case-id", "HC-MT-MEDSAFE-001-ZH-HANS"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["planned_variants"], 1)
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["generate-gemini-multiturn", "--model", "gemini-test", "--limit", "4",
                           "--family-ids", "HC-MT-TRIAGE-003,HC-MT-REASON-004"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["planned_api_calls"], 8)


if __name__ == "__main__":
    unittest.main()
