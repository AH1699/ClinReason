from copy import deepcopy
import json
from pathlib import Path
import unittest

from benchmark import confirmation_s37 as s37
from benchmark.config import load_json
from benchmark.criterion_anchors import validate_anchor_set
from benchmark.multiturn import validate_multiturn_dataset
from benchmark import scoring_s36 as scoring

ROOT = Path(__file__).resolve().parents[1]


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_json(ROOT / s37.CASES)
        self.anchors = load_json(ROOT / s37.ANCHORS)
        self.evidence = load_json(ROOT / s37.PROVENANCE)
        self.reservation = load_json(ROOT / s37.RESERVATION)

    def test_three_families_six_variants_remain_unreviewed(self):
        result = validate_multiturn_dataset(self.dataset)
        self.assertEqual((result["family_count"], result["variant_count"]), (3, 6))
        self.assertEqual(validate_anchor_set(self.anchors, self.dataset)["family_count"], 3)

    def test_all_six_case_and_anchor_bindings_exact(self):
        self.assertEqual(self.reservation, s37.reservation(ROOT))
        self.assertEqual(len(self.reservation["families"]), 6)
        self.assertEqual(self.reservation["live_call_allowance"], 0)

    def test_selected_split_source_and_group_checks(self):
        s37.check_sources(ROOT, self.reservation["families"])

    def test_normalization_detects_shared_source_despite_suffix(self):
        rows = deepcopy(self.reservation["families"])
        plan = load_json(ROOT / s37.mix.PLAN)
        fid = plan["development"][0]["family_id"]
        family = next(f for f in load_json(ROOT / "data/multiturn/batch_g_cases.json")["families"] if f["family_id"] == fid)
        rows[0]["source_refs"] = [family["source_refs"][0].rstrip("/") + "/?test=1#fragment"]
        with self.assertRaisesRegex(ValueError, "Source URL leakage"):
            s37.check_sources(ROOT, rows)

    def test_duplicates_and_development_overlap_rejected(self):
        for fid in (self.reservation["families"][1]["family_id"], "HC-MT-TRIAGE-019", "HC-MT-TRIAGE-018"):
            rows = deepcopy(self.reservation["families"])
            rows[0]["family_id"] = fid
            with self.subTest(fid=fid), self.assertRaises(ValueError):
                s37.check_sources(ROOT, rows)

    def test_balanced_categories_and_strata_are_not_optional(self):
        for key in ("category", "design_stratum"):
            rows = deepcopy(self.reservation["families"])
            rows[0][key] = rows[1][key]
            with self.assertRaises(ValueError): s37.check_sources(ROOT, rows)

    def test_case_edit_invalidates_anchor_hash(self):
        self.dataset["families"][0]["variants"]["zh-Hans"]["turns"][1]["user"] += " 另一条信息。"
        with self.assertRaisesRegex(ValueError, "Stale criterion"):
            validate_anchor_set(self.anchors, self.dataset)

    def test_missing_anchor_component_rejected(self):
        self.anchors["families"][0]["stages"]["update"][0].pop("partial")
        with self.assertRaises(ValueError): validate_anchor_set(self.anchors, self.dataset)

    def test_all_source_mappings_match_requirements_and_errors(self):
        s37.check_provenance(self.dataset, self.evidence)
        self.assertEqual(sum(len(r["criterion_map"]) for r in self.evidence["records"]), 18)
        self.assertEqual(sum(len(r["error_map"]) for r in self.evidence["records"]), 6)

    def test_missing_or_duplicate_source_record_rejected(self):
        for change in ("missing", "duplicate"):
            evidence = deepcopy(self.evidence)
            if change == "missing": evidence["records"].pop()
            else: evidence["records"][1] = evidence["records"][0]
            with self.assertRaises(ValueError): s37.check_provenance(self.dataset, evidence)

    def test_stale_requirement_or_error_map_rejected(self):
        for kind in ("criterion_map", "error_map"):
            evidence = deepcopy(self.evidence)
            evidence["records"][0][kind].reverse()
            with self.assertRaises(ValueError): s37.check_provenance(self.dataset, evidence)

    def test_unbound_mapping_url_rejected(self):
        self.evidence["records"][0]["criterion_map"][0]["sources"] = ["https://example.invalid"]
        with self.assertRaises(ValueError): s37.check_provenance(self.dataset, self.evidence)

    def test_twelve_structural_examples_no_future_initial_labels(self):
        packets = s37.example_packets(ROOT)
        self.assertEqual(len(packets), 12)
        for key, packet in packets.items():
            scoring.check_packet(packet)
            self.assertEqual(len(packet["criterion_anchors"]), 3)
            if key.endswith("__initial"):
                self.assertEqual(len(packet["transcript"]), 2)
                future = packets[key.removesuffix("initial") + "update"]["transcript"][2]["content"]
                self.assertNotIn(future, json.dumps(packet, ensure_ascii=False))
            for forbidden in ("profile", "design_stratum", "expected_status", "reference_answer", "source_refs"):
                self.assertNotIn(forbidden, packet)

    def test_new_families_are_not_default_development(self):
        config = load_json(ROOT / "config/benchmark.json")
        self.assertNotIn(s37.CASES, config["multiturn_cases_paths"])
        self.assertTrue(all(r["case_path"] == s37.CASES for r in self.reservation["families"][3:]))

    def test_reference_answers_are_not_expected_judgment_controls(self):
        references = load_json(ROOT / s37.ANSWERS)
        self.assertEqual(references["status"], "author_examples_not_gold_not_development_controls")
        for row in references["answers"]:
            self.assertEqual(set(row), {"family_id", "variants"})
        self.assertFalse(set(s37.NEW_IDS) & {key.split("__")[0] for key in scoring.controls(ROOT)})

    def test_readiness_blocks_and_offline_snapshot_matches(self):
        from benchmark.run_guard_s37 import readiness
        self.assertFalse(readiness(ROOT)["live_ready"])
        self.assertEqual(s37.snapshot(ROOT), load_json(ROOT / s37.FREEZE))

    def test_public_audit_recomputes_exactly(self):
        self.assertEqual(s37.audit(ROOT), load_json(ROOT / "data/audit/s37_confirmation_summary.json"))


if __name__ == "__main__":
    unittest.main()
