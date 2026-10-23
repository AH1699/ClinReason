import math
import re
import unittest
from pathlib import Path

from benchmark.config import load_json
from benchmark.multiturn import validate_multiturn_dataset

ROOT = Path(__file__).resolve().parents[1]


class BatchNSourceTests(unittest.TestCase):
    def setUp(self):
        self.batch = load_json(ROOT / "data/multiturn/batch_n_cases.json")
        self.ledger = load_json(ROOT / "data/multiturn/batch_n_provenance.json")
        self.family = self.batch["families"][0]
        self.record = self.ledger["records"][0]

    def test_bilingual_unreviewed_development_only(self):
        result = validate_multiturn_dataset(self.batch)
        self.assertEqual((result["family_count"], result["variant_count"]), (1, 2))
        self.assertFalse(result["clinical_review_complete"])
        self.assertFalse(result["language_review_complete"])
        self.assertEqual(self.ledger["split"], "public_development_not_calibration_or_gold")
        self.assertEqual(self.record["family_id"], self.family["family_id"])

    def test_all_seven_requirement_positions_have_source_mapping(self):
        wanted = [(t["stage_id"], i) for t in self.family["variants"]["en"]["turns"]
                  for i in range(1, len(t["critical_requirements"]) + 1)]
        self.assertEqual(len(wanted), 7)
        self.assertEqual([(r["stage"], r["index"]) for r in self.record["requirement_support"]], wanted)
        self.assertEqual(set(self.family["source_refs"]), set(self.record["supporting_sources"]))
        for row in self.record["requirement_support"]:
            self.assertIn(row["guidance_url"], self.family["source_refs"])
            self.assertTrue(row["basis"])
        for en, zh in zip(self.family["variants"]["en"]["turns"], self.family["variants"]["zh-Hans"]["turns"]):
            self.assertEqual(len(en["critical_requirements"]), len(zh["critical_requirements"]))

    def test_paired_numbers_units_and_blood_gas_arithmetic(self):
        for i, row in enumerate(self.record["synthetic_numeric_checks"]):
            en = self.family["variants"]["en"]["turns"][i]["user"]
            zh = self.family["variants"]["zh-Hans"]["turns"][i]["user"]
            self.assertEqual(re.findall(r"\d+(?:\.\d+)?", en), re.findall(r"\d+(?:\.\d+)?", zh))
            for key, unit in (("salicylate_mg_dl", "mg/dL"), ("paco2_mm_hg", "mmHg"),
                              ("bicarbonate_mmol_l", "mmol/L")):
                for text in (en, zh):
                    self.assertIn(f"{row[key]} {unit}", text)
            calculated = 6.1 + math.log10(row["bicarbonate_mmol_l"] / (0.03 * row["paco2_mm_hg"]))
            self.assertAlmostEqual(row["ph"], calculated, delta=0.01)
        # Numerical consistency is not clinical validation of these authored values.

    def test_purchased_locator_and_source_limits_are_explicit(self):
        self.assertEqual(self.record["pdf_pages_one_based"], [24, 25])
        self.assertIn("distractor explanation", self.record["inspiration_scope"])
        self.assertIn("not a source salicylate patient record", self.record["inspiration_scope"])
        self.assertTrue(self.record["critical_error_basis"])
        self.assertTrue(self.record["review_questions"])
        self.assertFalse(any("cgo.mod.uk" in url or "PMC4371029" in url for url in self.family["source_refs"]))

    def test_related_construct_is_grouped_not_claimed_independent(self):
        queue = load_json(ROOT / "data/audit/overlap_and_source_review.json")
        pair = next(p for p in queue["overlaps"] if set(p["family_ids"]) ==
                    {"HC-MT-MEDSAFE-019", "HC-MT-MEDSAFE-018"})
        self.assertTrue(pair["split_together"])
        self.assertEqual(pair["relationship"], "possible_construct_duplicate")


if __name__ == "__main__":
    unittest.main()
