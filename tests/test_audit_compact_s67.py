"""Synthetic offline journals only; no provider access or private source dependency."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_compact_s67 as audit
from tests.test_compact_live_s66 import portable_items, alter, judge_edit

ROOT = Path(__file__).resolve().parents[1]
live = audit.live


def ledger_for(value):
    return {"version": audit.VERSION, "protocol_sha256": value["protocol_sha256"],
        "source_journal_sha256": value["source_journal_sha256"],
        "reviewer": "assistant_local_preliminary_not_independent_clinician",
        "reviewed_at": "2026-10-28T11:50:00Z", "independent_clinical_review": False,
        "rows": [{"id": s["id"], "judgment_row_sha256": s["judgment_row_sha256"],
                  "relevance": "null_permitted" if s["reference_null"] else "supported",
                  "breadth": "not_applicable" if s["reference_null"] else "distributed_support",
                  "verdict": "no_objection", "note": "UNIT TEST ONLY: authored fixture, not semantic validation."}
                 for s in value["evidence_slots"]]}


class CompactAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name).resolve() / "complete"
        with patch.object(live, "read_setting", side_effect=AssertionError), patch.object(live, "tls", side_effect=AssertionError):
            writer = live.Session(ROOT, cls.directory, mode="offline_fixture", fixture_items=portable_items())
            while writer.step(live.fixture_for(writer.core)) is not None: pass
            cls.value = audit.audit(ROOT, cls.directory)

    def test_full_readout_without_review_is_not_advancement(self):
        v = self.value
        self.assertEqual(len(v["events"]), 16)
        self.assertEqual(v["evidence_totals"]["slots"], 64)
        self.assertEqual(v["comparison_totals"]["paired_packets"], 6)
        self.assertFalse(v["development_feasibility_passed"])
        self.assertEqual(v["local_review"]["status"], "not_supplied")
        self.assertEqual(v["measured_model_scores"], 0)

    def test_complete_fixture_review_is_never_live_or_clinical_pass(self):
        v = audit.audit(ROOT, self.directory, ledger_for(self.value))
        self.assertTrue(v["local_review"]["pass"])
        self.assertFalse(v["development_feasibility_passed"])
        self.assertFalse(v["clinical_validation"])
        self.assertFalse(v["automatic_retry_or_broader_run_authorized"])

    def test_missing_duplicate_stale_or_unbound_review_rejected(self):
        for mutate in (lambda v:v["rows"].pop(), lambda v:v["rows"].append(deepcopy(v["rows"][0])),
                       lambda v:v.update(source_journal_sha256="other"),
                       lambda v:v["rows"][0].update(judgment_row_sha256="other"),
                       lambda v:v.update(independent_clinical_review=True),
                       lambda v:v["rows"][0].update(extra="not allowed")):
            ledger = ledger_for(self.value); mutate(ledger)
            with self.assertRaises(ValueError): audit.review_readout(ledger, self.value["protocol_sha256"],
                self.value["source_journal_sha256"], self.value["evidence_slots"])

    def test_null_review_cannot_claim_nonnull_support(self):
        ledger = ledger_for(self.value)
        next(v for v in ledger["rows"] if v["relevance"] == "null_permitted")["relevance"] = "supported"
        with self.assertRaises(ValueError): audit.review_readout(ledger, self.value["protocol_sha256"],
            self.value["source_journal_sha256"], self.value["evidence_slots"])

    def test_qualified_or_overbroad_support_cannot_be_cleared(self):
        for changes in ({"relevance": "qualified"}, {"relevance": "not_demonstrated"}, {"breadth": "avoidable_extra_context"}):
            ledger = ledger_for(self.value); ledger["rows"][0].update(changes)
            with self.assertRaises(ValueError): audit.review_readout(ledger, self.value["protocol_sha256"],
                self.value["source_journal_sha256"], self.value["evidence_slots"])
            ledger["rows"][0]["verdict"] = "review_hold"
            v = audit.review_readout(ledger, self.value["protocol_sha256"], self.value["source_journal_sha256"], self.value["evidence_slots"])
            self.assertFalse(v["pass"]); self.assertEqual(v["hold_count"], 1)

    def test_no_raw_text_reasoning_approval_or_review_notes_exported(self):
        ledger = ledger_for(self.value); ledger["rows"][0]["note"] = "PRIVATE_NOTE_SENTINEL"
        value = audit.audit(ROOT, self.directory, ledger)
        encoded = live.json.dumps(value)
        for field in ("PRIVATE_NOTE_SENTINEL", "response_evidence", "rationale", "authorization_evidence", "reasoning_content"):
            self.assertNotIn(field, encoded)
        self.assertTrue(all(v["visible_characters"] > 0 and v["scored"] is False for v in value["candidate_turns"]))

    def test_readout_does_not_modify_journal(self):
        before = audit.previous.tree_hash(ROOT, self.directory)
        with patch.object(live, "read_setting", side_effect=AssertionError), patch.object(live, "tls", side_effect=AssertionError):
            audit.audit(ROOT, self.directory, ledger_for(self.value))
        self.assertEqual(before, audit.previous.tree_hash(ROOT, self.directory))

    def test_semantic_change_and_observation_drift_are_reported_separately(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder).resolve() / "drift"
            writer = live.Session(ROOT, directory, mode="offline_fixture", fixture_items=portable_items())
            while not writer.closed:
                if writer.core.index == 6:
                    def change(v):
                        v["criterion_assessments"][0]["status"] = "partial"
                        v["dimension_observations"][0].update(decision="distinct_failure",
                            independent_consequence_or_failure="Overlaps criterion; synthetic fixture only.")
                    fixture = alter(writer.core, lambda r:judge_edit(r, change))
                else: fixture = live.fixture_for(writer.core)
                writer.step(fixture)
            value = audit.audit(ROOT, directory)
            self.assertEqual(value["comparison_totals"]["changed_criterion_positions"], 1)
            self.assertEqual(value["comparison_totals"]["changed_observation_decisions"], 1)
            self.assertFalse(value["run_report"]["technical_gate"]["pass"])

    def test_unknown_cost_remains_missing_not_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder).resolve() / "unknown"
            writer = live.Session(ROOT, directory, mode="offline_fixture", fixture_items=portable_items())
            writer.step(live.old.previous.Fixture(b"{}", status=403))
            value = audit.audit(ROOT, directory)
            self.assertEqual(value["run_report"]["unknown_cost_attempts"], 1)
            self.assertIsNone(value["events"][0]["input_tokens"])
            self.assertEqual(value["comparison_totals"]["paired_packets"], 0)
            self.assertTrue(all(v["comparison"] is None for v in value["judge_pairs"]))
            self.assertFalse(value["development_feasibility_passed"])

    def test_unfinished_run_cannot_be_published_as_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder).resolve() / "unfinished"
            writer = live.Session(ROOT, directory, mode="offline_fixture", fixture_items=portable_items())
            writer.step(live.fixture_for(writer.core))
            with self.assertRaises(ValueError): audit.audit(ROOT, directory)


if __name__ == "__main__": unittest.main()
