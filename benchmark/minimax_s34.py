"""MiniMax workflow diagnostic beside S33, never a calibrated comparison."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from . import scoring_s33 as scoring
from .config import load_json
from .local_settings import read_setting
from .provenance import sha256_json, sha256_text
from .providers.minimax_conversation import ENDPOINT, MAX_COMPLETION_TOKENS, MiniMaxConversationProvider
from .providers.http_json import ProviderRequestError
from .providers.observed_http import DiagnosticRequestError, post_json_observed

POLICY = "config/minimax_s34_v1.json"
MANIFEST = "config/minimax_s34_frozen_v1.json"
PROMPT = "config/candidate_prompt_bilingual_v2.txt"
SOURCES = sorted(set(scoring.SOURCES + [scoring.MANIFEST, POLICY, PROMPT,
    "benchmark/minimax_s34.py", "tests/test_minimax_s34.py", "benchmark/providers/minimax_conversation.py"]))
MAX_CALLS = 24


def inputs(root):
    scoring.check_manifest(root)
    score_policy, full, _, _ = scoring.inputs(root)
    policy = load_json(root / POLICY)
    keys = [f"HC-MT-TRIAGE-{n}__{language}" for n in ("018", "020") for language in ("en", "zh-Hans")]
    if (policy["version"] != "s34-v1-minimax-stage-isolated-workflow-diagnostic"
            or policy["candidate"] != {"provider": "minimax", "model": "MiniMax-M2.7"}
            or policy["case_keys"] != keys or policy["candidate_prompt"] != PROMPT
            or [policy[k] for k in ("candidate_calls", "judge_calls", "maximum_calls", "automatic_retries", "timeout_seconds")] != [8, 16, 24, 0, 240]):
        raise ValueError("Unexpected S34 scope")
    templates = {key: full[key + "__safe"] for key in keys}
    levels = load_json(root / scoring.draft.ANCHORS)["levels"]
    return policy, score_policy, templates, levels


def schedule(policy, score_policy):
    steps = []
    for key in policy["case_keys"]:
        steps.extend({"case_key": key, "kind": "candidate", "stage": stage, **policy["candidate"]}
                     for stage in ("initial", "update"))
        steps.extend({"case_key": key, "kind": "judge", "stage": stage, **judge}
                     for stage in ("initial", "update") for judge in score_policy["judges"])
    return steps


def candidate_payload(model, history, instruction):
    return {"model": model, "messages": [{"role": "system", "content": instruction}, *history],
            "max_completion_tokens": MAX_COMPLETION_TOKENS, "reasoning_split": True}


def context(spec, templates, answers, levels, instruction):
    key, stage = spec["case_key"], spec["stage"]
    template = templates[key]
    if spec["kind"] == "candidate":
        history = [deepcopy(template["transcript"][0])]
        if stage == "update":
            history += [{"role": "assistant", "content": answers[(key, "initial")]["text"]}, deepcopy(template["transcript"][2])]
        return candidate_payload(spec["model"], history, instruction)
    full = deepcopy(template)
    for i, s in enumerate(("initial", "update")):
        full["transcript"][2 * i + 1]["content"] = answers[(key, s)]["text"]
    return scoring.stage_packet(full, stage, levels)


def parse_candidate(raw, latency, payload):
    if not isinstance(raw, dict) or raw.get("model") != payload["model"] or type(latency) is not int or latency < 0:
        raise ValueError("S34 candidate model or latency mismatch")
    def replay(endpoint, actual, **kwargs):
        if endpoint != ENDPOINT or actual != payload or kwargs["retries"] != 0:
            raise ValueError("S34 candidate adapter payload changed")
        return raw, latency
    provider = MiniMaxConversationProvider(model=payload["model"], api_key="offline-replay-only",
        instruction=payload["messages"][0]["content"], timeout=240, retries=0, transport=replay)
    try:
        return provider.reply(payload["messages"][1:])
    except ProviderRequestError:
        raise ValueError("S34 candidate response failed the frozen adapter contract") from None


def validate_response(raw, latency, spec, packet):
    if not isinstance(raw, dict) or raw.get("model") != spec["model"] or type(latency) is not int or latency < 0:
        raise ValueError("S34 returned model or latency mismatch")
    if spec["kind"] == "candidate":
        return parse_candidate(raw, latency, packet)
    judgment = scoring.base.parse_response(raw, spec["provider"])
    scoring.validate(judgment, packet)
    return judgment


def request(spec, key, packet, instruction):
    if spec["kind"] == "candidate":
        return post_json_observed(ENDPOINT, packet, auth_header="Authorization", auth_value=f"Bearer {key}", timeout=240, retries=0)
    return scoring.request(spec["provider"], spec["model"], key, packet, instruction, 240)


def instructions(root):
    return {"candidate": (root / PROMPT).read_text(encoding="utf-8").strip(),
            **{s: (root / p).read_text(encoding="utf-8") for s, p in scoring.PROMPTS.items()}}


def manifest(root):
    policy, score_policy, templates, _ = inputs(root)
    return {"version": "s34-frozen-v1",
            "files": {p: sha256_text((root / p).read_text(encoding="utf-8")) for p in SOURCES},
            "case_hashes": {k: p["case_content_hash"] for k, p in templates.items()},
            "candidate_user_turns": {k: sha256_json([p["transcript"][0], p["transcript"][2]]) for k, p in templates.items()},
            "schedule_sha256": sha256_json(schedule(policy, score_policy)),
            "dynamic_judge_packets": "Derived only from validated saved MiniMax content and frozen cases/anchors; exact input hash stored before every request."}


def check_manifest(root):
    actual = manifest(root)
    if actual != load_json(root / MANIFEST):
        raise ValueError("S34 frozen input changed; create a new version")
    return actual


def attempt(spec, packet, instruction):
    return {**spec, "input_sha256": sha256_json(packet), "instruction_sha256": sha256_text(instruction),
            "timeout_seconds": 240, "automatic_retries": 0}


def run(root, output, env_file, max_calls, approved_protocol_sha256=None):
    frozen = check_manifest(root)
    if (type(max_calls) is not int or max_calls != MAX_CALLS or approved_protocol_sha256 != sha256_json(frozen)
            or output.exists() or not output.resolve().is_relative_to((root / "work").resolve())):
        raise ValueError("S34 requires fresh work/ output, max-calls 24 and approved protocol SHA256")
    policy, score_policy, templates, levels = inputs(root)
    keys = {p: read_setting(env_file, p.upper() + "_API_KEY", secret=True) for p in ("minimax", "gemini", "grok")}
    prompts, answers = instructions(root), {}
    output.mkdir(parents=True, mode=0o700)
    scoring.base.write_new(output / "manifest.json", frozen)
    scoring.base.write_new(output / "external_call_acknowledgment.json", {"protocol_sha256": approved_protocol_sha256, "maximum_calls": MAX_CALLS})
    for i, spec in enumerate(schedule(policy, score_policy), 1):
        packet = context(spec, templates, answers, levels, prompts["candidate"])
        instruction = prompts["candidate" if spec["kind"] == "candidate" else spec["stage"]]
        record = attempt(spec, packet, instruction)
        scoring.base.write_new(output / f"{i:02d}.attempt.json", record)
        try:
            raw, latency = request(spec, keys[spec["provider"]], packet, instruction)
            scoring.base.write_new(output / f"{i:02d}.response.json", raw)
            result = validate_response(raw, latency, spec, packet)
            scoring.base.write_new(output / f"{i:02d}.judgment.json", {**record, "model_returned": raw["model"], "latency_ms": latency, "result": result})
            if spec["kind"] == "candidate": answers[(spec["case_key"], spec["stage"])] = result
            print(json.dumps({"completed": i, "maximum": MAX_CALLS, "kind": spec["kind"], "stage": spec["stage"], "provider": spec["provider"]}), flush=True)
        except DiagnosticRequestError as exc:
            scoring.base.write_new(output / "stopped.json", {"attempted": i, "saved": i - 1, "kind": "transport_failure", "diagnostic": exc.diagnostic})
            return audit(root, output)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            scoring.base.write_new(output / "stopped.json", {"attempted": i, "saved": i - 1, "kind": "response_validation_failure",
                "error_type": type(exc).__name__, "delivery": "response_saved_validation_failed"})
            return audit(root, output)
    scoring.base.write_new(output / "complete.json", {"candidate_calls": 8, "judge_calls": 16, "total_calls": MAX_CALLS})
    return audit(root, output)


def audit(root, output):
    frozen = check_manifest(root)
    if (load_json(output / "manifest.json") != frozen or load_json(output / "external_call_acknowledgment.json") != {
            "protocol_sha256": sha256_json(frozen), "maximum_calls": MAX_CALLS}):
        raise ValueError("S34 manifest or acknowledgment mismatch")
    policy, score_policy, templates, levels = inputs(root)
    steps, prompts = schedule(policy, score_policy), instructions(root)
    attempts, responses, saved = [sorted(output.glob(f"*.{suffix}.json")) for suffix in ("attempt", "response", "judgment")]
    if not 0 <= len(saved) <= len(responses) <= len(attempts) <= MAX_CALLS or len(attempts) > len(saved) + 1:
        raise ValueError("Invalid S34 artifact counts")
    for paths, suffix in ((attempts, "attempt"), (responses, "response"), (saved, "judgment")):
        if [p.name for p in paths] != [f"{i:02d}.{suffix}.json" for i in range(1, len(paths) + 1)]:
            raise ValueError("S34 artifacts must be a contiguous prefix")
    answers, judgments, cells = {}, {}, []
    for i, path in enumerate(attempts):
        spec = steps[i]
        packet = context(spec, templates, answers, levels, prompts["candidate"])
        instruction = prompts["candidate" if spec["kind"] == "candidate" else spec["stage"]]
        record = attempt(spec, packet, instruction)
        if load_json(path) != record: raise ValueError("S34 attempt or dynamic input mismatch")
        if i >= len(saved): continue
        raw = load_json(responses[i]); row = load_json(saved[i])
        if (not isinstance(row, dict) or set(row) != set(record) | {"model_returned", "latency_ms", "result"}
                or any(row[k] != v for k, v in record.items()) or not isinstance(raw, dict)
                or row["model_returned"] != raw.get("model")):
            raise ValueError("S34 saved result identity mismatch")
        result = validate_response(raw, row["latency_ms"], spec, packet)
        if row["result"] != result: raise ValueError("S34 raw response or saved result mismatch")
        if spec["kind"] == "candidate": answers[(spec["case_key"], spec["stage"])] = result
        else: judgments[(spec["case_key"], spec["stage"], spec["provider"])] = result
        cells.append({**spec, "latency_ms": row["latency_ms"], "input_sha256": record["input_sha256"],
                      "response_sha256": sha256_text(responses[i].read_text(encoding="utf-8"))})
    stopped = load_json(output / "stopped.json") if (output / "stopped.json").exists() else None
    if stopped is not None:
        scoring.previous.boundary.validate_stop(stopped, output, len(attempts), len(saved))
    complete = len(saved) == len(attempts) == MAX_CALLS and stopped is None and (output / "complete.json").exists()
    if (output / "complete.json").exists() and (not complete or load_json(output / "complete.json") != {
            "candidate_calls": 8, "judge_calls": 16, "total_calls": MAX_CALLS}):
        raise ValueError("Invalid S34 completion marker")
    scores = []
    for key, template in templates.items():
        if any((key, stage) not in answers for stage in ("initial", "update")): continue
        full = deepcopy(template)
        for i, stage in enumerate(("initial", "update")):
            full["transcript"][2*i+1]["content"] = answers[(key, stage)]["text"]
        for judge in score_policy["judges"]:
            provider = judge["provider"]
            if any((key, stage, provider) not in judgments for stage in ("initial", "update")): continue
            judgment, score = scoring.combine(judgments[(key, "initial", provider)], judgments[(key, "update", provider)], full, score_policy)
            scores.append({"case_key": key, "candidate_model": policy["candidate"]["model"], "judge": judge,
                "criterion_error_vector": scoring.previous.vector({"judgment": judgment}), "score": score})
    return {"status": "complete_workflow_diagnostic" if complete else "incomplete_saved_prefix",
            "experiment": policy["version"], "candidate": policy["candidate"], "attempted_calls": len(attempts),
            "valid_candidate_turns": len(answers), "valid_judge_stages": len(judgments),
            "complete_candidate_conversations": sum(all((k, s) in answers for s in ("initial", "update")) for k in templates),
            "derived_conversation_judge_scores": len(scores), "stopped": stopped,
            "comparison_ready": False, "calibration_complete": False, "s33_gate_overridden": False,
            "automatic_retries": 0, "score_cells": scores, "call_cells": cells,
            "limits": "User-requested workflow diagnostic, not a comparative pilot. Case-wise draft scores only, no aggregate ranking, score-band fit, historical pooling or clinical approval. S33 control results remain separate; completing this run cannot turn a failed S33 gate into a pass."}


def plan(root):
    frozen = check_manifest(root)
    policy, score_policy, _, _ = inputs(root)
    return {"status": "frozen_user_requested_workflow_diagnostic", "protocol_sha256": sha256_json(frozen),
            "candidate": policy["candidate"], "case_keys": policy["case_keys"], "judges": score_policy["judges"],
            "candidate_calls": 8, "judge_calls": 16, "maximum_calls": MAX_CALLS,
            "combined_ceiling_with_s33": 72, "comparison_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["manifest", "plan", "run", "audit"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--approved-protocol-sha256")
    args = parser.parse_args(); root = Path(__file__).resolve().parents[1]
    if args.command == "manifest": result = manifest(root)
    elif args.command == "plan": result = plan(root)
    elif args.output is None: parser.error("--output required")
    elif args.command == "run": result = run(root, args.output, args.env_file, args.max_calls, args.approved_protocol_sha256)
    else: result = audit(root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
