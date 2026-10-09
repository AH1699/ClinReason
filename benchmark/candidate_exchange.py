"""Prompt-only export and exact-revision response import for local pilots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_jsonl
from .db import connect, dump, new_id, now_iso
from .pipeline import bootstrap, create_run
from .reviews import case_content_hash
from .validation import validate_dataset


EXCHANGE_VERSION = "0.1.0"
ANSWER_REQUIRED = {"case_id", "case_version", "case_content_hash", "text"}
ANSWER_OPTIONAL = {"finish_reason", "latency_ms", "token_usage"}


def _checked_cases(
    cases_path: str | Path, rubric: dict[str, Any], authoring: dict[str, Any]
) -> list[dict[str, Any]]:
    result = validate_dataset(cases_path, rubric, authoring)
    if not result["valid"]:
        raise ValueError(f"Dataset has {result['error_count']} development validation errors")
    return load_jsonl(cases_path)


def prompt_rows(
    cases: list[dict[str, Any]], *, instruction: str, prompt_template_version: str
) -> list[dict[str, Any]]:
    """Allowlist only fields the candidate may see; no case object is forwarded."""
    return [
        {
            "exchange_version": EXCHANGE_VERSION,
            "case_id": case["id"],
            "case_version": case["version"],
            "case_content_hash": case_content_hash(case),
            "language": case["language"],
            "prompt_template_version": prompt_template_version,
            "instruction": instruction,
            "prompt": case["prompt"],
        }
        for case in sorted(cases, key=lambda item: item["id"])
    ]


def export_prompts(
    cases_path: str | Path,
    output_path: str | Path,
    *,
    rubric: dict[str, Any],
    authoring: dict[str, Any],
    instruction: str,
    prompt_template_version: str,
) -> int:
    cases = _checked_cases(cases_path, rubric, authoring)
    target = Path(output_path)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite prompt export: {target}")
    rows = prompt_rows(cases, instruction=instruction, prompt_template_version=prompt_template_version)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    return len(rows)


def validate_answers(
    answers_path: str | Path, cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    expected = {case["id"]: case for case in cases}
    answers = load_jsonl(answers_path)
    seen: set[str] = set()
    for index, answer in enumerate(answers, 1):
        if not isinstance(answer, dict):
            raise ValueError(f"Answer line {index} must be an object")
        missing = ANSWER_REQUIRED - set(answer)
        unknown = set(answer) - ANSWER_REQUIRED - ANSWER_OPTIONAL
        if missing or unknown:
            raise ValueError(f"Answer line {index}: missing {sorted(missing)}, unknown {sorted(unknown)}")
        case_id = answer["case_id"]
        if not isinstance(case_id, str) or case_id not in expected:
            raise ValueError(f"Answer line {index} has an unknown case ID")
        if case_id in seen:
            raise ValueError(f"Duplicate answer for {case_id}")
        seen.add(case_id)
        case = expected[case_id]
        if answer["case_version"] != case["version"] or answer["case_content_hash"] != case_content_hash(case):
            raise ValueError(f"Stale or mismatched case revision for {case_id}")
        if not isinstance(answer["text"], str) or not answer["text"].strip():
            raise ValueError(f"Empty answer text for {case_id}")
        if "finish_reason" in answer and answer["finish_reason"] is not None and not isinstance(answer["finish_reason"], str):
            raise ValueError(f"Invalid finish_reason for {case_id}")
        latency = answer.get("latency_ms")
        if latency is not None and (type(latency) is not int or latency < 0):
            raise ValueError(f"Invalid latency_ms for {case_id}")
        usage = answer.get("token_usage")
        if usage is not None and (
            not isinstance(usage, dict)
            or any(not isinstance(key, str) or type(value) is not int or value < 0 for key, value in usage.items())
        ):
            raise ValueError(f"Invalid token_usage for {case_id}")
    missing_ids = sorted(set(expected) - seen)
    if missing_ids:
        raise ValueError(f"Missing answers for {len(missing_ids)} cases: {', '.join(missing_ids)}")
    return answers


def import_answers(
    db_path: str | Path,
    cases_path: str | Path,
    answers_path: str | Path,
    *,
    config: dict[str, Any],
    rubric: dict[str, Any],
    provider: str,
    model_id: str,
    model_version: str,
) -> str:
    for field, value in (("provider", provider), ("model_id", model_id), ("model_version", model_version)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a nonempty string")
    cases = _checked_cases(cases_path, rubric, config.get("authoring", {}))
    answers = validate_answers(answers_path, cases)
    bootstrap(db_path, cases_path)
    run_id = create_run(db_path, config)
    with connect(db_path) as conn:
        for answer in answers:
            payload = {
                "text": answer["text"],
                "finish_reason": answer.get("finish_reason"),
                "latency_ms": answer.get("latency_ms"),
                "token_usage": answer.get("token_usage"),
            }
            conn.execute(
                """INSERT INTO model_responses
                (id, run_id, case_id, case_version, provider, model_id, model_version,
                 prompt_template_version, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_id("resp"), run_id, answer["case_id"], answer["case_version"],
                    provider, model_id, model_version, config["prompt_template_version"],
                    dump(payload), now_iso(),
                ),
            )
    return run_id
