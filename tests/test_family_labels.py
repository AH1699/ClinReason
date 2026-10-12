import json
import unittest
from collections import Counter, defaultdict
from pathlib import Path


class FamilyLabelTests(unittest.TestCase):
    def test_label_map_covers_only_complete_bilingual_families(self):
        root = Path(__file__).resolve().parents[1]
        cases = [json.loads(line) for line in (root / "data/alpha/global_core_cases.jsonl").read_text(encoding="utf-8").splitlines()]
        labels = json.loads((root / "data/alpha/family_labels.json").read_text(encoding="utf-8"))
        registry = json.loads((root / "data/evidence/public_sources.json").read_text(encoding="utf-8"))
        sources_by_url = {source["url"]: source for source in registry["sources"]}
        by_family = defaultdict(list)
        for case in cases:
            by_family[case["metadata"]["case_family_id"]].append(case)
        self.assertEqual(set(by_family), set(labels["families"]))
        self.assertEqual(len(by_family), 30)
        self.assertEqual(len(cases), 60)
        self.assertEqual(Counter(case["category"] for case in cases), {category: 10 for category in (
            "triage", "medication_safety", "patient_communication", "clinical_reasoning",
            "clinical_knowledge", "adversarial_safety",
        )})
        for family_id, family_cases in by_family.items():
            self.assertEqual({case["language"] for case in family_cases}, {"en", "zh-Hans"}, family_id)
            self.assertEqual(len(family_cases), 2, family_id)
            self.assertEqual(len({case["category"] for case in family_cases}), 1, family_id)
            error_signatures = [
                [(error["id"], error["severity"]) for error in case["critical_errors"]]
                for case in family_cases
            ]
            self.assertEqual(error_signatures[0], error_signatures[1], family_id)
            for case in family_cases:
                self.assertEqual(case["status"], "draft", family_id)
                self.assertFalse(case["metadata"]["clinician_validated"], family_id)
                for reference in case["metadata"]["source_refs"]:
                    url = "https://" + reference.split("https://", 1)[1]
                    self.assertIn(url, sources_by_url, (family_id, url))
                    self.assertIn(family_id, sources_by_url[url]["families"], (family_id, url))
            facets = labels["families"][family_id]
            self.assertEqual(set(facets), set(labels["axes"]))
            self.assertIn(facets["competency"], labels["axes"]["competency"])
            for axis in ("reasoning_operation", "failure_mode", "complexity"):
                self.assertTrue(facets[axis], (family_id, axis))
                self.assertEqual(len(facets[axis]), len(set(facets[axis])))
                self.assertLessEqual(set(facets[axis]), set(labels["axes"][axis]))


if __name__ == "__main__":
    unittest.main()
