from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import load_jsonl
from .db import connect, dump, init_db, new_id, now_iso
from .providers.base import CandidateProvider, JudgeProvider
from .scoring import aggregate_judgments


def ingest_cases(db_path: str | Path, cases_path: str | Path) -> int:
    cases = load_jsonl(cases_path)
    with connect(db_path) as conn:
        for case in cases:
            encoded = dump(case)
            content_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            conn.execute(
                """INSERT OR REPLACE INTO cases
                (id, version, category, payload_json, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (case["id"], case["version"], case["category"], encoded, content_hash, now_iso()),
            )
    return len(cases)


def create_run(db_path: str | Path, config: dict[str, Any]) -> str:
    run_id = new_id("run")
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO benchmark_runs
            (id, benchmark_id, benchmark_version, rubric_version, config_json, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                config["benchmark_id"],
                config["benchmark_version"],
                config["rubric_version"],
                dump(config),
                now_iso(),
                "running",
            ),
        )
    return run_id


def generate_responses(
    db_path: str | Path,
    run_id: str,
    provider: CandidateProvider,
    prompt_template_version: str,
) -> int:
    with connect(db_path) as conn:
        cases = conn.execute("SELECT payload_json FROM cases ORDER BY id").fetchall()
        for row in cases:
            case = json.loads(row["payload_json"])
            generated = provider.generate(case)
            payload = {
                "text": generated["text"],
                "finish_reason": generated.get("finish_reason"),
                "latency_ms": generated.get("latency_ms"),
                "token_usage": generated.get("token_usage"),
            }
            conn.execute(
                """INSERT INTO model_responses
                (id, run_id, case_id, case_version, provider, model_id, model_version,
                 prompt_template_version, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_id("resp"), run_id, case["id"], case["version"],
                    provider.provider_name, provider.model_id, provider.model_version,
                    prompt_template_version, dump(payload), now_iso(),
                ),
            )
    return len(cases)


def judge_responses(
    db_path: str | Path,
    run_id: str,
    judges: list[JudgeProvider],
    rubric: dict[str, Any],
    judge_prompt_version: str,
) -> int:
    count = 0
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT r.id response_id, r.payload_json response_json, c.payload_json case_json
               FROM model_responses r JOIN cases c
               ON r.case_id = c.id AND r.case_version = c.version
               WHERE r.run_id = ? ORDER BY r.id""",
            (run_id,),
        ).fetchall()
        for row in rows:
            case = json.loads(row["case_json"])
            response = json.loads(row["response_json"])
            for judge in judges:
                output = judge.evaluate(case, response, rubric)
                conn.execute(
                    """INSERT INTO judge_outputs
                    (id, run_id, response_id, judge_provider, judge_model_id,
                     judge_model_version, judge_prompt_version, rubric_version,
                     payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        new_id("judge"), run_id, row["response_id"], judge.provider_name,
                        judge.model_id, judge.model_version, judge_prompt_version,
                        rubric["version"], dump(output), now_iso(),
                    ),
                )
                count += 1
    return count


def score_run(
    db_path: str | Path,
    run_id: str,
    rubric: dict[str, Any],
    scoring_config: dict[str, Any],
) -> int:
    count = 0
    with connect(db_path) as conn:
        response_ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM model_responses WHERE run_id = ?", (run_id,)
            )
        ]
        for response_id in response_ids:
            judgments = [
                json.loads(row["payload_json"])
                for row in conn.execute(
                    "SELECT payload_json FROM judge_outputs WHERE response_id = ?",
                    (response_id,),
                )
            ]
            aggregate = aggregate_judgments(judgments, rubric, scoring_config)
            conn.execute(
                """INSERT OR REPLACE INTO scores
                (id, run_id, response_id, raw_score, gated_score, pass, confidence,
                 review_status, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_id("score"), run_id, response_id, aggregate["raw_score"],
                    aggregate["gated_score"], int(aggregate["pass"]),
                    aggregate["confidence"], aggregate["review_status"],
                    dump(aggregate), now_iso(),
                ),
            )
            count += 1
        conn.execute("UPDATE benchmark_runs SET status = 'complete' WHERE id = ?", (run_id,))
    return count


def report_run(db_path: str | Path, run_id: str) -> dict[str, Any]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT s.*, r.case_id, r.model_id, r.model_version
               FROM scores s JOIN model_responses r ON s.response_id = r.id
               WHERE s.run_id = ? ORDER BY r.case_id""",
            (run_id,),
        ).fetchall()
    if not rows:
        return {"run_id": run_id, "count": 0}
    scores = [float(row["gated_score"]) for row in rows]
    return {
        "run_id": run_id,
        "count": len(rows),
        "mean_gated_score": round(sum(scores) / len(scores), 2),
        "pass_rate": round(sum(int(row["pass"]) for row in rows) / len(rows), 3),
        "human_review_required": sum(row["review_status"] == "required" for row in rows),
        "cases": [
            {
                "case_id": row["case_id"],
                "model": f"{row['model_id']}@{row['model_version']}",
                "raw_score": row["raw_score"],
                "gated_score": row["gated_score"],
                "pass": bool(row["pass"]),
                "confidence": row["confidence"],
                "review_status": row["review_status"],
            }
            for row in rows
        ],
    }


def bootstrap(db_path: str | Path, cases_path: str | Path) -> int:
    init_db(db_path)
    return ingest_cases(db_path, cases_path)
