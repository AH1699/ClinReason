"""Provisional Gemini judge; strict shape and case-bound semantic checks."""

from __future__ import annotations

import json
from typing import Any, Callable

from .base import JudgeProvider
from .gemini import ENDPOINT
from .http_json import ProviderRequestError, post_json


def judgment_schema(rubric: dict[str, Any]) -> dict[str, Any]:
    dimensions = {}
    for definition in rubric["dimensions"]:
        dimensions[definition["id"]] = {
            "type": "object",
            "properties": {
                "score": {"type": ["number", "null"], "minimum": 0, "maximum": 4},
                "applicable": {"type": "boolean"},
                "rationale": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["score", "applicable", "rationale", "evidence"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "dimension_scores": {
                "type": "object", "properties": dimensions,
                "required": list(dimensions), "additionalProperties": False,
            },
            "critical_errors": {
                "type": "array", "items": {
                    "type": "object", "properties": {
                        "error_id": {"type": "string"},
                        "severity": {"type": "integer", "minimum": 1, "maximum": 3},
                        "rationale": {"type": "string"},
                    },
                    "required": ["error_id", "severity", "rationale"],
                    "additionalProperties": False,
                },
            },
            "overall_rationale": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "requires_human_review": {"type": "boolean"},
        },
        "required": ["dimension_scores", "critical_errors", "overall_rationale",
                     "confidence", "requires_human_review"],
        "additionalProperties": False,
    }


def validate_judgment(
    output: Any, case: dict[str, Any], rubric: dict[str, Any]
) -> dict[str, Any]:
    required = {"dimension_scores", "critical_errors", "overall_rationale",
                "confidence", "requires_human_review"}
    if not isinstance(output, dict) or set(output) != required:
        raise ProviderRequestError("Gemini judgment has invalid top-level fields")
    dimensions = output["dimension_scores"]
    expected = {item["id"] for item in rubric["dimensions"]}
    if not isinstance(dimensions, dict) or set(dimensions) != expected:
        raise ProviderRequestError("Gemini judgment has mismatched rubric dimensions")
    applicable = set(case["applicable_dimensions"])
    for name, item in dimensions.items():
        if not isinstance(item, dict) or set(item) != {"score", "applicable", "rationale", "evidence"}:
            raise ProviderRequestError("Gemini judgment has an invalid dimension item")
        if type(item["applicable"]) is not bool or item["applicable"] != (name in applicable):
            raise ProviderRequestError("Gemini changed dimension applicability")
        score = item["score"]
        if name in applicable:
            if type(score) not in (int, float) or not 0 <= score <= 4:
                raise ProviderRequestError("Gemini supplied an invalid dimension score")
        elif score is not None:
            raise ProviderRequestError("Gemini scored an inapplicable dimension")
        if not isinstance(item["rationale"], str) or not item["rationale"].strip():
            raise ProviderRequestError("Gemini omitted dimension rationale")
        if not isinstance(item["evidence"], list) or any(not isinstance(v, str) for v in item["evidence"]):
            raise ProviderRequestError("Gemini supplied invalid dimension evidence")
    errors = output["critical_errors"]
    configured = {item["id"]: item["severity"] for item in case["critical_errors"]}
    if not isinstance(errors, list):
        raise ProviderRequestError("Gemini supplied invalid critical errors")
    seen: set[str] = set()
    for item in errors:
        if not isinstance(item, dict) or set(item) != {"error_id", "severity", "rationale"}:
            raise ProviderRequestError("Gemini supplied an invalid critical-error item")
        error_id = item["error_id"]
        if not isinstance(error_id, str) or error_id not in configured or error_id in seen:
            raise ProviderRequestError("Gemini supplied an unknown or duplicate critical-error ID")
        seen.add(error_id)
        if type(item["severity"]) is not int or item["severity"] != configured[error_id]:
            raise ProviderRequestError("Gemini changed a configured critical-error severity")
        if not isinstance(item["rationale"], str) or not item["rationale"].strip():
            raise ProviderRequestError("Gemini omitted critical-error rationale")
    if not isinstance(output["overall_rationale"], str) or not output["overall_rationale"].strip():
        raise ProviderRequestError("Gemini omitted overall rationale")
    confidence = output["confidence"]
    if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
        raise ProviderRequestError("Gemini supplied invalid confidence")
    if type(output["requires_human_review"]) is not bool:
        raise ProviderRequestError("Gemini supplied invalid review flag")
    return output


class GeminiJudgeProvider(JudgeProvider):
    provider_name = "google-gemini"

    def __init__(
        self, *, model: str, api_key: str, instruction: str,
        timeout: float = 120, retries: int = 2,
        expected_version: str | None = None,
        transport: Callable[..., Any] = post_json,
    ) -> None:
        self.model_id = model
        self.model_version = expected_version or model
        self._expected_version = expected_version
        self._key = api_key
        self._instruction = instruction
        self._timeout = timeout
        self._retries = retries
        self._transport = transport

    def evaluate(
        self, case: dict[str, Any], response: dict[str, Any], rubric: dict[str, Any]
    ) -> dict[str, Any]:
        case_view = {
            "case_id": case["id"], "language": case["language"],
            "case_prompt": case["prompt"],
            "draft_reference_answer": case["reference_answer"],
            "critical_requirements": case["critical_requirements"],
            "critical_errors": [
                {key: error[key] for key in ("id", "severity", "description")}
                for error in case["critical_errors"]
            ],
            "applicable_dimensions": case["applicable_dimensions"],
            "candidate_response": response["text"],
            "rubric": rubric,
        }
        result, _latency = self._transport(
            ENDPOINT,
            {"model": self.model_id, "system_instruction": self._instruction,
             "input": json.dumps(case_view, ensure_ascii=False), "store": False,
             "response_format": {"type": "text", "mime_type": "application/json",
                                 "schema": judgment_schema(rubric)}},
            auth_header="x-goog-api-key", auth_value=self._key,
            timeout=self._timeout, retries=self._retries,
        )
        if result.get("status") != "completed":
            raise ProviderRequestError("Gemini judgment did not complete")
        returned = result.get("model")
        if not isinstance(returned, str) or not returned.strip():
            raise ProviderRequestError("Gemini judgment omitted model identity")
        if self._expected_version is not None and returned != self._expected_version:
            raise ProviderRequestError("Gemini returned mixed model IDs")
        text = "".join(
            content["text"]
            for step in result.get("steps", []) if isinstance(step, dict)
            and step.get("type") == "model_output"
            for content in step.get("content", []) if isinstance(content, dict)
            and content.get("type") == "text" and isinstance(content.get("text"), str)
        )
        try:
            output = json.loads(text)
        except (ValueError, TypeError):
            raise ProviderRequestError("Gemini judgment is not JSON") from None
        validated = validate_judgment(output, case, rubric)
        self.model_version = returned
        self._expected_version = returned
        return validated
