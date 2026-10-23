import unittest

from benchmark.local_privacy_worklist import build_worklist, page_signals


class LocalPrivacyWorklistTests(unittest.TestCase):
    def test_signals_count_only_not_values(self):
        counts = page_signals("姓名 示例 2020-01-02 电话 12345678901")
        self.assertEqual(counts, {"identity_field": 1, "contact_field": 1,
                                  "date_like": 1, "long_digit_sequence": 1})

    def test_every_page_is_held_even_without_a_pattern(self):
        digest = "a" * 64
        intake = {"files": [{"sha256": digest, "path": "private.pdf", "pages": 2}]}
        ocr = [{"sha256": digest, "status": "raw_ocr_unreviewed_not_deidentified",
                "pages": [{"page": 1, "text": "姓名 示例"}, {"page": 2, "text": "no obvious ID"}]}]
        report = build_worklist(intake, ocr)
        self.assertEqual((report["file_count"], report["page_count"], report["pages_with_any_signal"]),
                         (1, 2, 1))
        self.assertTrue(all(entry["release_status"] == "hold_no_external_model_or_public_case"
                            for entry in report["entries"]))
        self.assertNotIn("示例", str(report))

    def test_hash_or_page_mismatch_is_rejected(self):
        digest = "a" * 64
        intake = {"files": [{"sha256": digest, "path": "private.pdf", "pages": 2}]}
        ocr = [{"sha256": digest, "status": "raw_ocr_unreviewed_not_deidentified",
                "pages": [{"page": 1, "text": "example"}]}]
        with self.assertRaisesRegex(ValueError, "page count"):
            build_worklist(intake, ocr)


if __name__ == "__main__":
    unittest.main()
