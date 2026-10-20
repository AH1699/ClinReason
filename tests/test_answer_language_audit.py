"""Conservative offline script flags; not bilingual or clinical approval."""

import json
import tempfile
import unittest
from pathlib import Path

from benchmark.answer_language_audit import audit_saved_answer_languages
from benchmark.config import load_json
from benchmark.multiturn import variant_hash, variant_id


class AnswerLanguageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.family = load_json(cls.root / "data/multiturn/batch_g_cases.json")["families"][0]

    def _row(self, language, initial, update):
        return {
            "case_id": variant_id(self.family, language),
            "case_content_hash": variant_hash(self.family, language),
            "model_id": "fixture-model",
            "turn_outputs": [
                {"stage_id": "initial", "text": initial},
                {"stage_id": "update", "text": update},
            ],
        }

    def test_flags_obvious_wrong_script_but_not_chinese_response(self):
        english = "This is a sufficiently long English response with many words about checking new symptoms and seeking local help if needed. The person should also explain the history clearly and ask a qualified professional about the situation."
        chinese = "这是一个中文回答，说明需要根据新症状重新评估，并在危险信号出现时求助。"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "answers.jsonl"
            path.write_text(json.dumps(self._row("zh-Hans", english, chinese)) + "\n", encoding="utf-8")
            report = audit_saved_answer_languages(self.root, [path])
        self.assertEqual((report["answer_count"], report["checked_turn_count"]), (1, 2))
        self.assertEqual(len(report["flags"]), 1)
        self.assertEqual(report["flags"][0]["stage_id"], "initial")
        self.assertEqual(report["flags"][0]["reason"], "zh_expected_english_script_dominant")

    def test_rejects_wrong_case_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "answers.jsonl"
            row = self._row("en", "A full response with clinical reasoning.", "A later response with clinical reasoning.")
            row["case_content_hash"] = "not-the-case-hash"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                audit_saved_answer_languages(self.root, [path])


if __name__ == "__main__":
    unittest.main()
