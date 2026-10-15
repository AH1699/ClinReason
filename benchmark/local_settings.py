"""Literal local settings reader; never sources an env file or logs values."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


ALLOWED = {"GROK_API_KEY", "GROK_MODEL", "GEMINI_API_KEY", "GEMINI_JUDGE_MODEL",
           "MINIMAX_API_KEY"}


def read_setting(
    env_file: str | Path, name: str, *, environ: Mapping[str, str] | None = None,
    secret: bool = False,
) -> str:
    if name not in ALLOWED:
        raise ValueError("Unsupported local setting name")
    variables = os.environ if environ is None else environ
    value = variables.get(name, "").strip()
    if not value:
        path = Path(env_file)
        if not path.exists():
            raise ValueError(f"Set {name} in the environment or create .env.local")
        settings: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, separator, literal = stripped.partition("=")
            if not separator or key not in ALLOWED or key in settings:
                raise ValueError(".env.local has an unsupported or duplicate setting")
            literal = literal.strip()
            if len(literal) >= 2 and literal[0] == literal[-1] and literal[0] in "\"'":
                literal = literal[1:-1]
            settings[key] = literal
        value = settings.get(name, "")
    if not value or value == "replace-with-your-key" or not value.isascii() or any(c.isspace() for c in value):
        raise ValueError(f"{name} is missing or malformed")
    if not secret and not all(c.isalnum() or c in "-_. /" for c in value):
        raise ValueError(f"{name} is malformed")
    return value
