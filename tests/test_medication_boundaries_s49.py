"""Offline contrast integrity, not clinical or judge agreement tests."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from scripts import medication_boundaries_s49 as draft

ROOT = Path(__file__).resolve().parents[1]


class BoundaryTests(unittest.TestCase):
    def test_counts_and_limits(self):
        result = draft.audit(ROOT)
        self.assertEqual((result["packets"], result["author_hypotheses"], result["unlabelled_packets"], result["one_component_contrasts"]), (28,16,12,22))
        self.assertEqual(result["live_calls"], 0)
        self.assertFalse(result["judge_boundary_accuracy_measured"])
        self.assertFalse(result["existing_labels_changed"])
        self.assertEqual(result, json.loads((ROOT / "data/audit/s49_medication_boundaries_summary.json").read_text()))

    def test_all_profiles_are_bilingual_and_targeted(self):
        value, _, _ = draft.load(ROOT); packets = draft.packets(ROOT)
        for p in value["profiles"]:
            for lang in draft.LANGS:
                packet = packets[p["id"] + "__" + lang]
                self.assertEqual(packet["language"], lang)
                self.assertEqual(len(packet["target_requirements"]), 1)
                self.assertEqual(packet["target_requirements"][0]["requirement_index"], p["requirement_index"])
                self.assertEqual(packet["scoring_stage"], p["stage"])

    def test_no_profile_or_hypothesis_leak(self):
        value, _, _ = draft.load(ROOT)
        for packet in draft.packets(ROOT).values():
            text = json.dumps(packet)
            for key in ("author_hypothesis", "candidate_model", "review_questions", "H140", "H137", "H136"):
                self.assertNotIn(key, text)
            for profile in value["profiles"]: self.assertNotIn(profile["id"], text)

    def test_initial_stage_cannot_see_future_turn(self):
        baseline = draft.packets(ROOT)
        value, family, anchors = draft.load(ROOT)
        for lang in draft.LANGS:
            value["common"]["update_base"][lang] = "FUTURE_ANSWER_SENTINEL"
        with patch.object(draft, "load", return_value=(value, family, anchors)):
            changed = draft.packets(ROOT)
        for key, packet in baseline.items():
            if packet["scoring_stage"] != "initial": continue
            self.assertEqual(len(packet["transcript"]), 2)
            self.assertEqual(changed[key]["transcript"], packet["transcript"])
            self.assertNotIn("FUTURE", json.dumps(changed[key]))
            future_user = family["variants"][packet["language"]]["turns"][1]["user"]
            self.assertNotIn(future_user, [t["content"] for t in packet["transcript"]])

    def test_initial_only_hold_does_not_change_update(self):
        packets = draft.packets(ROOT)
        for lang in draft.LANGS:
            a = packets["no_update_action__"+lang]["transcript"]
            b = packets["initial_only_hold__"+lang]["transcript"]
            self.assertNotEqual(a[1], b[1])
            self.assertEqual(a[3], b[3])
            self.assertEqual(a[0], b[0]); self.assertEqual(a[2], b[2])

    def test_ambiguous_profiles_remain_unlabelled(self):
        value, _, _ = draft.load(ROOT)
        held = {p["id"] for p in value["profiles"] if p["author_hypothesis"] is None}
        self.assertEqual(held, {"no_addition", "no_increase", "ambiguous_reference", "clinician_ketone_only", "clinician_hold_only", "generic_plan_plus_direct_actions"})

    def test_nonisolated_contrast_is_rejected(self):
        loaded = deepcopy(draft.load(ROOT))
        p = next(p for p in loaded[0]["profiles"] if p["id"] == "no_addition")
        p["components"]["initial_hold"] = True
        with patch.object(draft, "load", return_value=loaded):
            with self.assertRaises(ValueError): draft.audit(ROOT)

    def test_existing_anchors_remain_exact(self):
        _, family, anchors = draft.load(ROOT)
        p = draft.packets(ROOT)["explicit_hold__en"]
        full = draft.workflow.full_packet(family, anchors, "en", "initial fixture", "update fixture")
        expected = next(a for a in full["criterion_anchors"] if a["stage_id"] == "update" and a["requirement_index"] == 3)
        self.assertEqual(p["target_requirements"], [expected])


if __name__ == "__main__":
    unittest.main()
