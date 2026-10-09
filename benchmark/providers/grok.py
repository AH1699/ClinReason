"""Grok candidate-only runner using xAI Responses API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .http_json import ProviderRequestError, post_json
from ..candidate_exchange import prompt_rows
from ..config import load_jsonl
from ..validation import validate_dataset


ENDPOINT = "https://api.x.ai/v1/responses"


def candidate_rows(
    cases_path: str | Path, *, rubric: dict[str, Any], authoring: dict[str, Any],
    instruction: str, prompt_template_version: str,
) -> list[dict[str, Any]]:
    validation = validate_dataset(cases_path, rubric, authoring)
    if not validation["valid"]:
        raise ValueError(f"Dataset has {validation['error_count']} development validation errors")
    return prompt_rows(load_jsonl(cases_path), instruction=instruction,
                       prompt_template_version=prompt_template_version)


def grok_answer(
    row: dict[str, Any], *, model: str, api_key: str, timeout: float = 120,
    retries: int = 2, transport: Callable[..., Any] = post_json,
) -> tuple[dict[str, Any], str]:
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": row["instruction"]},
            {"role": "user", "content": row["prompt"]},
        ],
        "store": False,
    }
    result, latency = transport(
        ENDPOINT, payload, auth_header="Authorization", auth_value=f"Bearer {api_key}",
        timeout=timeout, retries=retries,
    )
    if result.get("status") != "completed":
        raise ProviderRequestError("Grok response did not complete")
    returned_model = result.get("model")
    if not isinstance(returned_model, str) or not returned_model.strip():
        raise ProviderRequestError("Grok response omitted model identity")
    pieces = [
        content["text"]
        for item in result.get("output", []) if isinstance(item, dict) and item.get("type") == "message"
        for content in item.get("content", []) if isinstance(content, dict)
        and content.get("type") == "output_text" and isinstance(content.get("text"), str)
    ]
    text = "".join(pieces)
    if not text.strip():
        raise ProviderRequestError("Grok returned no answer text")
    answer = {
        "case_id": row["case_id"], "case_version": row["case_version"],
        "case_content_hash": row["case_content_hash"], "text": text,
        "finish_reason": "completed", "latency_ms": latency,
    }
    usage = result.get("usage")
    if isinstance(usage, dict):
        counters = {
            name: usage[source]
            for name, source in (("input_tokens", "input_tokens"),
                                 ("output_tokens", "output_tokens"),
                                 ("total_tokens", "total_tokens"))
            if type(usage.get(source)) is int and usage[source] >= 0
        }
        if counters:
            answer["token_usage"] = counters
    return answer, returned_model


def run_grok(
    rows: list[dict[str, Any]], output_path: str | Path, *, model: str, api_key: str,
    limit: int = 1, timeout: float = 120, retries: int = 2,
    transport: Callable[..., Any] = post_json,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    if not model or any(c.isspace() for c in model):
        raise ValueError("GROK_MODEL must be a nonempty model ID without spaces")
    if not api_key or any(c.isspace() for c in api_key):
        raise ValueError("GROK_API_KEY is missing or malformed")
    if type(limit) is not int or not 1 <= limit <= len(rows):
        raise ValueError(f"--limit must be between 1 and {len(rows)}")
    if timeout <= 0 or retries < 0:
        raise ValueError("Timeout must be positive and retries nonnegative")
    output = Path(output_path)
    manifest_path = output.with_suffix(".manifest.json")
    if output.exists() or manifest_path.exists():
        raise FileExistsError("Answer or manifest output already exists; choose a new --output path")
    answers: list[dict[str, Any]] = []
    returned_model: str | None = None
    for index, row in enumerate(rows[:limit], 1):
        answer, actual_model = grok_answer(
            row, model=model, api_key=api_key, timeout=timeout,
            retries=retries, transport=transport,
        )
        if returned_model is not None and actual_model != returned_model:
            raise ProviderRequestError("Grok returned mixed model IDs; no answer file was written")
        returned_model = actual_model
        answers.append(answer)
        if progress:
            progress(index, limit, row["case_id"])
    manifest = {
        "provider": "xai-grok", "requested_model": model, "returned_model": returned_model,
        "endpoint": ENDPOINT, "store": False, "case_count": limit,
        "total_available_cases": len(rows), "timeout_seconds": timeout,
        "max_http_retries": retries,
        "prompt_template_version": rows[0]["prompt_template_version"],
        "case_revisions": [
            {key: row[key] for key in ("case_id", "case_version", "case_content_hash")}
            for row in rows[:limit]
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for answer in answers:
            handle.write(json.dumps(answer, ensure_ascii=False, sort_keys=True) + "\n")
    with manifest_path.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {"output": str(output), "manifest": str(manifest_path), **manifest}
