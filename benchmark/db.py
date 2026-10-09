from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


DDL = """
CREATE TABLE IF NOT EXISTS benchmark_runs (
  id TEXT PRIMARY KEY,
  benchmark_id TEXT NOT NULL,
  benchmark_version TEXT NOT NULL,
  rubric_version TEXT NOT NULL,
  config_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
  id TEXT NOT NULL,
  version TEXT NOT NULL,
  category TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (id, version)
);
CREATE TABLE IF NOT EXISTS active_cases (
  case_id TEXT NOT NULL,
  case_version TEXT NOT NULL,
  PRIMARY KEY (case_id, case_version),
  FOREIGN KEY(case_id, case_version) REFERENCES cases(id, version)
);
CREATE TABLE IF NOT EXISTS run_cases (
  run_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  case_version TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  PRIMARY KEY (run_id, case_id, case_version),
  FOREIGN KEY(run_id) REFERENCES benchmark_runs(id),
  FOREIGN KEY(case_id, case_version) REFERENCES cases(id, version)
);
CREATE TABLE IF NOT EXISTS model_responses (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  case_version TEXT NOT NULL,
  provider TEXT NOT NULL,
  model_id TEXT NOT NULL,
  model_version TEXT NOT NULL,
  prompt_template_version TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES benchmark_runs(id)
);
CREATE TABLE IF NOT EXISTS judge_outputs (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  response_id TEXT NOT NULL,
  judge_provider TEXT NOT NULL,
  judge_model_id TEXT NOT NULL,
  judge_model_version TEXT NOT NULL,
  judge_prompt_version TEXT NOT NULL,
  rubric_version TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES benchmark_runs(id),
  FOREIGN KEY(response_id) REFERENCES model_responses(id)
);
CREATE TABLE IF NOT EXISTS scores (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  response_id TEXT NOT NULL UNIQUE,
  raw_score REAL NOT NULL,
  gated_score REAL NOT NULL,
  pass INTEGER NOT NULL,
  confidence REAL NOT NULL,
  review_status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES benchmark_runs(id),
  FOREIGN KEY(response_id) REFERENCES model_responses(id)
);
CREATE TABLE IF NOT EXISTS human_reviews (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  response_id TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  reviewer_role TEXT NOT NULL,
  rubric_version TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES benchmark_runs(id),
  FOREIGN KEY(response_id) REFERENCES model_responses(id)
);
CREATE TABLE IF NOT EXISTS pairwise_outputs (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  response_a_id TEXT NOT NULL,
  response_b_id TEXT NOT NULL,
  judge_model_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def init_db(path: str | Path) -> None:
    with connect(path) as conn:
        conn.executescript(DDL)


def insert_json(conn: sqlite3.Connection, sql: str, values: tuple[Any, ...]) -> None:
    conn.execute(sql, values)


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
