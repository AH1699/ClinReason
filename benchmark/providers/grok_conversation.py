"""Stateless, store=false Grok conversation adapter for the draft multi-turn pilot."""

from __future__ import annotations

from typing import Any, Callable

from .grok import ENDPOINT
from .http_json import ProviderRequestError, post_json


class GrokConversationProvider:
    provider_name = "xai-grok"
    endpoint = ENDPOINT

    def __init__(
        self, *, model: str, api_key: str, instruction: str,
        timeout: float = 120, retries: int = 2,
        transport: Callable[..., Any] = post_json,
    ) -> None:
        if not model or any(char.isspace() for char in model):
            raise ValueError("GROK_MODEL must be a nonempty model ID without spaces")
        if not api_key or any(char.isspace() for char in api_key):
            raise ValueError("GROK_API_KEY is missing or malformed")
        if not instruction.strip() or timeout <= 0 or retries < 0:
            raise ValueError("Invalid conversation instruction, timeout, or retries")
        self.model_id = model
        self.model_version: str | None = None
        self._key = api_key
        self._instruction = instruction
        self._timeout = timeout
        self._retries = retries
        self._transport = transport

    def reply(self, history: list[dict[str, str]]) -> dict[str, Any]:
        if not history or not isinstance(history[-1], dict) or history[-1].get("role") != "user" or any(
            not isinstance(item, dict) or set(item) != {"role", "content"}
            or item["role"] not in {"user", "assistant"}
            or not isinstance(item["content"], str) or not item["content"].strip()
            or item["role"] != ("user" if index % 2 == 0 else "assistant")
            for index, item in enumerate(history)
        ):
            raise ValueError("Conversation history must end in a nonempty user turn")
        payload = {
            "model": self.model_id,
            "input": [{"role": "system", "content": self._instruction}, *history],
            "store": False,
        }
        result, latency = self._transport(
            ENDPOINT, payload, auth_header="Authorization", auth_value=f"Bearer {self._key}",
            timeout=self._timeout, retries=self._retries,
        )
        if not isinstance(result, dict) or result.get("status") != "completed":
            raise ProviderRequestError("Grok conversation response did not complete")
        returned = result.get("model")
        if not isinstance(returned, str) or not returned.strip():
            raise ProviderRequestError("Grok conversation response omitted model identity")
        if self.model_version is not None and returned != self.model_version:
            raise ProviderRequestError("Grok returned mixed model IDs during a conversation batch")
        text = "".join(
            content["text"]
            for item in result.get("output", []) if isinstance(item, dict) and item.get("type") == "message"
            for content in item.get("content", []) if isinstance(content, dict)
            and content.get("type") == "output_text" and isinstance(content.get("text"), str)
        )
        if not text.strip():
            raise ProviderRequestError("Grok conversation response contained no answer text")
        self.model_version = returned
        response: dict[str, Any] = {"text": text, "latency_ms": latency}
        usage = result.get("usage")
        if isinstance(usage, dict):
            counters = {key: usage[key] for key in ("input_tokens", "output_tokens", "total_tokens")
                        if type(usage.get(key)) is int and usage[key] >= 0}
            if counters:
                response["token_usage"] = counters
        return response
