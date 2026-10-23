import unittest
from benchmark.local_lab_excerpt import select_cells, unit_review_bounds


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

    def test_unit_review_stays_in_known_column_and_selected_rows(self):
        boxes=[{'text':'K','bounds':[.1,.4,.2,.42]},
               {'text':'4.2','bounds':[.3,.4,.4,.42]},
               {'text':'mmol/L','bounds':[.65,.4,.72,.42]}]
        selected,rows=select_cells(boxes)
        bounds=unit_review_bounds(boxes,selected,rows)
        self.assertEqual(len(bounds),1)
        x0,y0,x1,y1=bounds[0]
        self.assertGreater(x0,.6)
        self.assertLess(x1,.75)
        self.assertGreater(y0,.39)
        self.assertLess(y1,.43)
        self.assertEqual(unit_review_bounds(boxes,[],rows),[])
        wide=[{'text':'mmol/L','bounds':[.3,.4,.9,.42]}]
        self.assertEqual(unit_review_bounds(wide,[0],rows),[])


if __name__ == "__main__":
    unittest.main()
