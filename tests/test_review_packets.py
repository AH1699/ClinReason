import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.config import load_jsonl
from benchmark.review_packets import export_review_packets
from benchmark.reviews import case_content_hash


class ReviewPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.cases = load_jsonl(root / "data" / "alpha" / "global_core_cases.jsonl")

    def test_exports_complete_bilingual_packets_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "packets"
            manifest = export_review_packets(self.cases, target)
            self.assertEqual(manifest["family_count"], 30)
            self.assertEqual(manifest["case_count"], 60)
            self.assertEqual(len(list(target.glob("*.md"))), 30)
            first = manifest["families"][0]
            self.assertEqual({item["language"] for item in first["cases"]}, {"en", "zh-Hans"})
            by_id = {case["id"]: case for case in self.cases}
            for item in first["cases"]:
                self.assertEqual(item["case_content_hash"], case_content_hash(by_id[item["case_id"]]))
            packet = (target / first["packet"]).read_text(encoding="utf-8")
            self.assertIn(first["cases"][0]["case_id"], packet)
            self.assertIn(first["cases"][1]["case_id"], packet)
            with self.assertRaises(FileExistsError):
                export_review_packets(self.cases, target)

    def test_refuses_gold_case_export(self):
        cases = deepcopy(self.cases)
        cases[0]["status"] = "gold"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                export_review_packets(cases, Path(directory) / "packets")


if __name__ == "__main__":
    unittest.main()
