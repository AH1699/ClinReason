import unittest
from benchmark.local_lab_excerpt import select_cells


class LabExcerptTests(unittest.TestCase):
    def test_allowlist_masks_identifiers_dates_and_nonmatching_rows(self):
        boxes = [
            {"text": "钾", "bounds": [0.1,0.4,0.2,0.42]},
            {"text": "4.2", "bounds": [0.3,0.4,0.4,0.42]},
            {"text": "mmol/L", "bounds": [0.5,0.4,0.6,0.42]},
            {"text": "张某某", "bounds": [0.7,0.4,0.8,0.42]},
            {"text": "13800138000", "bounds": [0.7,0.4,0.8,0.42]},
            {"text": "2025-03-08", "bounds": [0.7,0.4,0.8,0.42]},
            {"text": "1234", "bounds": [0.3,0.1,0.4,0.12]},
        ]
        selected, rows = select_cells(boxes)
        self.assertEqual(selected, [0,1,2])
        self.assertEqual(rows[0]["analyte"], "potassium")

    def test_narrative_mentions_are_not_allowed_as_analyte_labels(self):
        selected, rows = select_cells([
            {"text":"患者钾偏低，联系家属", "bounds":[0.1,0.4,0.2,0.42]},
            {"text":"4.2", "bounds":[0.3,0.4,0.4,0.42]}])
        self.assertEqual((selected,rows), ([],[]))


if __name__ == "__main__":
    unittest.main()
