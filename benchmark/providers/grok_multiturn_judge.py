"""Independent-provider structured judge for draft two-turn diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ..multiturn_judging import judgment_schema, validate_judgment
from .grok import ENDPOINT
from .http_json import ProviderRequestError, post_json


class GrokMultiturnJudge:
    provider_name = "xai-grok"

    def __init__(
        self, *, model: str, api_key: str, instruction: str,
        timeout: float = 120, retries: int = 2,
        transport: Callable[..., Any] = post_json,
    ) -> None:
        if (not model or any(char.isspace() for char in model)
            or not api_key or any(char.isspace() for char in api_key)
            or not instruction.strip() or timeout <= 0 or retries < 0):
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
            {
                "model": self.model_id,
                "input": [
                    {"role": "system", "content": self._instruction},
                    {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
                ],
                "store": False,
                "text": {"format": {"type": "json_schema", "name": "multiturn_judgment",
                                    "schema": judgment_schema(packet), "strict": True}},
            },
            auth_header="Authorization", auth_value=f"Bearer {self._key}",
            timeout=self._timeout, retries=self._retries,
        )
        if not isinstance(result, dict) or result.get("status") != "completed":
            raise ProviderRequestError("Grok multi-turn judgment did not complete")
        returned = result.get("model")
        if not isinstance(returned, str) or not returned.strip():
            raise ProviderRequestError("Grok multi-turn judgment omitted model identity")
        if self.model_version is not None and returned != self.model_version:
            raise ProviderRequestError("Grok returned mixed model IDs in the judgment batch")
        text = "".join(
            content["text"]
            for item in result.get("output", []) if isinstance(item, dict) and item.get("type") == "message"
            for content in item.get("content", []) if isinstance(content, dict)
            and content.get("type") == "output_text" and isinstance(content.get("text"), str)
        )
        try:
            judgment = json.loads(text)
        except (ValueError, TypeError):
            raise ProviderRequestError("Grok multi-turn judgment was not JSON") from None
        try:
            validated = validate_judgment(judgment, packet)
        except ProviderRequestError:
            rejected = getattr(self, "rejected_output_path", None)
            if rejected is not None:
                with Path(rejected).open("x", encoding="utf-8") as handle:
                    json.dump(judgment, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
            raise
        self.model_version = returned
        return validated
