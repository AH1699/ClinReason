"""Read-only S34 initial-quote diagnosis; never repair, rescore or send."""

import argparse
import json
from pathlib import Path

from . import minimax_s34 as experiment
from .config import load_json
from .provenance import sha256_text


def criterion_quote_violations(judgment, packet):
    answer = packet["transcript"][1]["content"]
    violations = []
    for row in judgment["criterion_assessments"]:
        quote = row["response_evidence"]
        if not quote or experiment.scoring.base._evidence_in_turn(quote, answer):
            continue
        # Describe the observed omission marker only. Do not turn separated
        # pieces into acceptable evidence or modify any saved response.
        pieces = quote.split("……") if "……" in quote else [quote]
        violations.append({"requirement_index": row["requirement_index"], "rejected_quote": quote,
            "whole_quote_matches_initial_answer": False,
            "separator": "……" if len(pieces) > 1 else None,
            "pieces": [{"text": piece, "matches_initial_answer": bool(piece) and
                experiment.scoring.base._evidence_in_turn(piece, answer)} for piece in pieces]})
    return violations


def diagnose(root, output):
    summary = experiment.audit(root, output)
    stop = summary["stopped"]
    if not stop or stop["kind"] != "response_validation_failure":
        raise ValueError("Requires an audited S34 response-validation stop")
    policy, score_policy, templates, levels = experiment.inputs(root)
    spec = experiment.schedule(policy, score_policy)[stop["attempted"] - 1]
    if spec["kind"] != "judge" or spec["stage"] != "initial":
        raise ValueError("Outside this diagnostic's initial-judge scope")
    answers = {}
    for path in sorted(output.glob("*.judgment.json")):
        row = load_json(path)
        if row["kind"] == "candidate":
            answers[(row["case_key"], row["stage"])] = row["result"]
    packet = experiment.context(spec, templates, answers, levels, experiment.instructions(root)["candidate"])
    path = output / f'{stop["attempted"]:02d}.response.json'
    raw = load_json(path)
    if raw.get("model") != spec["model"]:
        raise ValueError("Outside this diagnostic's exact-model scope")
    judgment = experiment.scoring.base.parse_response(raw, spec["provider"])
    try:
        experiment.scoring.validate(judgment, packet)
    except ValueError as exc:
        if str(exc) != "S33 initial evidence must match the initial assistant turn":
            raise ValueError("Outside this diagnostic's initial-quote scope") from exc
    else:
        raise ValueError("Saved response does not reproduce the initial-quote failure")
    violations = criterion_quote_violations(judgment, packet)
    if not violations:
        raise ValueError("No nonliteral initial-criterion quote found")
    return {"status": "offline_saved_response_diagnostic_not_repair",
        "attempted_call": stop["attempted"], "valid_prefix": stop["saved"],
        "valid_candidate_turns": summary["valid_candidate_turns"], "valid_judge_stages": summary["valid_judge_stages"],
        **spec, "returned_model": raw["model"], "model_matches": True,
        "response_sha256": sha256_text(path.read_text(encoding="utf-8")),
        "validation_failure": "initial_criterion_quote_not_contained_in_initial_answer",
        "violations": violations, "repaired": False, "rescored": False, "new_calls": 0,
        "limits": "Matching pieces do not satisfy the frozen evidence contract. The rejected judgment stays unscored; this diagnosis does not authorize repair or resumption."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(diagnose(Path(__file__).resolve().parents[1], args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
