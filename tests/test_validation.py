import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from benchmark.config import load_json
from benchmark.validation import validate_case, validate_dataset


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.config = load_json(cls.root / "config" / "benchmark.json")
        cls.rubric = load_json(cls.root / "config" / "rubric.json")
        cls.template = load_json(cls.root / "data" / "templates" / "case.template.json")

    def test_examples_are_development_valid_with_expected_warnings(self):
        result = validate_dataset(
            self.root / "data" / "examples" / "healthcare_cases.jsonl",
            self.rubric,
            self.config["authoring"],
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["case_count"], 6)
        self.assertEqual(result["error_count"], 0)
        self.assertGreater(result["warning_count"], 0)

    def test_unknown_dimension_is_an_error(self):
        case = deepcopy(self.template)
        case["applicable_dimensions"].append("not_in_rubric")
        issues = validate_case(case, self.rubric, self.config["authoring"])
        self.assertIn("UNKNOWN_DIMENSION", {issue["code"] for issue in issues})

    def test_unknown_category_is_an_error(self):
        case = deepcopy(self.template)
        case["category"] = "not_in_taxonomy"
        issues = validate_case(case, self.rubric, self.config["authoring"])
        self.assertIn("UNKNOWN_CATEGORY", {issue["code"] for issue in issues})

    def test_release_mode_rejects_unvalidated_template(self):
        issues = validate_case(
            self.template,
            self.rubric,
            self.config["authoring"],
            release_ready=True,
        )
        codes = {issue["code"] for issue in issues}
        self.assertIn("NOT_RELEASE_VALIDATED", codes)
        self.assertIn("MISSING_SOURCES", codes)
        self.assertIn("MISSING_REVIEWERS", codes)

    def test_duplicate_case_version_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            encoded = json.dumps(self.template)
            path.write_text(f"{encoded}\n{encoded}\n", encoding="utf-8")
            result = validate_dataset(
                path, self.rubric, self.config["authoring"]
            )
        self.assertFalse(result["valid"])
        self.assertIn(
            "DUPLICATE_CASE_VERSION", {issue["code"] for issue in result["issues"]}
        )

    def test_empty_dataset_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.jsonl"
            path.write_text("", encoding="utf-8")
            result = validate_dataset(
                path, self.rubric, self.config["authoring"]
            )
        self.assertFalse(result["valid"])
        self.assertIn("EMPTY_DATASET", {issue["code"] for issue in result["issues"]})

    def test_complete_bilingual_family_can_be_release_ready(self):
        english = deepcopy(self.template)
        chinese = deepcopy(self.template)
        for case, case_id, language, locale in (
            (english, "HC-CATEGORY-001-EN", "en", "en-US"),
            (chinese, "HC-CATEGORY-001-ZH-CN", "zh-CN", "zh-CN"),
        ):
            case["id"] = case_id
            case["language"] = language
            case["status"] = "clinician_validated"
            case["metadata"]["locale"] = locale
            case["metadata"]["clinician_validated"] = True
            case["metadata"]["source_refs"] = ["Example authoritative source citation"]
            case["metadata"]["reviewer_ids"] = ["reviewer_01", "reviewer_02"]
            case["metadata"]["jurisdiction"] = "Example jurisdiction"
        chinese["prompt"] = "用于测试的合成场景。"
        chinese["reference_answer"] = "替换为经过临床审核的预期行为。"
        chinese["critical_requirements"] = ["替换为可观察的要求"]
        chinese["critical_errors"][0]["description"] = "替换为案例特定的禁止错误。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paired.jsonl"
            path.write_text(
                "\n".join(json.dumps(case, ensure_ascii=False) for case in (english, chinese))
                + "\n",
                encoding="utf-8",
            )
            result = validate_dataset(
                path,
                self.rubric,
                self.config["authoring"],
                release_ready=True,
            )
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual(result["family_count"], 1)


if __name__ == "__main__":
    unittest.main()
