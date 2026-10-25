"""Offline draft regression: explanations explicit, scoring acceptance unchanged."""

from copy import deepcopy
from pathlib import Path
import unittest

from scripts import judge_observation_draft as draft
from benchmark import workflow_s38 as workflow

ROOT = Path(__file__).resolve().parents[1]


class ObservationDraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog, controls, answers = workflow.families(ROOT), workflow.score.controls(ROOT), {}
        cls.packets = {}
        for stage in ("initial", "update"):
            row = next(r for r in workflow.schedule(ROOT) if r["block"] == "control"
                       and r["stage"] == stage and r["model"] == "gemini-3.8-flash")
            cls.packets[stage] = workflow.request_context(ROOT, row, catalog, controls, answers)["packet"]

    def test_initial_schema_and_instruction_unchanged(self):
        packet = self.packets["initial"]
        self.assertEqual(draft.schema(packet), draft.score.schema(packet))
        self.assertEqual(draft.instruction(ROOT, packet), draft.score.instruction(ROOT, packet))

    def test_only_update_field_descriptions_change(self):
        packet = self.packets["update"]; original = draft.score.schema(packet)
        changed = draft.schema(packet)
        fields = changed["properties"]["dimension_observations"]["items"]["properties"]
        for name in ("overlap_note", "new_fact", "independent_consequence_or_failure", "response_evidence"):
            self.assertTrue(fields[name].pop("description"))
        self.assertEqual(changed, original)
        self.assertEqual(draft.score.schema(packet), original)

    def test_live_failure_shape_names_all_three_required_blanks(self):
        value = {"dimension_observations": [dict(dimension=d, decision="no_distinct_failure",
                 response_evidence="", new_fact="", independent_consequence_or_failure="", overlap_note="")
                 for d in ("safety", "revision")]}
        before = deepcopy(value)
        self.assertEqual(draft.missing_observation_fields(value, self.packets["update"]), [
            "dimension_observations[0].overlap_note", "dimension_observations[1].overlap_note",
            "dimension_observations[1].new_fact"])
        self.assertEqual(value, before)

    def test_no_failure_still_needs_explanations_not_fabricated_quotes(self):
        value = {"dimension_observations": [dict(dimension=d, decision="no_distinct_failure",
                 response_evidence="", new_fact="New fact" if d == "revision" else "",
                 independent_consequence_or_failure="", overlap_note="No independent omission")
                 for d in ("safety", "revision")]}
        self.assertEqual(draft.missing_observation_fields(value, self.packets["update"]), [])
        value["dimension_observations"][0]["decision"] = "distinct_failure"
        self.assertEqual(draft.missing_observation_fields(value, self.packets["update"]), [
            "dimension_observations[0].independent_consequence_or_failure"])

    def test_whitespace_is_missing_and_initial_has_no_observations(self):
        value = {"dimension_observations": [{"overlap_note": " \n"}, {"overlap_note": "ok", "new_fact": "\t"}]}
        self.assertEqual(len(draft.missing_observation_fields(value, self.packets["update"])), 2)
        self.assertEqual(draft.missing_observation_fields(value, self.packets["initial"]), [])

    def test_existing_rejection_not_repaired(self):
        for packet in self.packets.values():
            with self.assertRaises(draft.score.JudgmentFailure):
                draft.validate({}, packet)
        text = draft.instruction(ROOT, self.packets["update"])
        self.assertIn("no_distinct_failure", text)
        self.assertIn("Do not invent a failure", text)


if __name__ == "__main__":
    unittest.main()
