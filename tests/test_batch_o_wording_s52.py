from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts import batch_o_wording_s52 as run

ROOT = Path(__file__).resolve().parents[1]


class WordingTests(unittest.TestCase):
    def setUp(self):
        self.data = run.batch.load_json(ROOT / run.DATA)
        self.dataset, self.anchors, self.packets, self.hypotheses = run.materialize(ROOT)

    def test_original_cases_unchanged_except_version_and_two_derived_requirements(self):
        original = run.batch.load_json(ROOT / run.batch.FILES["cases"])
        derived = deepcopy(self.dataset)
        for a, b in zip(derived["families"], original["families"]):
            self.assertEqual(a["version"], "0.2.0")
            a["version"] = b["version"]
            for lang in ("en", "zh-Hans"):
                self.assertNotEqual(a["variants"][lang]["turns"][1]["critical_requirements"][2],
                                    b["variants"][lang]["turns"][1]["critical_requirements"][2])
                a["variants"][lang]["turns"][1]["critical_requirements"][2] = b["variants"][lang]["turns"][1]["critical_requirements"][2]
        self.assertEqual(derived, original)

    def test_only_two_anchors_changed(self):
        original = run.batch.load_json(ROOT / run.batch.FILES["anchors"])
        derived = deepcopy(self.anchors)
        derived["scope"] = original["scope"]
        for a, b in zip(derived["families"], original["families"]):
            a["case_hashes"] = b["case_hashes"]
            self.assertNotEqual(a["stages"]["update"][2], b["stages"]["update"][2])
            a["stages"]["update"][2] = b["stages"]["update"][2]
        self.assertEqual(derived, original)

    def test_18_bilingual_packets_have_no_author_expectations(self):
        self.assertEqual(len(self.packets), 18)
        for key, packet in self.packets.items():
            self.assertEqual(packet["scoring_stage"], "update")
            self.assertEqual(len(packet["criterion_anchors"]), 3)
            self.assertEqual([r["stage_id"] for r in packet["turn_labels"]], ["update"])
            serialized = json.dumps(packet)
            for hidden in ("expected_status", "author_hypotheses", "replacement", "review_issue", "human_review_resolved"):
                self.assertNotIn('"' + hidden + '"', serialized)
            self.assertNotIn('"profile"', serialized)
            counterpart = key.replace("__en__", "__zh-Hans__")
            self.assertEqual(self.hypotheses[key], self.hypotheses[counterpart])

    def test_controls_preserve_initial_and_first_two_update_components(self):
        original = run.batch.load_json(ROOT / run.batch.FILES["controls"])
        for key, packet in self.packets.items():
            fid, lang, profile = key.split("__")
            probe = next(p for p in original["probes"] if (p["family_id"],p["language"]) == (fid,lang))
            self.assertEqual(packet["transcript"][1]["content"], probe["initial_response"])
            prefix = probe["construction"]["component_separator"].join(probe["construction"]["safe_components"][:2])
            self.assertTrue(packet["transcript"][3]["content"].startswith(prefix))
            if profile == "baseline":
                self.assertEqual(packet["transcript"][3]["content"], run.batch.materialize_probe(probe)["safe_update_response"])

    def test_stale_binding_or_review_rejected(self):
        self.data["decisions"][0]["binding"]["anchor_sha256"] = "0"*64
        with self.assertRaises(ValueError): run.materialize(ROOT, self.data)
        self.data = run.batch.load_json(ROOT / run.DATA)
        self.data["original_review_sha256"] = "0"*64
        with self.assertRaises(ValueError): run.materialize(ROOT, self.data)

    def test_cannot_promote_to_default_or_resolve_human_review(self):
        for key in ("default_enabled", "numeric_scores"):
            value = deepcopy(self.data); value[key] = True
            with self.assertRaises(ValueError): run.materialize(ROOT, value)
        self.data["decisions"][0]["human_review_resolved"] = True
        with self.assertRaises(ValueError): run.materialize(ROOT, self.data)

    def test_missing_duplicate_control_or_translation_rejected(self):
        for change in (lambda d: d["decisions"].pop(),
                       lambda d: d["decisions"][0]["controls"].pop(),
                       lambda d: d["decisions"][0]["controls"][1]["replacement"].pop("zh-Hans"),
                       lambda d: d["decisions"].append(deepcopy(d["decisions"][0]))):
            value = deepcopy(self.data); change(value)
            with self.assertRaises(ValueError): run.materialize(ROOT, value)

    def test_no_case_count_inflation_or_numeric_scores(self):
        result = run.audit(ROOT)
        self.assertEqual(result["new_families"], 0)
        self.assertEqual(result["changed_criterion_positions"], 2)
        self.assertEqual(result["remaining_component_or_alternative_positions"], 10)
        self.assertEqual(result["live_calls"], 0)
        self.assertFalse(result["numeric_scores"])


if __name__ == "__main__":
    unittest.main()
