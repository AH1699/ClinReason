"""Stateless MiniMax Chat Completions adapter for draft two-turn cases."""

from __future__ import annotations

from typing import Any, Callable

from .http_json import ProviderRequestError, post_json


ENDPOINT = "https://api.minimax.io/v1/chat/completions"


class MiniMaxConversationProvider:
    provider_name = "minimax"
    endpoint = ENDPOINT
    input_format = "native_role_messages"
    request_parameters = {"input_format": "native_role_messages",
                          "max_completion_tokens": 2048,
                          "provider_storage_setting": "not_exposed"}

    def __init__(
        self, *, model: str, api_key: str, instruction: str,
        timeout: float = 120, retries: int = 0,
        transport: Callable[..., Any] = post_json,
    ) -> None:
        if (not model or any(char.isspace() for char in model)
            or not api_key or any(char.isspace() for char in api_key)
            or not instruction.strip() or timeout <= 0 or retries < 0):
            raise ValueError("Missing or malformed MiniMax conversation settings")
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
        result, latency = self._transport(
            ENDPOINT,
            {"model": self.model_id,
             "messages": [{"role": "system", "content": self._instruction}, *history],
             "max_completion_tokens": 2048},
            auth_header="Authorization", auth_value=f"Bearer {self._key}",
            timeout=self._timeout, retries=self._retries,
        )
        base_response = result.get("base_resp", {}) if isinstance(result, dict) else None
        if (not isinstance(result, dict) or not isinstance(base_response, dict)
            or base_response.get("status_code", 0) != 0):
            raise ProviderRequestError("MiniMax conversation did not complete")
        returned = result.get("model")
        if not isinstance(returned, str) or not returned.strip():
            raise ProviderRequestError("MiniMax response omitted model identity")
        if self.model_version is not None and returned != self.model_version:
            raise ProviderRequestError("MiniMax returned mixed model IDs during a batch")
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderRequestError("MiniMax response contained no choice")
        if choices[0].get("finish_reason") != "stop":
            raise ProviderRequestError("MiniMax response did not finish normally")
        message = choices[0].get("message")
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise ProviderRequestError("MiniMax response contained no answer text")
        self.model_version = returned
        response: dict[str, Any] = {"text": text, "latency_ms": latency}
        usage = result.get("usage")
        if isinstance(usage, dict):
            counters = {
                target: usage[source]
                for target, source in (("input_tokens", "prompt_tokens"),
                                       ("output_tokens", "completion_tokens"),
                                       ("total_tokens", "total_tokens"))
                if type(usage.get(source)) is int and usage[source] >= 0
            }
            if counters:
                response["token_usage"] = counters
        return response
