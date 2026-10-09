"""Minimal JSON POST transport with secret-safe errors and bounded retries."""

from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderRequestError(Exception):
    pass


def post_json(
    endpoint: str, payload: dict[str, Any], *, auth_header: str,
    auth_value: str, timeout: float = 60, retries: int = 2,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Any], int]:
    if timeout <= 0 or retries < 0:
        raise ProviderRequestError("Timeout must be positive and retries nonnegative")
    request = Request(
        endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", auth_header: auth_value},
        method="POST",
    )
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            with opener(request, timeout=timeout) as response:
                result = json.load(response)
            if not isinstance(result, dict):
                raise ProviderRequestError("Provider returned an invalid JSON object")
            return result, round((time.monotonic() - started) * 1000)
        except HTTPError as exc:
            if (exc.code == 429 or 500 <= exc.code <= 599) and attempt < retries:
                sleeper(min(2 ** attempt, 8))
                continue
            raise ProviderRequestError(f"Provider returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError):
            raise ProviderRequestError("Provider transport failed; delivery state is unknown") from None
        except (UnicodeError, json.JSONDecodeError):
            raise ProviderRequestError("Provider returned unreadable JSON") from None
        except ProviderRequestError:
            raise
        except Exception:
            raise ProviderRequestError("Provider request failed unexpectedly") from None
    raise AssertionError("Retry loop exhausted")
