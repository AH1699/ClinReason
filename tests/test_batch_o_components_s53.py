from copy import deepcopy
import json
from pathlib import Path
import unittest
from scripts import batch_o_components_s53 as run

ROOT = Path(__file__).resolve().parents[1]


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.value = run.batch.load_json(ROOT / run.DATA)
        self.packets, self.records = run.materialize(ROOT)

    def test_all_twelve_positions_and_counts_not_new_cases(self):
        result = run.audit(ROOT)
        self.assertEqual(result["criterion_positions_covered"], 12)
        self.assertEqual(result["new_targeted_control_records"], 54)
        self.assertEqual(result["total_targeted_control_records"], 72)
        self.assertEqual(result["unique_blinded_packets"], 58)
        self.assertEqual(result["exploratory_unlabelled_records"], 8)
        self.assertEqual(result["author_hypotheses"], 64)
        self.assertEqual(result["new_families"], 0)
        self.assertFalse(result["numeric_scores"])

    def test_all_s52_packets_remain_exactly_present(self):
        _, _, originals, _ = run.wording.materialize(ROOT)
        for packet in originals.values():
            self.assertEqual(self.packets[run.batch.sha256_json(packet)], packet)

    def test_blinded_packets_exclude_metadata_and_initial_excludes_update(self):
        for packet in self.packets.values():
            data = json.dumps(packet)
            for name in ("control_id", "author_status", "expected_status", "base_override", "source", "review_question_en"):
                self.assertNotIn('"' + name + '"', data)
            if packet["scoring_stage"] == "initial":
                self.assertEqual(len(packet["transcript"]), 2)
                self.assertEqual([r["stage_id"] for r in packet["turn_labels"]], ["initial"])

    def test_language_pairs_share_expectations(self):
        for record in self.records:
            key = (record["family_id"], record["stage"], record["requirement_index"])
            counterpart = record["control_id"].replace("__en__", "__zh-Hans__") if record["source"] == "s52" else record["control_id"].removesuffix("__en") + "__zh-Hans"
            if record["language"] != "en": continue
            other = next(r for r in self.records if r["control_id"] == counterpart)
            self.assertEqual(record["author_status"], other["author_status"])
            self.assertEqual(key, (other["family_id"], other["stage"], other["requirement_index"]))

    def test_each_contrast_changes_only_target_component_relative_to_declared_baseline(self):
        probes = run.batch.load_json(ROOT / run.batch.FILES["controls"])["probes"]
        for group in self.value["groups"]:
            fid, stage, index = group["family_id"], group["stage"], group["requirement_index"]
            for lang in ("en", "zh-Hans"):
                probe = next(p for p in probes if (p["family_id"],p["language"]) == (fid,lang))
                base = deepcopy(self.value["initial_components"][fid][lang] if stage == "initial" else probe["construction"]["safe_components"])
                if group["base_override"]: base[1] = group["base_override"]["replacement"][lang]
                for control in group["controls"]:
                    parts = deepcopy(base)
                    if control["replacement"]: parts[index-1] = control["replacement"][lang]
                    self.assertEqual(sum(a != b for a,b in zip(base,parts)), int(control["id"] != "baseline"))
                    identifier = "__".join((fid,stage,str(index),control["id"],lang))
                    row = next(r for r in self.records if r["control_id"] == identifier)
                    packet = self.packets[row["packet_sha256"]]
                    self.assertEqual(packet["transcript"][-1]["content"], probe["construction"]["component_separator"].join(parts))

    def test_exploratory_records_cannot_silently_acquire_labels(self):
        for group in self.value["groups"]:
            for control in group["controls"]:
                if control["expected_status"] is None:
                    control["expected_status"] = "partial"
                    with self.assertRaises(ValueError): run.materialize(ROOT, self.value)
                    return
        self.fail("Expected unlabelled contrasts")

    def test_stale_binding_missing_group_duplicate_and_missing_translation_rejected(self):
        for change in (lambda x: x["groups"][0]["binding"].update(anchor_sha256="0"*64),
                       lambda x: x["groups"].pop(),
                       lambda x: x["groups"].append(deepcopy(x["groups"][0])),
                       lambda x: x["groups"][0]["controls"][1]["replacement"].pop("zh-Hans")):
            value = deepcopy(self.value); change(value)
            with self.assertRaises(ValueError): run.materialize(ROOT, value)

    def test_initial_reference_must_reconstruct_original(self):
        self.value["initial_components"][run.HF]["en"][0] += "changed"
        with self.assertRaises(ValueError): run.materialize(ROOT, self.value)

    def test_neutral_monitoring_baseline_is_explicit_and_scoped(self):
        target = next(g for g in self.value["groups"] if (g["family_id"],g["stage"],g["requirement_index"]) == (run.HF,"update",1))
        target["base_override"]["component_index"] = 3
        with self.assertRaises(ValueError): run.materialize(ROOT, self.value)

    def test_no_default_adoption_or_numeric_scores(self):
        for key in ("default_enabled", "numeric_scores"):
            value = deepcopy(self.value); value[key] = True
            with self.assertRaises(ValueError): run.materialize(ROOT, value)


if __name__ == "__main__": unittest.main()
