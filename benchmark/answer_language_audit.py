"""Conservative offline script-mismatch flags for saved bilingual answers.

This detects obvious wrong-script turns only. It is not language proficiency,
translation equivalence, clinical correctness, or a scoring adjustment.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .config import load_json, load_jsonl
from .multiturn import merge_multiturn_datasets, ordered_variants, variant_hash, variant_id
from .provenance import sha256_text


HAN = re.compile(r"[\u3400-\u9fff]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def audit_saved_answer_languages(root: Path, answer_files: list[Path], *,
                                 expected_instruction: str | None = None) -> dict[str, Any]:
    """Bind answers to exact configured cases, then flag unmistakable script mismatch."""
    if not answer_files:
        raise ValueError("At least one saved answer file is required")
    config = load_json(root / "config/benchmark.json")
    dataset = merge_multiturn_datasets([
        load_json(root / path) for path in config["multiturn_cases_paths"]
    ])
    expected = {
        variant_id(family, language): (variant_hash(family, language), language)
        for family, language in ordered_variants(dataset)
    }
    seen: set[tuple[str, str]] = set()
    flags: list[dict[str, Any]] = []
    checked_turns = 0
    for path in answer_files:
        rows = load_jsonl(path)
        if len(rows) != 1:
            raise ValueError(f"Expected exactly one answer row: {path}")
        row = rows[0]
        case_id = row.get("case_id")
        model_id = row.get("model_id")
        if (case_id not in expected or not isinstance(model_id, str) or not model_id
            or (model_id, case_id) in seen or row.get("case_content_hash") != expected[case_id][0]):
            raise ValueError(f"Duplicate, unknown or wrong-revision saved answer: {path}")
        if expected_instruction is not None:
            manifest_path = path.with_suffix(".manifest.json")
            manifest = load_json(manifest_path)
            revisions = manifest.get("case_revisions") if isinstance(manifest, dict) else None
            if (not isinstance(revisions, list)
                or manifest.get("candidate_instruction_sha256") != sha256_text(expected_instruction)
                or not any(isinstance(item, dict) and item.get("case_id") == case_id
                           and item.get("case_content_hash") == row["case_content_hash"]
                           for item in revisions)):
                raise ValueError(f"Answer manifest does not match declared candidate protocol: {path}")
        seen.add((model_id, case_id))
        language = expected[case_id][1]
        turns = row.get("turn_outputs")
        if (not isinstance(turns, list) or len(turns) != 2
            or [turn.get("stage_id") for turn in turns] != ["initial", "update"]):
            raise ValueError(f"Expected initial and update answer turns: {path}")
        for turn in turns:
            response = turn.get("text")
            if not isinstance(response, str) or not response.strip():
                raise ValueError(f"Empty saved answer turn: {path}")
            han_count = len(HAN.findall(response))
            latin_word_count = len(LATIN_WORD.findall(response))
            checked_turns += 1
            reason = None
            if language == "zh-Hans" and han_count < 3 and latin_word_count >= 20:
                reason = "zh_expected_english_script_dominant"
            elif language == "en" and latin_word_count < 5 and han_count >= 20:
                reason = "en_expected_han_script_dominant"
            if reason:
                flags.append({
                    "case_id": case_id, "model_id": model_id,
                    "stage_id": turn["stage_id"], "reason": reason,
                    "han_character_count": han_count,
                    "latin_word_count": latin_word_count,
                })
    return {
        "status": "offline_obvious_script_mismatch_flags_not_language_or_clinical_scoring",
        "answer_count": len(answer_files),
        "checked_turn_count": checked_turns,
        "verified_candidate_instruction_sha256": (
            sha256_text(expected_instruction) if expected_instruction is not None else None
        ),
        "flags": sorted(flags, key=lambda item: (item["model_id"], item["case_id"], item["stage_id"])),
        "limits": [
            "An unflagged response is not evidence of correct language or bilingual equivalence.",
            "Mixed-language quality and medical terminology require human review.",
            "Historical scores are unchanged; no provider API is called.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flag obvious wrong-script saved answer turns offline")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--answer-file", type=Path, action="append", required=True)
    parser.add_argument("--candidate-prompt", type=Path,
                        help="Verify each answer manifest used this exact versioned candidate instruction")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    instruction = args.candidate_prompt.read_text(encoding="utf-8").strip() if args.candidate_prompt else None
    report = audit_saved_answer_languages(args.root, args.answer_file, expected_instruction=instruction)
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError("Refusing to overwrite an existing language-audit output")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(json.dumps({"status": report["status"], "output": str(args.output)}))
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
