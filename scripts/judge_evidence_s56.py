"""Prospective, offline evidence instructions; frozen S36 acceptance is unchanged.

No provider connection, repair, label change, scoring change or authorization.
Only descriptions change in the provider schema; local validation is authoritative.
"""

from copy import deepcopy
import json

from scripts import judge_observation_draft as prior

score = prior.score
VERSION = "s56-explicit-criterion-evidence-v1"


def contract(packet):
    score.check_packet(packet)
    stage = packet["scoring_stage"]
    return [{"stage_id": stage, "requirement_index": anchor["requirement_index"],
             "allowed_assistant_turn": 1 if stage == "initial" else 2,
             "nonblank_quote_required": {
                 "met": not anchor["met"].startswith(("Does not ", "Avoids ")),
                 "partial": True, "missed": False, "unclear": False}}
            for anchor in packet["criterion_anchors"]]


def instruction(root, packet):
    return prior.instruction(root, packet) + "\n" + """Per-criterion evidence checklist
The following computed table states the EXISTING quote requirement for each status.
true means response_evidence must be nonblank; false permits an empty string but
does not require one. Every nonempty quote must still be a contiguous span from
the listed assistant turn, under the unchanged normalization rules. Turn 1 is the
initial assistant answer; turn 2 is the update assistant answer, not a user turn.
This table is about evidence FORMAT, not a target status or clinical answer key.
Determine status from the supplied criterion anchors and actual answer. Do not
change a status merely to avoid a quote requirement. Do not invent, stitch or
paraphrase evidence, or import evidence from another turn. Explain uncertainty
honestly using the existing anchors; never fill a required quote with a rationale.
In particular, a met anchor beginning 'Do not ' is NOT an empty-quote exception.
Only the existing literal 'Does not ' and 'Avoids ' met exceptions apply. They do
not exempt partial. A clinically negative requirement is not automatically an
exception. Observation quote permissions and mandatory explanations are unchanged.
Before returning, check EACH criterion against this table and the full contract.
""" + json.dumps({"version": VERSION, "criteria": contract(packet)}, ensure_ascii=False) + "\n"


def schema(packet):
    result = deepcopy(prior.schema(packet))
    fields = result["properties"]["criterion_assessments"]["items"]["properties"]
    fields["response_evidence"]["description"] = (
        "One contiguous matching-stage assistant span; nonblank when the selected "
        "status has true below. false permits empty, never a fabricated quote. "
        "These are evidence-format rules, not status assignments: "
        + json.dumps(contract(packet), ensure_ascii=False))
    return result


def validate(judgment, packet):
    return score.validate(judgment, packet)
