from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CandidateProvider(ABC):
    """Adapter contract for a model being benchmarked."""

    provider_name: str
    model_id: str
    model_version: str

    @abstractmethod
    def generate(self, case: dict[str, Any]) -> dict[str, Any]:
        """Return at least {text: str}; usage/latency metadata is optional."""


class JudgeProvider(ABC):
    """Adapter contract for an evaluator model."""

    provider_name: str
    model_id: str
    model_version: str

    @abstractmethod
    def evaluate(
        self, case: dict[str, Any], response: dict[str, Any], rubric: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a structured judgment matching schemas/judge-output.schema.json."""

    def pairwise(
        self,
        case: dict[str, Any],
        response_a: dict[str, Any],
        response_b: dict[str, Any],
        rubric: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("Pairwise evaluation is optional for providers")
