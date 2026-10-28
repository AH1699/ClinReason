from copy import deepcopy
from pathlib import Path
import unittest

from scripts import evidence_refs_s64 as draft
from tests.test_scoring_s36 import judgment

ROOT = Path(__file__).resolve().parents[1]


def fixture(packet, status="met"):
    """Mechanical adapter for tests only, not a mapping of historical quotes."""
    value = judgment(packet, status)
    catalog = draft.catalog(packet)
    current = 1 if packet["scoring_stage"] == "initial" else 2
    spans = [s for s in catalog["spans"] if s["assistant_turn"] == current]
    value["packet_sha256"] = catalog["packet_sha256"]
    for field in ("criterion_assessments", "dimension_observations"):
        for row in value.get(field, []):
            quote = row.pop("response_evidence")
            row["response_evidence_ref"] = {"first": spans[0]["id"], "last": spans[-1]["id"]} if quote else None
    return value


class EvidenceRefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controls = draft.score.controls(ROOT)

    def setUp(self):
        full, levels = self.controls["HC-MT-REASON-020__en__safe"]
        self.packet = draft.score.stage_packet(full, "update", levels)

    def test_all_36_bilingual_stage_controls_lossless_and_unchanged(self):
        for full, levels in self.controls.values():
            for stage in draft.score.STAGES:
                packet = draft.score.stage_packet(full, stage, levels)
                original = deepcopy(packet)
                value = fixture(packet)
                before = deepcopy(value)
                self.assertEqual(draft.resolve(value, packet), judgment(packet))
                self.assertEqual(value, before)
                self.assertEqual(packet, original)
                for index in range(1, len(packet["transcript"]), 2):
                    spans = [s for s in draft.catalog(packet)["spans"] if s["assistant_turn"] == (index+1)//2]
                    self.assertEqual("".join(s["text"] for s in spans), packet["transcript"][index]["content"])

    def test_unicode_whitespace_long_chunks_and_repeated_text(self):
        text = "\n。💊e\u0301！\r\n" + "甲"*501 + "?same!same!\nend"
        self.packet["transcript"][3]["content"] = text
        spans = [s for s in draft.catalog(self.packet)["spans"] if s["assistant_turn"] == 2]
        self.assertEqual("".join(s["text"] for s in spans), text)
        self.assertEqual(len({s["id"] for s in spans}), len(spans))
        self.assertTrue(all(0 < len(s["text"]) <= draft.CHUNK_CHARS for s in spans))
        self.assertEqual(draft.resolve(fixture(self.packet), self.packet), judgment(self.packet))

    def test_each_chunk_and_contiguous_range_resolves_exactly(self):
        spans = [s for s in draft.catalog(self.packet)["spans"] if s["assistant_turn"] == 2]
        for first in spans:
            value = fixture(self.packet)
            value["criterion_assessments"][0]["response_evidence_ref"] = {"first": first["id"], "last": spans[-1]["id"]}
            result = draft.resolve(value, self.packet)
            self.assertEqual(result["criterion_assessments"][0]["response_evidence"],
                             self.packet["transcript"][3]["content"][first["start"]:])

    def test_wrong_turn_cross_turn_reverse_unknown_and_malformed(self):
        spans = draft.catalog(self.packet)["spans"]
        early = [s for s in spans if s["assistant_turn"] == 1]
        late = [s for s in spans if s["assistant_turn"] == 2]
        cases = [[], "text", {}, {"first": [] , "last": late[0]["id"]},
                 {"first": "invented", "last": late[0]["id"]},
                 {"first": early[0]["id"], "last": early[-1]["id"]},
                 {"first": early[0]["id"], "last": late[-1]["id"]},
                 {"first": late[-1]["id"], "last": late[0]["id"]},
                 {"first": late[0]["id"], "last": late[0]["id"], "text": "fabrication"}]
        for ref in cases:
            value = fixture(self.packet); value["criterion_assessments"][0]["response_evidence_ref"] = ref
            with self.subTest(ref=ref), self.assertRaises(draft.score.JudgmentFailure):
                draft.resolve(value, self.packet)

    def test_other_packet_source_case_language_and_anchor_drift(self):
        value = fixture(self.packet)
        for field in ("answer", "case_id", "language", "anchor"):
            packet = deepcopy(self.packet)
            if field == "answer": packet["transcript"][3]["content"] += " changed"
            elif field == "anchor": packet["criterion_anchors"][0]["partial"] += " changed"
            else: packet[field] += " changed"
            with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(value, packet)
            # Forging only the new top-level hash cannot reuse old IDs.
            value2 = deepcopy(value); value2["packet_sha256"] = draft.catalog(packet)["packet_sha256"]
            with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(value2, packet)

    def test_null_permissions_preserve_literal_absence_exception(self):
        for prefix in ("Avoids ", "Does not ", "Do not ", " Avoids ", "不建议"):
            self.packet["criterion_anchors"][0]["met"] = prefix + "fixture"
            for status in ("met", "partial", "missed", "unclear"):
                value = fixture(self.packet, status)
                value["criterion_assessments"][0]["response_evidence_ref"] = None
                required = status == "partial" or status == "met" and prefix not in ("Avoids ", "Does not ")
                if required:
                    with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(value, self.packet)
                else: draft.resolve(value, self.packet)

    def test_observation_either_turn_but_not_explanation_waiver(self):
        value = fixture(self.packet)
        first = draft.catalog(self.packet)["spans"][0]["id"]
        value["dimension_observations"][0]["response_evidence_ref"] = {"first": first, "last": first}
        draft.resolve(value, self.packet)
        for index, field in ((0, "overlap_note"), (1, "overlap_note"), (1, "new_fact")):
            changed = deepcopy(value); changed["dimension_observations"][index][field] = ""
            with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(changed, self.packet)

    def test_no_legacy_quote_repair_or_extra_fields(self):
        with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(judgment(self.packet), self.packet)
        for field in ("response_evidence", "extra"):
            value = fixture(self.packet); value["criterion_assessments"][0][field] = "fabricated quotation"
            with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(value, self.packet)

    def test_identity_order_status_and_severity_validation_unchanged(self):
        for kind in ("missing", "reordered", "duplicate", "bad_status", "error"):
            value = fixture(self.packet); rows = value["criterion_assessments"]
            if kind == "missing": rows.pop()
            elif kind == "reordered": rows.reverse()
            elif kind == "duplicate": rows[1] = deepcopy(rows[0])
            elif kind == "bad_status": rows[0]["status"] = "excellent"
            else: value["critical_errors"] = [{"stage_id": "update", "error_id": "invented", "severity": 3, "rationale": "x"}]
            with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(value, self.packet)

    def test_initial_catalog_cannot_expose_update_or_user(self):
        full, levels = self.controls["HC-MT-REASON-020__en__safe"]
        packet = draft.score.stage_packet(full, "initial", levels)
        catalog = draft.catalog(packet)
        self.assertEqual({s["assistant_turn"] for s in catalog["spans"]}, {1})
        self.assertEqual("".join(s["text"] for s in catalog["spans"]), full["transcript"][1]["content"])
        self.assertNotIn("dimension_observations", draft.schema(packet)["properties"])

    def test_schema_enumerates_only_permitted_ids(self):
        value = draft.schema(self.packet)
        criteria = value["properties"]["criterion_assessments"]["items"]["properties"]
        self.assertNotIn("response_evidence", criteria)
        allowed = criteria["response_evidence_ref"]["anyOf"][1]["properties"]["first"]["enum"]
        self.assertEqual(allowed, [s["id"] for s in draft.catalog(self.packet)["spans"] if s["assistant_turn"] == 2])


if __name__ == "__main__": unittest.main()
