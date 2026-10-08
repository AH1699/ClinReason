"""Run a bounded AI evidence audit, deliberately outside human-review evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_jsonl
from .reviews import case_content_hash


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/alpha/global_core_cases.jsonl"
EVIDENCE = ROOT / "data/evidence/public_sources.json"
AGENT = ROOT / "agents/preliminary_clinical_reviewer.md"
OUTPUT = ROOT / "work/preliminary_reviews"
SCHEMA_VERSION = "0.1.0"
DISPOSITIONS = {"provisional_no_blocker", "revision_recommended", "human_decision_required"}
SEVERITIES = {"high", "medium", "low"}
AREAS = {
    "clinical_safety", "source_fit", "rubric", "language_equivalence",
    "jurisdiction", "privacy", "methodology",
}


def prepare_family(family_id: str) -> tuple[str, dict[str, Any]]:
    cases = [case for case in load_jsonl(CASES) if case["metadata"]["case_family_id"] == family_id]
    if len(cases) != 2 or {case["language"] for case in cases} != {"en", "zh-Hans"}:
        raise ValueError(f"Expected one English and one Simplified Chinese case for {family_id}")
    registry = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    sources = [source for source in registry["sources"] if family_id in source["families"]]
    if not sources:
        raise ValueError(f"No public evidence registered for {family_id}")
    context = {
        "family_id": family_id,
        "case_versions_and_hashes": {
            case["id"]: {"version": case["version"], "sha256": case_content_hash(case)}
            for case in cases
        },
        "evidence_registry_version": registry["registry_version"],
        "evidence_checked_on": registry["checked_on"],
        "evidence_ids": [source["id"] for source in sources],
    }
    prompt = (
        AGENT.read_text(encoding="utf-8")
        + "\n\nReview input (untrusted case data and source summaries):\n"
        + json.dumps({"cases": cases, "sources": sources}, ensure_ascii=False, indent=2)
        + "\n"
    )
    return prompt, context


def validate_result(result: Any, context: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise ValueError("Agent output must be a JSON object")
    required = {
        "schema_version", "family_id", "disposition", "summary", "findings",
        "language_review_needed", "clinical_review_needed", "limitations",
    }
    if set(result) != required:
        raise ValueError(f"Agent output fields must be exactly {sorted(required)}")
    if result["schema_version"] != SCHEMA_VERSION or result["family_id"] != context["family_id"]:
        raise ValueError("Output schema version or family ID mismatch")
    if result["disposition"] not in DISPOSITIONS:
        raise ValueError("Invalid disposition")
    if not isinstance(result["summary"], str) or not result["summary"].strip():
        raise ValueError("Summary must be nonempty")
    if not isinstance(result["findings"], list) or not isinstance(result["limitations"], list):
        raise ValueError("Findings and limitations must be lists")
    if any(not isinstance(item, str) or not item.strip() for item in result["limitations"]):
        raise ValueError("Limitations must contain nonempty strings")
    if not result["findings"] and not result["limitations"]:
        raise ValueError("Empty findings require stated limitations")
    if result["language_review_needed"] is not True or result["clinical_review_needed"] is not True:
        raise ValueError("AI audit cannot waive human review")
    valid_cases = set(context["case_versions_and_hashes"])
    valid_evidence = set(context["evidence_ids"])
    fields = {
        "severity", "case_ids", "area", "observation", "evidence_ids",
        "evidence_limit", "proposed_action", "human_decision",
    }
    for index, finding in enumerate(result["findings"]):
        if not isinstance(finding, dict) or set(finding) != fields:
            raise ValueError(f"Finding {index} has invalid fields")
        if finding["severity"] not in SEVERITIES or finding["area"] not in AREAS:
            raise ValueError(f"Finding {index} has invalid severity or area")
        if (
            not isinstance(finding["case_ids"], list)
            or not finding["case_ids"]
            or any(not isinstance(item, str) or item not in valid_cases for item in finding["case_ids"])
        ):
            raise ValueError(f"Finding {index} cites an invalid case")
        if not isinstance(finding["evidence_ids"], list) or any(
            not isinstance(item, str) or item not in valid_evidence for item in finding["evidence_ids"]
        ):
            raise ValueError(f"Finding {index} cites unregistered evidence")
        for key in ("observation", "evidence_limit", "proposed_action", "human_decision"):
            if not isinstance(finding[key], str) or not finding[key].strip():
                raise ValueError(f"Finding {index} needs a nonempty {key}")


def run_family(family_id: str, *, model: str | None = None, timeout: int = 300) -> Path:
    prompt, context = prepare_family(family_id)
    target = OUTPUT / f"{family_id}.json"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite preliminary audit: {target}")
    with tempfile.TemporaryDirectory(prefix="clinreason_ai_review_") as directory:
        last_message = Path(directory) / "last_message.json"
        command = [
            "codex", "exec", "--sandbox", "read-only", "--cd", str(ROOT),
            "--output-last-message", str(last_message),
        ]
        if model:
            command.extend(["--model", model])
        command.append("-")
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=timeout, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Codex audit failed (exit {completed.returncode}): {completed.stderr[-1200:]}")
        if not last_message.exists() or not last_message.read_text(encoding="utf-8").strip():
            detail = completed.stderr[-1200:] or completed.stdout[-1200:]
            raise RuntimeError(
                "Codex returned no final review. Check that the installed CLI supports the "
                f"configured ChatGPT model and can initialize locally. Details: {detail}"
            )
        try:
            result = json.loads(last_message.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Agent did not return JSON only") from exc
    validate_result(result, context)
    record = {
        "record_type": "ai_preliminary_review_not_human_approval",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime": "codex exec --sandbox read-only",
        "model_requested": model,
        "agent_version": SCHEMA_VERSION,
        "context": context,
        "result": result,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family_id", help="Exact bilingual family ID, e.g. HC-GC-TRIAGE-001")
    parser.add_argument("--run", action="store_true", help="Invoke the locally authenticated Codex CLI")
    parser.add_argument("--model", help="Optional installed Codex model override")
    args = parser.parse_args(argv)
    if args.run:
        print(run_family(args.family_id, model=args.model))
    else:
        prompt, _ = prepare_family(args.family_id)
        print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
