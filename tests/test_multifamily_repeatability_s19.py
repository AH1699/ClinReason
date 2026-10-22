import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmark.multifamily_repeatability_s19 import compare_cells, run


class MultifamilyRepeatabilityS19Tests(unittest.TestCase):
    def test_comparator_reports_non_ceiling_and_error_disagreement_without_rescoring(self):
        first = {}
        second = {}
        for family in ("HC-MT-TRIAGE-018", "HC-MT-TRIAGE-019"):
            for language in ("EN", "ZH-HANS"):
                for variant in ("safe", "partial", "unsafe"):
                    for judge in ("gemini", "grok"):
                        key = (f"{family}-{language}", variant, judge)
                        first[key] = {
                            "returned_model": judge, "criterion_statuses": ["met"] * 6,
                            "requirements": 4, "safety": 4, "revision": 4,
                            "critical_errors": [] if variant != "unsafe" else [("ERR", 1)],
                            "score": {"safe": 100, "partial": 65, "unsafe": 40}[variant],
                            "pass": variant == "safe", "human_review": False,
                        }
                        second[key] = dict(first[key])
        changed = next(key for key in first if key[1] == "unsafe")
        second[changed]["critical_errors"] = []
        second[changed]["score"] = 45
        result = compare_cells(first, second)
        self.assertEqual(result["cells"], 24)
        self.assertEqual(result["exact_score_repeats"], 23)
        self.assertEqual(result["critical_error_repeats"], 23)
        self.assertEqual(result["pass_repeats"], 24)

    def test_run_requires_exact_call_cap_before_any_source_or_api_access(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "--max-api-calls 24"):
                run(root, Path(directory) / "unused", env_file=root / ".env.local",
                    max_api_calls=25, timeout=240)


if __name__ == "__main__":
    unittest.main()
