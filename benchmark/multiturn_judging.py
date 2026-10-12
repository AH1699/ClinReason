"""Provisional structured judge and gated scores for scripted two-turn cases."""

from __future__ import annotations

import json
from typing import Any, Callable

from .providers.gemini import ENDPOINT
from .providers.http_json import ProviderRequestError, post_json


STAGES = ("initial", "update")


def judgment_schema() -> dict[str, Any]:
    stage = {
        "type": "object",
        "properties": {
            "stage_id": {"type": "string", "enum": list(STAGES)},
            "safety": {"type": "integer", "minimum": 0, "maximum": 4},
            "requirements": {"type": "integer", "minimum": 0, "maximum": 4},
            "rationale": {"type": "string"},
        },
        "required": ["stage_id", "safety", "requirements", "rationale"],
        "additionalProperties": False,
    }
    error = {
        "type": "object",
        "properties": {
            "stage_id": {"type": "string", "enum": list(STAGES)},
            "error_id": {"type": "string"},
            "severity": {"type": "integer", "minimum": 1, "maximum": 3},
            "rationale": {"type": "string"},
        },
        "required": ["stage_id", "error_id", "severity", "rationale"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "stage_scores": {"type": "array", "items": stage, "minItems": 2, "maxItems": 2},
            "revision_score": {"type": "integer", "minimum": 0, "maximum": 4},
            "critical_errors": {"type": "array", "items": error},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "requires_human_review": {"type": "boolean"},
            "overall_rationale": {"type": "string"},
        },
        "required": ["stage_scores", "revision_score", "critical_errors", "confidence",
                     "requires_human_review", "overall_rationale"],
        "additionalProperties": False,
    }


def validate_judgment(judgment: Any, packet: dict[str, Any]) -> dict[str, Any]:
    expected = set(judgment_schema()["required"])
    if not isinstance(judgment, dict) or set(judgment) != expected:
        raise ProviderRequestError("Multi-turn judgment has invalid top-level fields")
    scores = judgment["stage_scores"]
    if not isinstance(scores, list) or len(scores) != 2 or [item.get("stage_id") for item in scores if isinstance(item, dict)] != list(STAGES):
        raise ProviderRequestError("Multi-turn judgment must score initial then update")
    for item in scores:
        if set(item) != {"stage_id", "safety", "requirements", "rationale"} or any(
            type(item[key]) is not int or not 0 <= item[key] <= 4 for key in ("safety", "requirements")
        ) or not isinstance(item["rationale"], str) or not item["rationale"].strip():
            raise ProviderRequestError("Multi-turn judgment has invalid stage scores")
    if type(judgment["revision_score"]) is not int or not 0 <= judgment["revision_score"] <= 4:
        raise ProviderRequestError("Multi-turn judgment has invalid revision score")
    configured = {
        (turn["stage_id"], error["id"]): error["severity"]
        for turn in packet["turn_labels"] for error in turn["critical_errors"]
    }
    errors = judgment["critical_errors"]
    if not isinstance(errors, list):
        raise ProviderRequestError("Multi-turn judgment has invalid critical errors")
    seen = set()
    for error in errors:
        if not isinstance(error, dict) or set(error) != {"stage_id", "error_id", "severity", "rationale"}:
            raise ProviderRequestError("Multi-turn judgment has malformed critical error")
        key = (error["stage_id"], error["error_id"])
        if key not in configured or key in seen or type(error["severity"]) is not int or error["severity"] != configured[key]:
            raise ProviderRequestError("Multi-turn judgment invented or changed a critical error")
        if not isinstance(error["rationale"], str) or not error["rationale"].strip():
            raise ProviderRequestError("Multi-turn judgment omitted critical-error rationale")
        seen.add(key)
    if type(judgment["confidence"]) not in (int, float) or not 0 <= judgment["confidence"] <= 1:
        raise ProviderRequestError("Multi-turn judgment has invalid confidence")
    if type(judgment["requires_human_review"]) is not bool or not isinstance(judgment["overall_rationale"], str) or not judgment["overall_rationale"].strip():
        raise ProviderRequestError("Multi-turn judgment has invalid review flag or rationale")
    return judgment


def score_judgment(judgment: dict[str, Any], packet: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    validate_judgment(judgment, packet)
    stage_weights = rubric["stage_component_weights"]
    conversation = rubric["conversation_weights"]
    if (set(stage_weights) != {"safety", "requirements"}
        or set(conversation) != {"initial", "update", "revision"}
        or any(type(weight) not in (int, float) or weight < 0 for weight in [*stage_weights.values(), *conversation.values()])
        or abs(sum(stage_weights.values()) - 1) > 1e-9
        or abs(sum(conversation.values()) - 1) > 1e-9):
        raise ValueError("Multi-turn rubric weights must each sum to one")
    if rubric["scale_max"] != 4:
        raise ValueError("Unsupported multi-turn score scale")
    stage_scores = {}
    for item in judgment["stage_scores"]:
        stage_scores[item["stage_id"]] = (
            item["safety"] * stage_weights["safety"]
            + item["requirements"] * stage_weights["requirements"]
        ) / rubric["scale_max"] * 100
    revision = judgment["revision_score"] / rubric["scale_max"] * 100
    raw = (stage_scores["initial"] * conversation["initial"]
           + stage_scores["update"] * conversation["update"]
           + revision * conversation["revision"])
    deduction = 0.0
    caps = []
    hard_fail = False
    for error in judgment["critical_errors"]:
        rule = rubric["critical_error_rules"][str(error["severity"])]
        deduction += rule.get("deduction", 0)
        if "cap" in rule:
            caps.append(rule["cap"])
        hard_fail = hard_fail or rule.get("hard_fail", False)
    gated = min([raw - deduction, *caps]) if caps else raw - deduction
    gated = max(0.0, round(gated, 2))
    return {
        "case_id": packet["case_id"], "case_content_hash": packet["case_content_hash"],
        "status": "experimental_unvalidated_single_ai_judge",
        "raw_score": round(raw, 2), "gated_score": gated,
        "stage_scores": {key: round(value, 2) for key, value in stage_scores.items()},
        "revision_score": round(revision, 2),
        "hard_fail": bool(hard_fail),
        "pass": not hard_fail and gated >= rubric["pass_threshold"],
        "critical_errors": judgment["critical_errors"],
        "review_status": "required",
        "review_reasons": ["single_uncalibrated_ai_judge", "draft_case_and_translation"]
        + (["judge_requested_review"] if judgment["requires_human_review"] else []),
    }


class GeminiMultiturnJudge:
    provider_name = "google-gemini"

    def __init__(
        self, *, model: str, api_key: str, instruction: str,
        timeout: float = 120, retries: int = 2,
        transport: Callable[..., Any] = post_json,
    ) -> None:
        if not model or any(char.isspace() for char in model) or not api_key or any(char.isspace() for char in api_key) or not instruction.strip():
            raise ValueError("Missing or malformed multi-turn judge settings")
        self.model_id = model
        self.model_version: str | None = None
        self._key = api_key
        self._instruction = instruction
        self._timeout = timeout
        self._retries = retries
        self._transport = transport

    def evaluate(self, packet: dict[str, Any]) -> dict[str, Any]:
        result, _latency = self._transport(
            ENDPOINT,
            {"model": self.model_id, "system_instruction": self._instruction,
             "input": json.dumps(packet, ensure_ascii=False), "store": False,
             "response_format": {"type": "text", "mime_type": "application/json",
                                 "schema": judgment_schema()}},
            auth_header="x-goog-api-key", auth_value=self._key,
            timeout=self._timeout, retries=self._retries,
        )
        if not isinstance(result, dict) or result.get("status") != "completed":
            raise ProviderRequestError("Gemini multi-turn judgment did not complete")
        returned = result.get("model")
        if not isinstance(returned, str) or not returned.strip():
            raise ProviderRequestError("Gemini multi-turn judgment omitted model identity")
        if self.model_version is not None and returned != self.model_version:
            raise ProviderRequestError("Gemini returned mixed model IDs")
        text = "".join(
            content["text"]
            for step in result.get("steps", []) if isinstance(step, dict)
            and step.get("type") == "model_output"
            for content in step.get("content", []) if isinstance(content, dict)
            and content.get("type") == "text" and isinstance(content.get("text"), str)
        )
        try:
            judgment = json.loads(text)
        except (ValueError, TypeError):
            raise ProviderRequestError("Gemini multi-turn judgment was not JSON") from None
        validated = validate_judgment(judgment, packet)
        self.model_version = returned
        return validated
