"""Stateless Gemini adapter for the draft two-turn patient-facing pilot."""

from __future__ import annotations

from typing import Any, Callable

from .gemini import ENDPOINT
from .http_json import ProviderRequestError, post_json


class GeminiConversationProvider:
    provider_name = "google-gemini"
    endpoint = ENDPOINT
    input_format = "role_labeled_visible_history_text_v1"

    def __init__(
        self, *, model: str, api_key: str, instruction: str,
        timeout: float = 120, retries: int = 2,
        transport: Callable[..., Any] = post_json,
    ) -> None:
        if not model or any(char.isspace() for char in model):
            raise ValueError("Gemini model must be a nonempty ID without spaces")
        if not api_key or any(char.isspace() for char in api_key):
            raise ValueError("GEMINI_API_KEY is missing or malformed")
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
        if not history or any(
            not isinstance(item, dict) or set(item) != {"role", "content"}
            or item["role"] != ("user" if index % 2 == 0 else "assistant")
            or not isinstance(item["content"], str) or not item["content"].strip()
            for index, item in enumerate(history)
        ) or history[-1]["role"] != "user":
            raise ValueError("Conversation history must alternate and end in a nonempty user turn")
        # The Interactions API accepts text input. Explicit delimiters keep the local,
        # stateless transcript visible without relying on provider-side storage.
        sections = [
            f"<{item['role']} turn=\"{index + 1}\">\n{item['content']}\n</{item['role']}>"
            for index, item in enumerate(history)
        ]
        payload = {
            "model": self.model_id,
            "system_instruction": self._instruction,
            "input": "Conversation so far (reply only to the final user turn):\n\n" + "\n\n".join(sections),
            "store": False,
        }
        result, latency = self._transport(
            ENDPOINT, payload, auth_header="x-goog-api-key", auth_value=self._key,
            timeout=self._timeout, retries=self._retries,
        )
        if not isinstance(result, dict) or result.get("status") != "completed":
            raise ProviderRequestError("Gemini conversation response did not complete")
        returned = result.get("model")
        if not isinstance(returned, str) or not returned.strip():
            raise ProviderRequestError("Gemini conversation response omitted model identity")
        if self.model_version is not None and returned != self.model_version:
            raise ProviderRequestError("Gemini returned mixed model IDs during a conversation batch")
        text = "".join(
            content["text"]
            for step in result.get("steps", []) if isinstance(step, dict) and step.get("type") == "model_output"
            for content in step.get("content", []) if isinstance(content, dict)
            and content.get("type") == "text" and isinstance(content.get("text"), str)
        )
        if not text.strip():
            raise ProviderRequestError("Gemini conversation response contained no answer text")
        self.model_version = returned
        response: dict[str, Any] = {"text": text, "latency_ms": latency}
        usage = result.get("usage")
        if isinstance(usage, dict):
            counters = {
                target: usage[source]
                for target, source in (("input_tokens", "total_input_tokens"),
                                       ("output_tokens", "total_output_tokens"))
                if type(usage.get(source)) is int and usage[source] >= 0
            }
            if counters:
                response["token_usage"] = counters
        return response
