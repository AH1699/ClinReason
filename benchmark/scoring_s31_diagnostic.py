"""Read-only S31 stopped-response diagnosis; never repair, rescore or send."""

import argparse
import json
from pathlib import Path

from . import scoring_s31 as experiment
from .config import load_json
from .multiturn_judging import _evidence_in_turn
from .provenance import sha256_text


def observation_quote_violations(judgment, packet):
    answers = {stage: packet["transcript"][index]["content"]
               for stage, index in (("initial", 1), ("update", 3))}
    violations = []
    for row in judgment["dimension_observations"]:
        quote = row["response_evidence"]
        if not quote or any(_evidence_in_turn(quote, text) for text in answers.values()):
            continue
        # Explain the observed separator; never turn these pieces into accepted
        # evidence or edit the original reply. This is not a new scoring rule.
        pieces = quote.split(" / ") if " / " in quote else [quote]
        violations.append({"dimension": row["dimension"], "rejected_quote": quote,
                           "whole_quote_matches_one_assistant_turn": False,
                           "separator": " / " if len(pieces) > 1 else None,
                           "pieces": [{"text": piece, "matching_assistant_stages": [
                               stage for stage, text in answers.items() if piece and _evidence_in_turn(piece, text)]}
                               for piece in pieces]})
    return violations


def diagnose(root, output):
    summary = experiment.audit(root, output)
    stop = summary["stopped"]
    if not stop or stop["kind"] != "response_validation_failure":
        raise ValueError("Requires an audited S31 response-validation stop")
    policy, packets, _ = experiment.inputs(root)
    phase, key, spec = experiment.schedule(policy, packets)[stop["attempted"] - 1]
    path = output / f'{stop["attempted"]:02d}.response.json'
    raw = load_json(path)
    judgment = experiment.base.parse_response(raw, spec["provider"])
    try:
        experiment.base.validate(judgment, packets[key])
    except ValueError as exc:
        if str(exc) != "S26 observation quote is not in an assistant response":
            raise ValueError("Outside this diagnostic's observation-quote scope") from exc
    else:
        raise ValueError("Saved response does not reproduce the observation-quote failure")
    violations = observation_quote_violations(judgment, packets[key])
    if not violations:
        raise ValueError("No observation-quote violation found")
    return {"status": "offline_saved_response_diagnostic_not_repair",
            "attempted_call": stop["attempted"], "valid_prefix": summary["valid_judgments"],
            "phase": phase, "packet": key, "provider": spec["provider"],
            "requested_model": spec["model"], "returned_model": raw["model"],
            "model_matches": raw["model"] == spec["model"],
            "response_sha256": sha256_text(path.read_text(encoding="utf-8")),
            "validation_failure": "observation_quote_not_contained_in_one_assistant_turn",
            "violations": violations, "repaired": False, "rescored": False, "new_calls": 0,
            "limits": "The rejected response stays unscored. Matching pieces do not satisfy the frozen single-span contract or authorize repair/resumption."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(diagnose(Path(__file__).resolve().parents[1], args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
