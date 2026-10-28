import base64
from copy import deepcopy
import json
from unittest.mock import patch

from scripts import evidence_refs_s65 as draft
from tests import test_evidence_refs_s64 as old

original_fixture = old.fixture


def fixture(packet, status="met"):
    # Explicitly authored fixture, never a repair of a historical judge reply.
    with patch.object(old, "draft", draft):
        value = original_fixture(packet, status)
    value["evidence_version"] = draft.VERSION
    return value


class CompactEvidenceTests(old.EvidenceRefTests):
    @classmethod
    def setUpClass(cls):
        cls.patcher = patch.multiple(old, draft=draft, fixture=fixture)
        cls.patcher.start()
        cls.addClassCleanup(cls.patcher.stop)
        super().setUpClass()

    def test_schema_enumerates_only_permitted_ids(self):
        # S65 deliberately moves membership enforcement out of provider schema.
        value = draft.schema(self.packet)
        prop = value["properties"]["criterion_assessments"]["items"]["properties"]
        self.assertNotIn("response_evidence", prop)
        self.assertEqual(prop["response_evidence_ref"]["anyOf"][1]["properties"]["first"], {"type": "string"})
        before = len(json.dumps(value))
        changed = deepcopy(self.packet)
        changed["transcript"][3]["content"] *= 10
        self.assertEqual(len(json.dumps(draft.schema(changed))), before)

    def test_full_256_bits_not_truncated_and_old_ids_rejected(self):
        for span in draft.catalog(self.packet)["spans"]:
            self.assertEqual(len(span["id"]), 44)
            self.assertEqual(base64.urlsafe_b64decode(span["id"][1:] + "="), bytes.fromhex(span["legacy_id"][5:]))
        value = fixture(self.packet)
        value["criterion_assessments"][0]["response_evidence_ref"]["first"] = draft.catalog(self.packet)["spans"][0]["legacy_id"]
        with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(value, self.packet)

    def test_wire_transcript_lossless_no_second_catalog_or_offsets(self):
        request = draft.judge_input(old.ROOT, self.packet)
        self.assertEqual(set(request), {"packet", "instruction", "schema"})
        for original, wire in zip(self.packet["transcript"], request["packet"]["transcript"]):
            if original["role"] == "user": self.assertEqual(original, wire)
            else:
                self.assertEqual(set(wire), {"role", "chunks"})
                self.assertEqual("".join(c[1] for c in wire["chunks"]), original["content"])
        for forbidden in ("source_sha256", "legacy_id", "assistant_turn", "evidence_catalog"):
            self.assertNotIn(forbidden, json.dumps(request))

    def test_payload_has_expected_provider_contract(self):
        payload = draft.payload(old.ROOT, self.packet)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["generation_config"], {"max_output_tokens": 32768, "thinking_level": "medium"})
        self.assertEqual(payload["response_format"]["schema"], draft.schema(self.packet))
        self.assertNotIn("tools", payload)
        self.assertEqual(json.loads(payload["input"]), draft.judge_input(old.ROOT, self.packet)["packet"])

    def test_decoder_completion_identity_version_and_malformed_envelope(self):
        raw = {"model": "gemini-3.8-flash", "status": "completed", "steps": [
            {"type": "model_output", "content": [{"type": "text", "text": json.dumps(fixture(self.packet))}]}]}
        self.assertEqual(draft.decode(raw, raw["model"], self.packet), old.judgment(self.packet))
        for change in ({"status": "in_progress"}, {"model": "other"}, {"steps": []}):
            with self.assertRaises(draft.score.JudgmentFailure): draft.decode({**raw, **change}, raw["model"], self.packet)
        value = fixture(self.packet); value["evidence_version"] = "old"
        with self.assertRaises(draft.score.JudgmentFailure): draft.resolve(value, self.packet)

    def test_no_future_observation_instruction_for_initial(self):
        full, levels = self.controls["HC-MT-REASON-020__en__safe"]
        packet = draft.score.stage_packet(full, "initial", levels)
        self.assertNotIn("Return safety then revision", draft.instruction(old.ROOT, packet))
        self.assertNotIn("critical_errors only.", draft.instruction(old.ROOT, packet))
        self.assertIn("Return evidence_version and packet_sha256", draft.instruction(old.ROOT, packet))

    def test_arithmetic_and_critical_errors_unchanged(self):
        policy = {"version": draft.score.VERSION, **draft.score.ARITHMETIC}
        for full, levels in self.controls.values():
            packets = [draft.score.stage_packet(full, s, levels) for s in draft.score.STAGES]
            for status in ("met", "partial", "missed", "unclear"):
                expected = [old.judgment(p, status) for p in packets]
                actual = [draft.resolve(fixture(p, status), p) for p in packets]
                self.assertEqual(draft.score.combine(*expected, full, policy), draft.score.combine(*actual, full, policy))
            for error in packets[1]["turn_labels"][0]["critical_errors"]:
                values = [fixture(p) for p in packets]
                values[1]["critical_errors"] = [{"stage_id": "update", "error_id": error["id"],
                    "severity": error["severity"], "rationale": "Fixture only."}]
                expected = [old.judgment(p) for p in packets]
                expected[1]["critical_errors"] = deepcopy(values[1]["critical_errors"])
                actual = [draft.resolve(v, p) for v, p in zip(values, packets)]
                self.assertEqual(draft.score.combine(*expected, full, policy), draft.score.combine(*actual, full, policy))
