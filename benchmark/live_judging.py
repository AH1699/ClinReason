"""Resumable one-judge pilot for imported Grok candidate answers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .db import connect, dump, new_id, now_iso
from .pipeline import report_run, score_run
from .providers.gemini_judge import GeminiJudgeProvider


def gemini_judge_status(
    db_path: str | Path, run_id: str, *, model: str, judge_prompt_version: str,
    rubric_version: str,
) -> tuple[list[Any], str | None, int]:
    with connect(db_path) as conn:
        expected = conn.execute("SELECT COUNT(*) FROM run_cases WHERE run_id = ?", (run_id,)).fetchone()[0]
        responses = conn.execute(
            """SELECT r.id, r.case_id, r.provider, r.payload_json response_json,
                      c.payload_json case_json
               FROM model_responses r JOIN cases c
                 ON c.id = r.case_id AND c.version = r.case_version
               WHERE r.run_id = ? ORDER BY r.case_id""", (run_id,),
        ).fetchall()
        if not expected or len(responses) != expected or any(row["provider"] != "xai-grok" for row in responses):
            raise ValueError("Run must have one imported Grok response per snapshotted case")
        if conn.execute("SELECT COUNT(*) FROM scores WHERE run_id = ?", (run_id,)).fetchone()[0]:
            raise ValueError("Run is already scored")
        judgments = conn.execute(
            """SELECT response_id, judge_provider, judge_model_id, judge_model_version,
                      judge_prompt_version, rubric_version
               FROM judge_outputs WHERE run_id = ?""", (run_id,),
        ).fetchall()
    versions = {row["judge_model_version"] for row in judgments}
    if len(versions) > 1 or any(
        row["judge_provider"] != "google-gemini" or row["judge_model_id"] != model
        or row["judge_prompt_version"] != judge_prompt_version
        or row["rubric_version"] != rubric_version for row in judgments
    ):
        raise ValueError("Run contains a different or mixed judge configuration")
    judged_ids = [row["response_id"] for row in judgments]
    response_ids = {row["id"] for row in responses}
    if len(judged_ids) != len(set(judged_ids)) or not set(judged_ids) <= response_ids:
        raise ValueError("Run contains duplicate or unrelated Gemini judgments")
    pending = [row for row in responses if row["id"] not in set(judged_ids)]
    return pending, next(iter(versions), None), expected


def judge_imported_grok(
    db_path: str | Path, run_id: str, *, model: str, api_key: str,
    instruction: str, rubric: dict[str, Any], judge_prompt_version: str,
    scoring: dict[str, Any], limit: int = 1, timeout: float = 120,
    retries: int = 2, transport: Callable[..., Any] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    pending, expected_version, total = gemini_judge_status(
        db_path, run_id, model=model, judge_prompt_version=judge_prompt_version,
        rubric_version=rubric["version"],
    )
    if type(limit) is not int or limit < 1:
        raise ValueError("--limit must be a positive integer")
    if timeout <= 0 or retries < 0:
        raise ValueError("Timeout must be positive and retries nonnegative")
    if not pending:
        raise ValueError("No unjudged responses remain")
    options = {
        "model": model, "api_key": api_key, "instruction": instruction,
        "timeout": timeout, "retries": retries, "expected_version": expected_version,
    }
    if transport is not None:
        options["transport"] = transport
    judge = GeminiJudgeProvider(**options)
    selected = pending[:limit]
    for index, row in enumerate(selected, 1):
        case = json.loads(row["case_json"])
        response = json.loads(row["response_json"])
        output = judge.evaluate(case, response, rubric)
        with connect(db_path) as conn:
            conn.execute(
                """INSERT INTO judge_outputs
                (id, run_id, response_id, judge_provider, judge_model_id,
                 judge_model_version, judge_prompt_version, rubric_version,
                 payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_id("judge"), run_id, row["id"], judge.provider_name,
                 judge.model_id, judge.model_version, judge_prompt_version,
                 rubric["version"], dump(output), now_iso()),
            )
        if progress:
            progress(index, len(selected), row["case_id"])
    remaining, _, _ = gemini_judge_status(
        db_path, run_id, model=model, judge_prompt_version=judge_prompt_version,
        rubric_version=rubric["version"],
    )
    result = {
        "run_id": run_id, "judged_this_call": len(selected),
        "total_cases": total, "remaining_unjudged": len(remaining),
        "judge_model_requested": model, "judge_model_returned": judge.model_version,
        "report_status": "experimental_unvalidated",
        "warning": "Single uncalibrated AI judge on draft cases; not clinical validation.",
    }
    if not remaining:
        score_run(db_path, run_id, rubric, scoring)
        result["report"] = report_run(db_path, run_id)
    return result
