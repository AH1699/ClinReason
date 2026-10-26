"""Prospective instruction checks against unchanged local acceptance."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts import judge_evidence_s56 as draft
from tests.test_scoring_s36 import judgment

ROOT = Path(__file__).resolve().parents[1]
score = draft.score


def without_descriptions(value):
    if isinstance(value, dict):
        return {k: without_descriptions(v) for k, v in value.items() if k != "description"}
    if isinstance(value, list):
        return [without_descriptions(v) for v in value]
    return value


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controls = score.controls(ROOT)

    def packets(self):
        for full, levels in self.controls.values():
            for stage in score.STAGES:
                yield score.stage_packet(full, stage, levels)

    def test_all_36_control_packets_have_per_criterion_status_contract(self):
        for packet in self.packets():
            before = deepcopy(packet)
            rules = draft.contract(packet)
            self.assertEqual(len(rules), len(packet["criterion_anchors"]))
            for rule in rules:
                for status, required in rule["nonblank_quote_required"].items():
                    value = judgment(packet)
                    value["criterion_assessments"][rule["requirement_index"] - 1].update(
                        status=status, response_evidence="")
                    if required:
                        with self.assertRaises(score.JudgmentFailure): draft.validate(value, packet)
                    else:
                        draft.validate(value, packet)
            self.assertEqual(before, packet)

    def test_schema_shape_unchanged_only_description_added(self):
        for packet in self.packets():
            self.assertEqual(without_descriptions(draft.schema(packet)),
                             without_descriptions(draft.prior.schema(packet)))
            description = draft.schema(packet)["properties"]["criterion_assessments"]["items"]["properties"]["response_evidence"]["description"]
            self.assertIn(json.dumps(draft.contract(packet), ensure_ascii=False), description)

    def test_previous_instructions_retained_and_table_explicit(self):
        for packet in self.packets():
            text = draft.instruction(ROOT, packet)
            self.assertTrue(text.startswith(draft.prior.instruction(ROOT, packet)))
            self.assertIn(json.dumps({"version": draft.VERSION, "criteria": draft.contract(packet)}, ensure_ascii=False), text)
            self.assertIn("not a target status", text)
            self.assertIn("'Do not ' is NOT", text)

    def test_prefix_and_whitespace_are_literal_for_both_languages_and_stages(self):
        for language in ("en", "zh-Hans"):
            full, levels = self.controls[f"HC-MT-REASON-020__{language}__safe"]
            for stage in score.STAGES:
                for prefix in ("Does not ", "Avoids ", "Do not ", "does not ", " Does not ", "Never ", "不建议"):
                    packet = score.stage_packet(full, stage, levels)
                    packet["criterion_anchors"][0]["met"] = prefix + "fixture"
                    for status in ("met", "partial", "missed", "unclear"):
                        required = status == "partial" or (status == "met" and prefix not in ("Does not ", "Avoids "))
                        self.assertEqual(draft.contract(packet)[0]["nonblank_quote_required"][status], required)
                        value = judgment(packet)
                        value["criterion_assessments"][0].update(status=status, response_evidence=" ")
                        # Required means nonblank, not merely a nonempty string.
                        if required:
                            with self.assertRaises(score.JudgmentFailure): draft.validate(value, packet)

    def test_s55_failure_remains_rejected_not_repaired(self):
        for language in ("en", "zh-Hans"):
            full, levels = self.controls[f"HC-MT-REASON-020__{language}__safe"]
            packet = score.stage_packet(full, "update", levels)
            self.assertTrue(draft.contract(packet)[3]["nonblank_quote_required"]["met"])
            value = judgment(packet)
            value["criterion_assessments"][3]["response_evidence"] = ""
            before = deepcopy(value)
            with self.assertRaises(score.JudgmentFailure): draft.validate(value, packet)
            self.assertEqual(before, value)

    def test_missing_reordered_duplicate_and_extra_criteria_rejected(self):
        packet = next(self.packets())
        for kind in ("missing", "duplicate", "reordered", "extra"):
            value = judgment(packet)
            rows = value["criterion_assessments"]
            if kind == "missing": rows.pop()
            elif kind == "duplicate": rows[1] = deepcopy(rows[0])
            elif kind == "reordered": rows.reverse()
            else: rows.append(deepcopy(rows[0]))
            with self.assertRaises(score.JudgmentFailure): draft.validate(value, packet)

    def test_wrong_turn_user_spliced_and_paraphrased_quotes_still_rejected(self):
        for language in ("en", "zh-Hans"):
            full, levels = self.controls[f"HC-MT-REASON-020__{language}__safe"]
            packet = score.stage_packet(full, "update", levels)
            for quote in (packet["transcript"][0]["content"], packet["transcript"][1]["content"],
                          packet["transcript"][2]["content"], "Start ... End invented stitch", "Invented paraphrase"):
                value = judgment(packet)
                value["criterion_assessments"][0]["response_evidence"] = quote
                with self.assertRaises(score.JudgmentFailure): draft.validate(value, packet)

    def test_observation_exception_does_not_waive_explanations(self):
        full, levels = self.controls["HC-MT-REASON-020__en__safe"]
        packet = score.stage_packet(full, "update", levels)
        value = judgment(packet)
        draft.validate(value, packet)
        for index, field in ((0, "overlap_note"), (1, "overlap_note"), (1, "new_fact")):
            changed = deepcopy(value)
            changed["dimension_observations"][index][field] = ""
            with self.assertRaises(score.JudgmentFailure): draft.validate(changed, packet)
        for observation in value["dimension_observations"]:
            observation["response_evidence"] = full["transcript"][1]["content"]
        draft.validate(value, packet)


if __name__ == "__main__":
    unittest.main()
