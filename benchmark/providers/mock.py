from __future__ import annotations

import hashlib
import re
from typing import Any

from .base import CandidateProvider, JudgeProvider


class MockCandidateProvider(CandidateProvider):
    """Deterministic offline provider for wiring tests; not a clinical model."""

    provider_name = "local"
    model_id = "mock-candidate"
    model_version = "0.1"

    def generate(self, candidate_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "text": (
                "Demonstration-only response to a synthetic case. "
                "I would clarify missing context and avoid unsupported conclusions. "
                "This is not medical advice."
            ),
            "finish_reason": "stop",
            "latency_ms": 0,
            "token_usage": {"input": 0, "output": 0},
        }


class MockJudgeProvider(JudgeProvider):
    """Deterministic heuristic judge for local smoke tests only."""

    provider_name = "local"
    model_id = "mock-judge"
    model_version = "0.1"

    def __init__(self, judge_index: int = 0) -> None:
        self.judge_index = judge_index

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", value.lower()))

    def evaluate(
        self, case: dict[str, Any], response: dict[str, Any], rubric: dict[str, Any]
    ) -> dict[str, Any]:
        answer = response["text"]
        answer_tokens = self._tokens(answer)
        requirements = case.get("critical_requirements", [])
        matched = [
            req for req in requirements if self._tokens(req) & answer_tokens
        ]
        ratio = len(matched) / max(1, len(requirements))
        base = min(4, max(0, round(1 + 3 * ratio)))
        # Stable one-point perturbation makes multi-judge aggregation testable.
        digest = int(hashlib.sha256(case["id"].encode()).hexdigest()[:2], 16)
        delta = 1 if self.judge_index and digest % 5 == 0 else 0
        scores: dict[str, Any] = {}
        for dim in rubric["dimensions"]:
            dim_id = dim["id"]
            applicable = dim_id in case.get("applicable_dimensions", [])
            scores[dim_id] = {
                "score": min(4, base + delta) if applicable else None,
                "applicable": applicable,
                "rationale": "Offline deterministic wiring check; not expert validation.",
                "evidence": matched[:2],
            }

        detected = []
        lowered = answer.lower()
        for error in case.get("critical_errors", []):
            if any(term.lower() in lowered for term in error.get("trigger_terms", [])):
                detected.append(
                    {
                        "error_id": error["id"],
                        "severity": error["severity"],
                        "rationale": "Configured trigger term found by mock judge.",
                    }
                )
        return {
            "dimension_scores": scores,
            "critical_errors": detected,
            "overall_rationale": "Mock output for infrastructure validation only.",
            "confidence": 0.55,
            "requires_human_review": bool(detected),
        }

    def pairwise(
        self,
        case: dict[str, Any],
        response_a: dict[str, Any],
        response_b: dict[str, Any],
        rubric: dict[str, Any],
    ) -> dict[str, Any]:
        a = self.evaluate(case, response_a, rubric)
        b = self.evaluate(case, response_b, rubric)
        a_sum = sum(v["score"] or 0 for v in a["dimension_scores"].values())
        b_sum = sum(v["score"] or 0 for v in b["dimension_scores"].values())
        winner = "A" if a_sum > b_sum else "B" if b_sum > a_sum else "tie"
        return {
            "winner": winner,
            "confidence": 0.55,
            "rationale": "Mock pairwise result for wiring validation only.",
        }
