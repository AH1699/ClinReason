from copy import deepcopy
from pathlib import Path
import re
import unittest

from benchmark.config import load_json
from benchmark.multiturn import play_variant
from scripts import audit_batch_q as batch

ROOT = Path(__file__).resolve().parents[1]


class BatchQTests(unittest.TestCase):
    def setUp(self):
        self.data = {name: load_json(ROOT / path) for name, path in batch.FILES.items()}

    def test_complete_standalone_package(self):
        value = batch.audit(ROOT)
        self.assertEqual((value["new_standalone_families"], value["variants"],
                          value["mapped_criterion_positions"], value["bilingual_requirement_instances"]), (4, 8, 28, 56))
        self.assertEqual((value["initial_references"], value["update_references"]), (8, 24))
        self.assertEqual((value["default_portfolio_additions"], value["live_calls"], value["numeric_scores"]), (0, 0, 0))
        self.assertEqual(value["triage_transitions"], {"timely_nonemergency→emergency": 1})

    def test_changed_case_invalidates_exact_labels(self):
        self.data["cases"]["families"][0]["variants"]["en"]["turns"][0]["user"] += " changed"
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_stale_source_hash_is_rejected(self):
        self.data["provenance"]["records"][0]["requirement_support"][0]["case_hashes"]["en"] = "0" * 64
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_missing_or_reordered_mapping_is_rejected(self):
        for remove in (True, False):
            with self.subTest(remove=remove):
                data = deepcopy(self.data)
                rows = data["provenance"]["records"][0]["requirement_support"]
                if remove: rows.pop()
                else: rows[0], rows[1] = rows[1], rows[0]
                with self.assertRaises(ValueError): batch.validate(data)

    def test_unlisted_guidance_is_rejected(self):
        self.data["provenance"]["records"][0]["requirement_support"][0]["guidance_url"] = "https://example.org"
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_missing_source_inventory_is_rejected(self):
        self.data["provenance"]["sources"].pop(0)
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_inference_type_must_remain_explicit(self):
        self.data["provenance"]["records"][0]["requirement_support"][0]["support_type"] = "clinically_proven"
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_duplicate_source_inventory_is_rejected(self):
        self.data["provenance"]["sources"].append(deepcopy(self.data["provenance"]["sources"][0]))
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_missing_anchor_family_is_rejected(self):
        self.data["anchors"]["families"].pop()
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_duplicate_reference_language_is_rejected(self):
        self.data["controls"]["probes"][1] = deepcopy(self.data["controls"]["probes"][0])
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_partial_is_exact_one_component_deletion(self):
        for probe in self.data["controls"]["probes"]:
            value = batch.materialize(probe)
            separator = " " if probe["language"] == "en" else ""
            index = probe["partial_omitted_requirement_index"]
            self.assertEqual(value["partial_update_response"], separator.join(
                t for i, t in enumerate(probe["safe_components"], 1) if i != index))
            self.assertNotIn(probe["safe_components"][index - 1], value["partial_update_response"])
            self.assertEqual(value["initial_response"], probe["initial_response"])

    def test_invalid_omission_indices(self):
        for index in (0, 5, True, "1"):
            with self.subTest(index=index):
                self.data["controls"]["probes"][0]["partial_omitted_requirement_index"] = index
                with self.assertRaises(ValueError): batch.validate(self.data)

    def test_unsafe_error_must_be_in_current_case(self):
        self.data["controls"]["probes"][0]["expected_unsafe_error_id"] = "NOT-IN-CASE"
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_no_review_or_privacy_promotion(self):
        for key in ("private_records_used", "source_patient_reconstructed", "images_used"):
            data = deepcopy(self.data)
            data["provenance"]["records"][0]["privacy_check"][key] = True
            with self.assertRaises(ValueError): batch.validate(data)
        self.data["provenance"]["records"][0]["review_complete"] = True
        with self.assertRaises(ValueError): batch.validate(self.data)

    def test_case_identity_overlap_in_reserved_set_is_rejected(self):
        with self.assertRaises(ValueError):
            batch.overlap_check(self.data, [(Path("data/calibration/fake.json"), "HC-MT-REASON-027", [])])

    def test_report_alias_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            batch.overlap_check(self.data, [(Path("data/confirmation/fake.json"), "EXISTING",
                                           ["https://doi.org/10.3389/fsurg.2020.00030"] )])

    def test_shared_guidance_is_reported_not_silently_independent(self):
        url = self.data["cases"]["families"][0]["source_refs"][1]
        value = batch.overlap_check(self.data, [(Path("data/calibration/fake.json"), "EXISTING", [url])])
        self.assertEqual(len(value["shared_guidance"]), 1)

    def test_bilingual_numeric_facts_align_not_language_approval(self):
        for family in self.data["cases"]["families"]:
            for en, zh in zip(family["variants"]["en"]["turns"], family["variants"]["zh-Hans"]["turns"]):
                self.assertEqual(re.findall(r"\d+(?:\.\d+)?", en["user"]), re.findall(r"\d+(?:\.\d+)?", zh["user"]))

    def test_candidate_gets_no_labels_or_future_turn(self):
        class Candidate:
            provider_name, model_id, model_version = "offline", "fixture", None
            def __init__(self): self.histories = []
            def reply(self, history):
                self.histories.append(history)
                return {"text": "Offline test answer"}
        for family in self.data["cases"]["families"]:
            candidate = Candidate()
            play_variant(family, "en", candidate)
            self.assertEqual(candidate.histories[0], [{"role": "user", "content": family["variants"]["en"]["turns"][0]["user"]}])
            self.assertEqual(len(candidate.histories[1]), 3)


if __name__ == "__main__": unittest.main()
