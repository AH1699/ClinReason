from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .config import load_jsonl
from .db import connect, dump, init_db, new_id, now_iso
from .providers.base import CandidateProvider, JudgeProvider
from .reviews import case_content_hash
from .scoring import aggregate_judgments


def ingest_cases(db_path: str | Path, cases_path: str | Path) -> int:
    cases = load_jsonl(cases_path)
    with connect(db_path) as conn:
        conn.execute("DELETE FROM active_cases")
        for case in cases:
            encoded = dump(case)
            content_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            existing = conn.execute(
                "SELECT payload_json FROM cases WHERE id = ? AND version = ?",
                (case["id"], case["version"]),
            ).fetchone()
            if existing and case_content_hash(json.loads(existing["payload_json"])) != case_content_hash(case):
                raise ValueError(
                    f"Reviewable content of {case['id']}@{case['version']} changed without a new version"
                )
            conn.execute(
                """INSERT INTO cases
                (id, version, category, payload_json, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id, version) DO UPDATE SET
                  category = excluded.category,
                  payload_json = excluded.payload_json,
                  content_hash = excluded.content_hash""",
                (case["id"], case["version"], case["category"], encoded, content_hash, now_iso()),
            )
            conn.execute(
                "INSERT INTO active_cases (case_id, case_version) VALUES (?, ?)",
                (case["id"], case["version"]),
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
        active_count = conn.execute("SELECT COUNT(*) FROM active_cases").fetchone()[0]
        if not active_count:
            raise ValueError("Cannot create a run without an active dataset")
        conn.execute(
            """INSERT INTO run_cases (run_id, case_id, case_version, content_hash)
               SELECT ?, a.case_id, a.case_version, c.content_hash
               FROM active_cases a JOIN cases c
               ON c.id = a.case_id AND c.version = a.case_version""",
            (run_id,),
        )
    return run_id


def generate_responses(
    db_path: str | Path,
    run_id: str,
    provider: CandidateProvider,
    prompt_template_version: str,
) -> int:
    with connect(db_path) as conn:
        cases = conn.execute(
            """SELECT c.payload_json FROM run_cases rc JOIN cases c
               ON c.id = rc.case_id AND c.version = rc.case_version
               WHERE rc.run_id = ? ORDER BY c.id""",
            (run_id,),
        ).fetchall()
        for row in cases:
            case = json.loads(row["payload_json"])
            candidate_input = {
                "id": case["id"],
                "version": case["version"],
                "language": case.get("language"),
                "prompt": case["prompt"],
            }
            generated = provider.generate(candidate_input)
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
        expected_case_count = conn.execute(
            "SELECT COUNT(*) FROM run_cases WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        rows = conn.execute(
            """SELECT s.*, r.case_id, r.provider, r.model_id, r.model_version,
                      c.category, c.payload_json AS case_json
               FROM scores s JOIN model_responses r ON s.response_id = r.id
               JOIN cases c ON r.case_id = c.id AND r.case_version = c.version
               WHERE s.run_id = ? ORDER BY r.case_id""",
            (run_id,),
        ).fetchall()
    if not rows:
        return {
            "run_id": run_id,
            "count": 0,
            "expected_case_count": expected_case_count,
            "coverage": 0.0,
            "report_status": "experimental_unvalidated",
        }

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "count": len(items),
            "mean_gated_score": round(sum(item["gated_score"] for item in items) / len(items), 2),
            "pass_rate": round(sum(item["pass"] for item in items) / len(items), 3),
            "human_review_required": sum(item["review_status"] == "required" for item in items),
            "confirmed_critical_error_count": sum(len(item["confirmed_critical_errors"]) for item in items),
        }

    cases = []
    for row in rows:
        case = json.loads(row["case_json"])
        score = json.loads(row["payload_json"])
        cases.append(
            {
                "case_id": row["case_id"],
                "case_family_id": case.get("metadata", {}).get("case_family_id"),
                "category": row["category"],
                "language": case.get("language"),
                "provider": row["provider"],
                "model_id": row["model_id"],
                "model_version": row["model_version"],
                "model": f"{row['model_id']}@{row['model_version']}",
                "raw_score": row["raw_score"],
                "gated_score": float(row["gated_score"]),
                "pass": bool(row["pass"]),
                "confidence": row["confidence"],
                "review_status": row["review_status"],
                "dimension_scores": score["dimension_scores"],
                "confirmed_critical_errors": score["confirmed_critical_errors"],
                "review_reasons": score["review_reasons"],
            }
        )

    def grouped(key: str, items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            buckets[str(item[key])].append(item)
        return {name: summarize(bucket) for name, bucket in sorted(buckets.items())}

    model_buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in cases:
        model_buckets[(item["provider"], item["model_id"], item["model_version"])].append(item)
    by_model = []
    for (provider, model_id, model_version), items in sorted(model_buckets.items()):
        category_summary = grouped("category", items)
        family_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            # Legacy example cases have no bilingual family; treat each as a singleton.
            family_buckets[item["case_family_id"] or item["case_id"]].append(item)
        family_rows = []
        for family_id, members in sorted(family_buckets.items()):
            languages = {member["language"]: member["gated_score"] for member in members}
            family_rows.append({
                "family_id": family_id,
                "category": members[0]["category"],
                "prompt_count": len(members),
                "mean_gated_score": round(sum(member["gated_score"] for member in members) / len(members), 2),
                "by_language": languages,
                "complete_bilingual_pair": len(members) == 2 and set(languages) == {"en", "zh-Hans"},
                "language_gap_en_minus_zh": round(languages["en"] - languages["zh-Hans"], 2)
                if len(members) == 2 and set(languages) == {"en", "zh-Hans"} else None,
            })
        family_category: dict[str, list[float]] = defaultdict(list)
        for family in family_rows:
            family_category[family["category"]].append(family["mean_gated_score"])
        paired = [family for family in family_rows if family["complete_bilingual_pair"]]
        by_model.append(
            {
                "provider": provider,
                "model_id": model_id,
                "model_version": model_version,
                **summarize(items),
                "prompt_coverage": round(len({item["case_id"] for item in items}) / expected_case_count, 3)
                if expected_case_count else 0.0,
                "macro_category_mean": round(
                    sum(group["mean_gated_score"] for group in category_summary.values())
                    / len(category_summary), 2
                ),
                "by_category": category_summary,
                "by_language": grouped("language", items),
                "family_count": len(family_rows),
                "complete_bilingual_pair_count": len(paired),
                "mean_family_score": round(sum(family["mean_gated_score"] for family in family_rows) / len(family_rows), 2),
                "macro_category_family_mean": round(
                    sum(sum(values) / len(values) for values in family_category.values())
                    / len(family_category), 2
                ),
                "mean_absolute_paired_language_gap": round(
                    sum(abs(family["language_gap_en_minus_zh"]) for family in paired) / len(paired), 2
                ) if paired else None,
                "by_family": family_rows,
            }
        )
    overview = summarize(cases)
    return {
        "run_id": run_id,
        "report_status": "experimental_unvalidated",
        "caution": "Draft cases or uncalibrated judges; scores are not clinical validation or a public model ranking.",
        "analysis_unit": "clinical_case_family; bilingual prompts are paired variants, not independent scenarios",
        "uncertainty_note": "Descriptive scores only; no confidence interval or comparative ranking is justified for this selected, unreviewed set.",
        "expected_case_count": expected_case_count,
        "coverage": round(len({item["case_id"] for item in cases}) / expected_case_count, 3)
        if expected_case_count else 0.0,
        **overview,
        "by_model": by_model,
        "cases": cases,
    }


def bootstrap(db_path: str | Path, cases_path: str | Path) -> int:
    init_db(db_path)
    return ingest_cases(db_path, cases_path)
