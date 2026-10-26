"""Offline reproduction of the S55 stop, not a repair or clinical adjudication.

Uses synthetic test judgments and public control packets, never private replies.
The frozen rule remains literal: Do not is not an empty-quote exception.
"""

from copy import deepcopy
from pathlib import Path
import unittest

from benchmark import scoring_s36 as score
from tests.test_scoring_s36 import judgment

ROOT = Path(__file__).resolve().parents[1]


class EvidenceContractRegression(unittest.TestCase):
    def packets(self):
        controls = score.controls(ROOT)
        for language in ("en", "zh-Hans"):
            full, levels = deepcopy(controls[f"HC-MT-REASON-020__{language}__safe"])
            yield score.stage_packet(full, "update", levels)

    def test_real_do_not_anchor_rejects_met_without_quote_in_both_languages(self):
        for packet in self.packets():
            with self.subTest(language=packet["language"]):
                self.assertTrue(packet["criterion_anchors"][3]["met"].startswith("Do not "))
                value = judgment(packet)
                value["criterion_assessments"][3]["response_evidence"] = ""
                with self.assertRaisesRegex(score.JudgmentFailure, "contiguous span"):
                    score.validate(value, packet)

    def test_current_contract_accepts_literal_stage_quote_without_changing_anchor(self):
        for packet in self.packets():
            value = judgment(packet)
            score.validate(value, packet)  # Format only, not confirmation of met.

    def test_only_declared_prefixes_allow_empty_met_evidence_in_mechanical_fixture(self):
        for original in self.packets():
            for prefix in ("Does not ", "Avoids "):
                packet = deepcopy(original)
                packet["criterion_anchors"][3]["met"] = prefix + "mechanical fixture behavior."
                value = judgment(packet)
                value["criterion_assessments"][3]["response_evidence"] = ""
                score.validate(value, packet)

    def test_partial_never_inherits_the_met_avoidance_exception(self):
        for original in self.packets():
            for prefix in ("Do not ", "Does not ", "Avoids "):
                packet = deepcopy(original)
                packet["criterion_anchors"][3]["met"] = prefix + "mechanical fixture behavior."
                value = judgment(packet)
                value["criterion_assessments"][3].update(status="partial", response_evidence="")
                with self.assertRaises(score.JudgmentFailure): score.validate(value, packet)


if __name__ == "__main__":
    unittest.main()
