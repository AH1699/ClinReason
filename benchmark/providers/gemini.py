"""Opt-in Gemini candidate runner using only the candidate-visible case fields."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..candidate_exchange import prompt_rows
from ..config import load_jsonl
from ..local_settings import read_setting
from ..validation import validate_dataset
from ..provenance import sha256_json, sha256_text


ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"


class GeminiRunError(Exception):
    """A safe-to-display runner error; never includes API response bodies."""


def _check_key(value: str) -> str:
    if not value or value == "replace-with-your-key" or not value.isascii() or any(char.isspace() for char in value):
        raise GeminiRunError("GEMINI_API_KEY is missing or malformed; no API call was made.")
    return value


def local_api_key(env_file: str | Path, environ: Mapping[str, str] | None = None) -> str:
    """Read a literal GEMINI_API_KEY value; never execute an env file as shell code."""
    try:
        return read_setting(env_file, "GEMINI_API_KEY", environ=environ, secret=True)
    except ValueError as exc:
        raise GeminiRunError(str(exc)) from None


def candidate_rows(
    cases_path: str | Path, *, rubric: dict[str, Any], authoring: dict[str, Any],
    instruction: str, prompt_template_version: str,
) -> list[dict[str, Any]]:
    validation = validate_dataset(cases_path, rubric, authoring)
    if not validation["valid"]:
        raise GeminiRunError(f"Dataset has {validation['error_count']} development validation errors.")
    return prompt_rows(
        load_jsonl(cases_path), instruction=instruction,
        prompt_template_version=prompt_template_version,
    )


def _request(
    row: dict[str, Any], *, model: str, api_key: str, timeout: float, retries: int,
    opener: Callable[..., Any], sleeper: Callable[[float], None],
) -> tuple[dict[str, Any], int]:
    payload = {
        "model": model,
        "system_instruction": row["instruction"],
        "input": row["prompt"],
        "store": False,
    }
    request = Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            with opener(request, timeout=timeout) as response:
                result = json.load(response)
            return result, round((time.monotonic() - started) * 1000)
        except HTTPError as exc:
            if (exc.code == 429 or 500 <= exc.code <= 599) and attempt < retries:
                sleeper(min(2 ** attempt, 8))
                continue
            raise GeminiRunError(f"Gemini API returned HTTP {exc.code}; no answer file was written.") from None
        except (URLError, TimeoutError, OSError):
            # Unknown delivery state: a retry could duplicate a charged request.
            raise GeminiRunError("Gemini transport failed; delivery state is unknown. No answer file was written.") from None
        except (UnicodeError, json.JSONDecodeError):
            raise GeminiRunError("Gemini returned an unreadable response; no answer file was written.") from None
        except Exception:
            raise GeminiRunError("Gemini request failed unexpectedly; no answer file was written.") from None
    raise AssertionError("retry loop exhausted")


def _answer(row: dict[str, Any], result: Any, latency_ms: int) -> tuple[dict[str, Any], str]:
    if not isinstance(result, dict) or result.get("status") != "completed":
        raise GeminiRunError("Gemini interaction did not complete; no answer file was written.")
    model = result.get("model")
    if not isinstance(model, str) or not model.strip():
        raise GeminiRunError("Gemini response omitted model identity; no answer file was written.")
    pieces: list[str] = []
    for step in result.get("steps", []):
        if isinstance(step, dict) and step.get("type") == "model_output":
            for content in step.get("content", []):
                if isinstance(content, dict) and content.get("type") == "text":
                    if isinstance(content.get("text"), str):
                        pieces.append(content["text"])
    text = "".join(pieces)
    if not text.strip():
        raise GeminiRunError("Gemini returned no final answer text; no answer file was written.")
    answer = {
        "case_id": row["case_id"],
        "case_version": row["case_version"],
        "case_content_hash": row["case_content_hash"],
        "text": text,
        "finish_reason": "completed",
        "latency_ms": latency_ms,
    }
    usage = result.get("usage")
    if isinstance(usage, dict):
        counters = {
            name: usage[source]
            for name, source in (
                ("input_tokens", "total_input_tokens"),
                ("output_tokens", "total_output_tokens"),
                ("thought_tokens", "total_thought_tokens"),
                ("total_tokens", "total_tokens"),
            )
            if type(usage.get(source)) is int and usage[source] >= 0
        }
        if counters:
            answer["token_usage"] = counters
    return answer, model


def run_gemini(
    rows: list[dict[str, Any]], output_path: str | Path, *, model: str, api_key: str,
    limit: int = 1, timeout: float = 60, retries: int = 2,
    opener: Callable[..., Any] = urlopen, sleeper: Callable[[float], None] = time.sleep,
    progress: Callable[[int, int, str], None] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(model, str) or not model.strip() or any(char.isspace() for char in model):
        raise GeminiRunError("Provide an exact Gemini model ID without spaces.")
    _check_key(api_key)
    if type(limit) is not int or not 1 <= limit <= len(rows):
        raise GeminiRunError(f"--limit must be between 1 and {len(rows)}.")
    if timeout <= 0 or retries < 0:
        raise GeminiRunError("Timeout must be positive and retries nonnegative.")
    output = Path(output_path)
    manifest_path = output.with_suffix(".manifest.json")
    if output.exists() or manifest_path.exists():
        raise FileExistsError("Answer or manifest output already exists; choose a new --output path.")
    answers: list[dict[str, Any]] = []
    returned_model: str | None = None
    for index, row in enumerate(rows[:limit], 1):
        result, latency = _request(
            row, model=model, api_key=api_key, timeout=timeout,
            retries=retries, opener=opener, sleeper=sleeper,
        )
        answer, response_model = _answer(row, result, latency)
        if returned_model is not None and response_model != returned_model:
            raise GeminiRunError("Gemini returned mixed model IDs; no answer file was written.")
        returned_model = response_model
        answers.append(answer)
        if progress:
            progress(index, limit, row["case_id"])
    manifest = {
        "provider": "google-gemini",
        "requested_model": model,
        "returned_model": returned_model,
        "endpoint": ENDPOINT,
        "store": False,
        "actual_request_parameters": {"store": False},
        "sampling_policy": "provider_default_unpinned",
        "case_count": limit,
        "total_available_cases": len(rows),
        "timeout_seconds": timeout,
        "max_http_retries": retries,
        "prompt_template_version": rows[0]["prompt_template_version"],
        "candidate_instruction_sha256": sha256_text(rows[0]["instruction"]),
        "candidate_visible_inputs_sha256": sha256_json(rows[:limit]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance": provenance or {},
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
