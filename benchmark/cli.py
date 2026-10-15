from __future__ import annotations

import argparse
import json
from pathlib import Path

from .candidate_exchange import export_prompts, import_answers
from .config import load_json, load_jsonl, resolve_path
from .coverage import audit_coverage
from .judge_diagnostics import assess_contrasts
from .dataset_status import summarize_dataset
from .difficulty_audit import (
    audit_multiturn_difficulty, compare_multiturn_candidate_reports,
    compare_multiturn_judge_passes,
)
from .db import connect
from .live_judging import gemini_judge_status, judge_imported_grok
from .local_settings import read_setting
from .multiturn import (
    judge_packets_from_answers, merge_multiturn_datasets, ordered_variants,
    validate_multiturn_dataset, variant_id, write_batch,
)
from .multiturn_judging import GeminiMultiturnJudge, score_judgment
from .model_matrix import compare_matrix_reports, prepare_matrix, run_matrix
from .multiturn_diagnostics import assess_contrast_pairs
from .multiturn_bilingual_probes import (
    compare_bilingual_probe_reports, run_bilingual_probes, validate_probe_set,
)
from .provenance import sha256_json, sha256_text
from .pipeline import (
    bootstrap,
    create_run,
    generate_responses,
    judge_responses,
    report_run,
    score_run,
)
from .provenance import candidate_provenance
from .providers.mock import MockCandidateProvider, MockJudgeProvider
from .providers.gemini import GeminiRunError, candidate_rows, local_api_key, run_gemini
from .providers.grok import candidate_rows as grok_candidate_rows, run_grok
from .providers.grok_conversation import GrokConversationProvider
from .providers.grok_multiturn_judge import GrokMultiturnJudge
from .providers.gemini_conversation import GeminiConversationProvider
from .providers.gemini_judge import GeminiJudgeProvider
from .professional import (
    combine_professional_datasets, export_professional_prompts, professional_candidate_rows,
    validate_case_adaptation_registry, validate_professional_dataset, validate_professional_rubric,
)
from .providers.http_json import ProviderRequestError
from .review_packets import export_review_packets
from .reviews import (
    REVIEW_TYPES,
    ROLES,
    assess_reviews,
    build_review_template,
    release_review_issues,
)
from .validation import validate_dataset


def _context(config_path: str) -> tuple[dict, Path, Path, dict]:
    config = load_json(config_path)
    db_path = resolve_path(config_path, config["database_path"])
    cases_path = resolve_path(config_path, config["cases_path"])
    rubric_path = resolve_path(config_path, config["rubric_path"])
    return config, db_path, cases_path, load_json(rubric_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sectorbench")
    parser.add_argument("--config", default="config/benchmark.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Initialize SQLite and ingest configured cases")
    sub.add_parser("run-demo", help="Run the complete offline mock pipeline")
    prompt_export = sub.add_parser(
        "export-prompts", help="Export only candidate-visible prompts for an external model"
    )
    prompt_export.add_argument("--output", default="work/candidate_prompts.jsonl")
    gemini = sub.add_parser(
        "generate-gemini", help="Generate Gemini candidate answers (dry-run unless --live)"
    )
    gemini.add_argument("--model", required=True, help="Exact Gemini model ID")
    gemini.add_argument("--output", default="work/candidate_gemini_answers.jsonl")
    gemini.add_argument("--env-file", default=".env.local")
    gemini.add_argument("--limit", type=int, default=1, help="Maximum cases; default 1")
    gemini.add_argument("--timeout", type=float, default=60, help="Seconds per API request")
    gemini.add_argument("--retries", type=int, default=2, help="Retries for HTTP 429/5xx only")
    gemini.add_argument("--live", action="store_true", help="Authorize real Gemini API calls")
    grok = sub.add_parser(
        "generate-grok", help="Generate Grok candidate answers (dry-run unless --live)"
    )
    grok.add_argument("--model", help="Override GROK_MODEL from local settings")
    grok.add_argument("--output", default="work/candidate_grok_answers.jsonl")
    grok.add_argument("--env-file", default=".env.local")
    grok.add_argument("--limit", type=int, default=1)
    grok.add_argument("--timeout", type=float, default=120)
    grok.add_argument("--retries", type=int, default=2)
    grok.add_argument("--live", action="store_true")
    answer_import = sub.add_parser(
        "import-responses", help="Import one external-model answer for each exact case revision"
    )
    answer_import.add_argument("--input", required=True, help="Answer JSONL file")
    answer_import.add_argument("--provider", required=True)
    answer_import.add_argument("--model-id", required=True)
    answer_import.add_argument("--model-version", required=True)
    imported_demo = sub.add_parser(
        "score-imported-demo", help="Score imported answers with mock judges (infrastructure only)"
    )
    imported_demo.add_argument("run_id")
    gemini_judge = sub.add_parser(
        "judge-imported-gemini", help="Judge imported Grok answers with Gemini (dry-run unless --live)"
    )
    gemini_judge.add_argument("run_id")
    gemini_judge.add_argument("--model", help="Override GEMINI_JUDGE_MODEL from local settings")
    gemini_judge.add_argument("--env-file", default=".env.local")
    gemini_judge.add_argument("--limit", type=int, default=1)
    gemini_judge.add_argument("--timeout", type=float, default=120)
    gemini_judge.add_argument("--retries", type=int, default=2)
    gemini_judge.add_argument("--live", action="store_true")
    report = sub.add_parser("report", help="Print a JSON report for a run")
    report.add_argument("run_id")
    sub.add_parser("coverage-audit", help="Audit family-level coverage and development/holdout status")
    sub.add_parser("validate-multiturn", help="Validate the separate two-turn draft pilot")
    sub.add_parser("validate-professional", help="Validate the separate clinician-facing development pilot")
    pro_export = sub.add_parser("export-professional-prompts", help="Export only clinician-facing candidate-visible prompts")
    pro_export.add_argument("--output", default="work/professional_candidate_prompts.jsonl")
    mt_grok = sub.add_parser(
        "generate-grok-multiturn", help="Run scripted two-turn Grok pilot (dry-run unless --live)"
    )
    mt_grok.add_argument("--model", help="Override GROK_MODEL from local settings")
    mt_grok.add_argument("--env-file", default=".env.local")
    mt_grok.add_argument("--limit", type=int, default=1, help="Variants, two calls each")
    mt_grok.add_argument("--case-id", help="Run one exact bilingual variant, such as HC-MT-MEDSAFE-001-ZH-HANS")
    mt_grok.add_argument("--family-ids", help="Comma-separated exact family IDs; --limit must equal two variants per family")
    mt_grok.add_argument("--output", default="work/multiturn_grok_answers.jsonl")
    mt_grok.add_argument("--live", action="store_true")
    mt_gemini = sub.add_parser(
        "generate-gemini-multiturn", help="Run scripted two-turn Gemini candidate pilot (dry-run unless --live)"
    )
    mt_gemini.add_argument("--model", required=True, help="Exact Gemini candidate model ID")
    mt_gemini.add_argument("--env-file", default=".env.local")
    mt_gemini.add_argument("--limit", type=int, default=1, help="Variants, two calls each")
    mt_gemini.add_argument("--case-id")
    mt_gemini.add_argument("--family-ids", help="Comma-separated exact family IDs; --limit must equal two variants per family")
    mt_gemini.add_argument("--output", default="work/multiturn_gemini_candidate_answers.jsonl")
    mt_gemini.add_argument("--live", action="store_true")
    mt_packet = sub.add_parser(
        "export-multiturn-judge-packets", help="Create draft per-turn judge packets from a completed conversation file"
    )
    mt_packet.add_argument("--answers", required=True)
    mt_packet.add_argument("--output", default="work/multiturn_judge_packets.jsonl")
    mt_judge = sub.add_parser(
        "judge-multiturn-gemini", help="Provisional judge of scripted conversations (dry-run unless --live)"
    )
    mt_judge.add_argument("--answers", required=True)
    mt_judge.add_argument("--model", help="Override GEMINI_JUDGE_MODEL from local settings")
    mt_judge.add_argument("--env-file", default=".env.local")
    mt_judge.add_argument("--limit", type=int, default=1)
    mt_judge.add_argument("--output", default="work/multiturn_gemini_judgments.jsonl")
    mt_judge.add_argument("--live", action="store_true")
    mt_contrast = sub.add_parser(
        "judge-multiturn-contrast", help="Test Gemini on safe/partial/unsafe two-turn transcripts (dry-run unless --live)"
    )
    mt_contrast.add_argument("--model", help="Override GEMINI_JUDGE_MODEL from local settings")
    mt_contrast.add_argument("--env-file", default=".env.local")
    mt_contrast.add_argument("--limit", type=int, default=1, help="Number of pairs; two or three calls each")
    mt_contrast.add_argument("--family-id", help="Run one exact family, such as HC-MT-REASON-004")
    mt_contrast.add_argument("--output", default="work/multiturn_judge_contrasts.json")
    mt_contrast.add_argument("--live", action="store_true")
    mt_bilingual = sub.add_parser(
        "judge-multiturn-bilingual-probes",
        help="Blinded matched EN/ZH near-miss probes (dry-run unless --live)",
    )
    mt_bilingual.add_argument("--provider", choices=("gemini", "grok"), required=True)
    mt_bilingual.add_argument("--model", help="Override the selected judge model in local settings")
    mt_bilingual.add_argument("--family-id", help="Run both languages of one exact family")
    mt_bilingual.add_argument("--env-file", default=".env.local")
    mt_bilingual.add_argument("--timeout", type=float, default=240, help="Seconds per API request")
    mt_bilingual.add_argument("--output", default="work/multiturn_bilingual_probe_judgments.json")
    mt_bilingual.add_argument("--live", action="store_true")
    mt_bilingual_compare = sub.add_parser(
        "compare-multiturn-bilingual-probes",
        help="Verify and compare a complete first judge report with one or more second-provider parts",
    )
    mt_bilingual_compare.add_argument("--first", required=True)
    mt_bilingual_compare.add_argument("--second", action="append", required=True,
                                      help="Repeat for nonoverlapping second-provider family files")
    mt_bilingual_compare.add_argument("--output", default="work/multiturn_bilingual_probe_comparison.json")
    mt_audit = sub.add_parser(
        "difficulty-audit-multiturn", help="Describe a paired draft candidate/judge run without clinical claims"
    )
    mt_audit.add_argument("--answers", required=True, help="Candidate JSONL from generate-grok-multiturn")
    mt_audit.add_argument("--judgments", required=True, help="Judgment JSONL from judge-multiturn-gemini")
    mt_audit.add_argument("--output", help="Optional new JSON report path; never overwrites")
    mt_audit.add_argument("--cases-path", action="append", dest="cases_paths",
                          help="Repeat to select exact historical batch files instead of the current configured set")
    mt_repeat = sub.add_parser(
        "compare-multiturn-judges", help="Compare two provisional judge passes on the same answers"
    )
    mt_repeat.add_argument("--answers", required=True)
    mt_repeat.add_argument("--first", required=True, help="First judgment JSONL")
    mt_repeat.add_argument("--second", required=True, help="Second judgment JSONL")
    mt_repeat.add_argument("--output", help="Optional new JSON report path; never overwrites")
    mt_repeat.add_argument("--cases-path", action="append", dest="cases_paths",
                           help="Repeat to select exact historical batch files instead of the current configured set")
    mt_candidates = sub.add_parser(
        "compare-multiturn-candidates", help="Compare two independently audited fixed-sample candidate runs"
    )
    mt_candidates.add_argument("--first-report", required=True)
    mt_candidates.add_argument("--second-report", required=True)
    mt_candidates.add_argument("--output", help="Optional new JSON report path; never overwrites")
    matrix = sub.add_parser(
        "model-matrix", help="Plan or run bounded Gemini/Grok/MiniMax candidates with two AI judges"
    )
    matrix.add_argument("--roster", default="config/model_matrix.json")
    matrix.add_argument("--candidate-id", help="Run just one roster candidate")
    matrix.add_argument("--case-id", action="append",
                        help="Select exact variant ID; repeat for a fixed multi-case panel")
    matrix.add_argument("--env-file", default=".env.local")
    matrix.add_argument("--output-dir", default="work/model_matrix_pilot")
    matrix.add_argument("--max-api-calls", type=int, default=0,
                        help="Required explicit call-count ceiling for --live")
    matrix.add_argument("--timeout", type=float, default=240)
    matrix.add_argument("--live", action="store_true")
    matrix_compare = sub.add_parser(
        "compare-model-matrix", help="Align completed one-candidate matrix reports on exact cases and judges"
    )
    matrix_compare.add_argument("--report", action="append", required=True,
                                help="Repeat for each completed model-matrix report.json")
    matrix_compare.add_argument("--output", required=True)
    contrast = sub.add_parser(
        "judge-contrast-gemini", help="Check a Gemini judge on synthetic good/unsafe pairs (dry-run unless --live)"
    )
    contrast.add_argument("--model", help="Override GEMINI_JUDGE_MODEL from local settings")
    contrast.add_argument("--env-file", default=".env.local")
    contrast.add_argument("--limit", type=int, default=1, help="Number of pairs; two API calls per pair")
    contrast.add_argument("--output", default="work/judge_contrast_gemini.json")
    contrast.add_argument("--live", action="store_true")
    validate = sub.add_parser(
        "validate-data", help="Validate and lint a benchmark case JSONL file"
    )
    validate.add_argument(
        "--cases",
        help="Case JSONL path; defaults to cases_path from the benchmark config",
    )
    validate.add_argument(
        "--release-ready",
        action="store_true",
        help="Enforce clinician-validation, provenance, and bilingual-pair requirements",
    )
    validate.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    validate.add_argument(
        "--reviews",
        help="Review JSON/JSONL file or directory for release-ready evidence",
    )
    status = sub.add_parser(
        "dataset-status", help="Summarize authoring and review progress"
    )
    status.add_argument(
        "--cases",
        help="Case JSONL path; defaults to cases_path from the benchmark config",
    )
    status.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    validate_reviews = sub.add_parser(
        "validate-reviews", help="Validate append-only case review records"
    )
    validate_reviews.add_argument(
        "--reviews",
        help="Review JSON/JSONL file or directory; defaults to reviews_path",
    )
    validate_reviews.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    review_status = sub.add_parser(
        "review-status", help="Summarize independent case-review gates"
    )
    review_status.add_argument(
        "--reviews",
        help="Review JSON/JSONL file or directory; defaults to reviews_path",
    )
    review_status.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    review_template = sub.add_parser(
        "review-template", help="Create a review record bound to an exact case revision"
    )
    review_template.add_argument("case_id")
    review_template.add_argument("--review-type", choices=sorted(REVIEW_TYPES), required=True)
    review_template.add_argument("--reviewer-id", required=True)
    review_template.add_argument("--role", choices=sorted(ROLES), required=True)
    review_template.add_argument("--qualification-scope", required=True)
    review_template.add_argument("--jurisdiction-scope", required=True)
    review_template.add_argument(
        "--output", help="Write JSON to this path instead of standard output"
    )
    packets = sub.add_parser(
        "export-review-packets", help="Export bilingual Alpha packets and an assignment manifest"
    )
    packets.add_argument(
        "--output-dir", default="work/reviewer_packets", help="New or empty output directory"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config, db_path, cases_path, rubric = _context(args.config)
    if args.command == "compare-multiturn-candidates":
        try:
            report = compare_multiturn_candidate_reports(
                load_json(resolve_path(args.config, args.first_report)),
                load_json(resolve_path(args.config, args.second_report)),
            )
            if args.output:
                target = resolve_path(args.config, args.output)
                if target.exists():
                    raise FileExistsError(f"Refusing to overwrite candidate comparison: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8") as handle:
                    json.dump(report, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
        except (ValueError, KeyError, FileExistsError, OSError) as exc:
            print(f"Cannot compare candidate runs: {exc}")
            return 2
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command in {"validate-professional", "export-professional-prompts"}:
        try:
            professional_paths = config.get("professional_cases_paths") or [
                config.get("professional_cases_path", "data/professional/pilot_cases.json")
            ]
            professional = combine_professional_datasets([
                load_json(resolve_path(args.config, path)) for path in professional_paths
            ])
            status = validate_professional_dataset(professional)
            provenance = validate_case_adaptation_registry(load_json(resolve_path(
                args.config, config.get("professional_adaptations_path", "data/evidence/clinical_case_adaptations.json")
            )), professional)
            status.update(provenance)
            validate_professional_rubric(load_json(resolve_path(
                args.config, config.get("professional_rubric_path", "config/professional_rubric.json")
            )))
            if args.command == "validate-professional":
                print(json.dumps(status, ensure_ascii=False, indent=2))
                return 0
            instruction = resolve_path(
                args.config, config.get("professional_candidate_prompt_path", "config/professional_candidate_prompt.txt")
            ).read_text(encoding="utf-8").strip()
            rows = professional_candidate_rows(
                professional, instruction=instruction, prompt_template_version="professional-candidate-0.1.0"
            )
            target = resolve_path(args.config, args.output)
            count = export_professional_prompts(rows, target)
        except (ValueError, KeyError, FileExistsError, OSError) as exc:
            print(f"Cannot process professional pilot: {exc}")
            return 2
        print(json.dumps({"status": "draft_prompts_not_clinical_scores", "output": str(target),
                          "case_count": count, "track": status["track"]}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "init":
        count = bootstrap(db_path, cases_path)
        print(json.dumps({"database": str(db_path), "ingested_cases": count}, indent=2))
        return 0

    if args.command == "run-demo":
        bootstrap(db_path, cases_path)
        run_id = create_run(db_path, config)
        generate_responses(
            db_path, run_id, MockCandidateProvider(), config["prompt_template_version"]
        )
        judges = [MockJudgeProvider(index) for index in range(config["demo_judge_count"])]
        judge_responses(
            db_path, run_id, judges, rubric, config["judge_prompt_version"]
        )
        score_run(db_path, run_id, rubric, config["scoring"])
        print(json.dumps(report_run(db_path, run_id), ensure_ascii=False, indent=2))
        return 0

    if args.command == "export-prompts":
        target = resolve_path(args.config, args.output)
        instruction_path = resolve_path(
            args.config, config.get("candidate_prompt_path", "config/candidate_prompt.txt")
        )
        try:
            count = export_prompts(
                cases_path, target, rubric=rubric, authoring=config.get("authoring", {}),
                instruction=instruction_path.read_text(encoding="utf-8").strip(),
                prompt_template_version=config["prompt_template_version"],
            )
        except (ValueError, FileExistsError, OSError) as exc:
            print(f"Cannot export prompts: {exc}")
            return 2
        print(json.dumps({"output": str(target), "case_count": count}, indent=2))
        return 0

    if args.command == "generate-gemini":
        target = resolve_path(args.config, args.output)
        instruction_path = resolve_path(
            args.config, config.get("candidate_prompt_path", "config/candidate_prompt.txt")
        )
        try:
            rows = candidate_rows(
                cases_path, rubric=rubric, authoring=config.get("authoring", {}),
                instruction=instruction_path.read_text(encoding="utf-8").strip(),
                prompt_template_version=config["prompt_template_version"],
            )
            if not 1 <= args.limit <= len(rows):
                raise GeminiRunError(f"--limit must be between 1 and {len(rows)}.")
            if not args.live:
                print(json.dumps({
                    "status": "dry_run_no_api_calls", "model": args.model,
                    "planned_cases": args.limit, "total_cases": len(rows),
                    "output": str(target),
                }, indent=2))
                return 0
            key = local_api_key(resolve_path(args.config, args.env_file))
            result = run_gemini(
                rows, target, model=args.model, api_key=key, limit=args.limit,
                timeout=args.timeout, retries=args.retries,
                progress=lambda done, total, case_id: print(f"Gemini {done}/{total}: {case_id}"),
                provenance=candidate_provenance(config, rubric, Path(__file__).resolve().parents[1]),
            )
        except (GeminiRunError, FileExistsError, ValueError, OSError) as exc:
            print(f"Cannot generate Gemini answers: {exc}")
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "generate-grok":
        target = resolve_path(args.config, args.output)
        env_path = resolve_path(args.config, args.env_file)
        instruction_path = resolve_path(
            args.config, config.get("candidate_prompt_path", "config/candidate_prompt.txt")
        )
        try:
            model = args.model or read_setting(env_path, "GROK_MODEL")
            rows = grok_candidate_rows(
                cases_path, rubric=rubric, authoring=config.get("authoring", {}),
                instruction=instruction_path.read_text(encoding="utf-8").strip(),
                prompt_template_version=config["prompt_template_version"],
            )
            if not 1 <= args.limit <= len(rows):
                raise ValueError(f"--limit must be between 1 and {len(rows)}")
            if not args.live:
                print(json.dumps({"status": "dry_run_no_api_calls", "model": model,
                                  "planned_cases": args.limit, "total_cases": len(rows),
                                  "output": str(target)}, indent=2))
                return 0
            key = read_setting(env_path, "GROK_API_KEY", secret=True)
            result = run_grok(
                rows, target, model=model, api_key=key, limit=args.limit,
                timeout=args.timeout, retries=args.retries,
                progress=lambda done, total, case_id: print(f"Grok {done}/{total}: {case_id}"),
                provenance=candidate_provenance(config, rubric, Path(__file__).resolve().parents[1]),
            )
        except (ProviderRequestError, FileExistsError, ValueError, OSError) as exc:
            print(f"Cannot generate Grok answers: {exc}")
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "import-responses":
        try:
            run_id = import_answers(
                db_path, cases_path, Path(args.input), config=config, rubric=rubric,
                provider=args.provider, model_id=args.model_id, model_version=args.model_version,
            )
        except (ValueError, OSError) as exc:
            print(f"Cannot import responses: {exc}")
            return 2
        print(json.dumps({"run_id": run_id, "response_count": len(load_jsonl(args.input)), "status": "awaiting_mock_or_future_real_judges"}, indent=2))
        return 0

    if args.command == "score-imported-demo":
        with connect(db_path) as conn:
            expected = {
                (row["case_id"], row["case_version"])
                for row in conn.execute(
                    "SELECT case_id, case_version FROM run_cases WHERE run_id = ?", (args.run_id,)
                )
            }
            actual = [
                (row["case_id"], row["case_version"])
                for row in conn.execute(
                    "SELECT case_id, case_version FROM model_responses WHERE run_id = ?", (args.run_id,)
                )
            ]
            judged = conn.execute("SELECT COUNT(*) FROM judge_outputs WHERE run_id = ?", (args.run_id,)).fetchone()[0]
            scored = conn.execute("SELECT COUNT(*) FROM scores WHERE run_id = ?", (args.run_id,)).fetchone()[0]
        if not expected or len(actual) != len(expected) or set(actual) != expected or judged or scored:
            print("Run must have one unjudged, unscored response per snapshotted case.")
            return 2
        judges = [MockJudgeProvider(index) for index in range(config["demo_judge_count"])]
        judge_responses(db_path, args.run_id, judges, rubric, config["judge_prompt_version"])
        score_run(db_path, args.run_id, rubric, config["scoring"])
        print(json.dumps(report_run(db_path, args.run_id), ensure_ascii=False, indent=2))
        return 0

    if args.command == "judge-imported-gemini":
        env_path = resolve_path(args.config, args.env_file)
        try:
            model = args.model or read_setting(env_path, "GEMINI_JUDGE_MODEL")
            pending, _version, total = gemini_judge_status(
                db_path, args.run_id, model=model,
                judge_prompt_version=config["judge_prompt_version"],
                rubric_version=rubric["version"],
            )
            if args.limit < 1:
                raise ValueError("--limit must be positive")
            if not args.live:
                print(json.dumps({"status": "dry_run_no_api_calls", "run_id": args.run_id,
                                  "model": model, "total_cases": total,
                                  "remaining_unjudged": len(pending),
                                  "planned_judgments": min(args.limit, len(pending))}, indent=2))
                return 0
            key = read_setting(env_path, "GEMINI_API_KEY", secret=True)
            judge_instruction = resolve_path(
                args.config, config.get("absolute_judge_prompt_path", "config/absolute_judge_prompt.txt")
            ).read_text(encoding="utf-8").strip()
            result = judge_imported_grok(
                db_path, args.run_id, model=model, api_key=key,
                instruction=judge_instruction, rubric=rubric,
                judge_prompt_version=config["judge_prompt_version"],
                scoring=config["scoring"], limit=args.limit,
                timeout=args.timeout, retries=args.retries,
                progress=lambda done, total, case_id: print(f"Gemini judge {done}/{total}: {case_id}"),
            )
        except (ProviderRequestError, ValueError, OSError) as exc:
            print(f"Cannot judge imported responses: {exc}")
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "report":
        print(json.dumps(report_run(db_path, args.run_id), ensure_ascii=False, indent=2))
        return 0

    if args.command == "coverage-audit":
        try:
            result = audit_coverage(
                load_jsonl(cases_path),
                load_json(resolve_path(args.config, config.get("coverage_tags_path", "data/alpha/coverage_tags.json"))),
                load_json(resolve_path(args.config, config.get("family_splits_path", "data/alpha/family_splits.json"))),
                load_json(resolve_path(args.config, config.get("family_labels_path", "data/alpha/family_labels.json"))),
            )
        except (ValueError, KeyError, OSError) as exc:
            print(f"Cannot audit coverage: {exc}")
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "compare-multiturn-bilingual-probes":
        try:
            batch_paths = config.get("multiturn_cases_paths") or [
                config.get("multiturn_cases_path", "data/multiturn/pilot_cases.json")
            ]
            dataset = merge_multiturn_datasets([
                load_json(resolve_path(args.config, path)) for path in batch_paths
            ])
            probes = load_json(resolve_path(
                args.config, config.get("multiturn_bilingual_probes_path", "data/multiturn/bilingual_judge_probes.json")
            ))
            mt_rubric = load_json(resolve_path(
                args.config, config.get("multiturn_rubric_path", "config/multiturn_rubric.json")
            ))
            instruction = resolve_path(
                args.config, config.get("multiturn_judge_prompt_path", "config/multiturn_judge_prompt.txt")
            ).read_text(encoding="utf-8").strip()
            target = resolve_path(args.config, args.output)
            if target.exists():
                raise FileExistsError(f"Refusing to overwrite bilingual comparison: {target}")
            result = compare_bilingual_probe_reports(
                dataset, probes, load_json(resolve_path(args.config, args.first)),
                [load_json(resolve_path(args.config, path)) for path in args.second],
                mt_rubric, sha256_text(instruction),
            )
            from datetime import datetime, timezone

            result["generated_at"] = datetime.now(timezone.utc).isoformat()
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except (ProviderRequestError, FileExistsError, ValueError, KeyError, TypeError, OSError) as exc:
            print(f"Cannot compare bilingual probes: {exc}")
            return 2
        print(json.dumps({
            "output": str(target), "pair_count": result["pair_count"],
            "same_positive_direction_count": result["same_positive_direction_count"],
            "exact_gap_agreement_count": result["exact_gap_agreement_count"],
            "challenge_review_flag_agreement_count": result["challenge_review_flag_agreement_count"],
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "compare-model-matrix":
        try:
            comparison = compare_matrix_reports([
                load_json(resolve_path(args.config, path)) for path in args.report
            ])
            target = resolve_path(args.config, args.output)
            if target.exists():
                raise FileExistsError("Model-matrix comparison already exists; choose a new output")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as handle:
                json.dump(comparison, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except (FileExistsError, ValueError, KeyError, TypeError, OSError) as exc:
            print(f"Cannot compare model matrix: {exc}")
            return 2
        print(json.dumps({"output": str(target), "status": comparison["status"],
                          "candidate_count": len(comparison["candidate_results"]),
                          "case_count": len(comparison["case_revisions"])}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "model-matrix":
        try:
            batch_paths = config.get("multiturn_cases_paths") or [
                config.get("multiturn_cases_path", "data/multiturn/pilot_cases.json")
            ]
            dataset = merge_multiturn_datasets([
                load_json(resolve_path(args.config, path)) for path in batch_paths
            ])
            roster = load_json(resolve_path(args.config, args.roster))
            plan, selected, candidates, judges = prepare_matrix(
                roster, dataset, candidate_id=args.candidate_id,
                selected_case_ids=args.case_id,
            )
            if not args.live:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
                return 0
            candidate_instruction = resolve_path(
                args.config, config.get("candidate_prompt_path", "config/candidate_prompt.txt")
            ).read_text(encoding="utf-8").strip()
            judge_instruction = resolve_path(
                args.config, config.get("multiturn_judge_prompt_path", "config/multiturn_judge_prompt.txt")
            ).read_text(encoding="utf-8").strip()
            mt_rubric = load_json(resolve_path(
                args.config, config.get("multiturn_rubric_path", "config/multiturn_rubric.json")
            ))
            result = run_matrix(
                plan, selected, candidates, judges, dataset, mt_rubric,
                output_dir=resolve_path(args.config, args.output_dir),
                env_file=resolve_path(args.config, args.env_file),
                candidate_instruction=candidate_instruction,
                judge_instruction=judge_instruction,
                max_api_calls=args.max_api_calls, timeout=args.timeout,
                retries=0,
            )
        except (ProviderRequestError, FileExistsError, ValueError, KeyError, TypeError, OSError) as exc:
            print(f"Cannot process model matrix: {exc}")
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command in {"validate-multiturn", "generate-grok-multiturn", "generate-gemini-multiturn", "export-multiturn-judge-packets", "judge-multiturn-gemini", "judge-multiturn-contrast", "judge-multiturn-bilingual-probes", "difficulty-audit-multiturn", "compare-multiturn-judges"}:
        try:
            batch_paths = config.get("multiturn_cases_paths")
            if getattr(args, "cases_paths", None):
                batch_paths = args.cases_paths
            if batch_paths is None:
                batch_paths = [config.get("multiturn_cases_path", "data/multiturn/pilot_cases.json")]
            if not isinstance(batch_paths, list) or not batch_paths or any(
                not isinstance(path, str) or not path.strip() for path in batch_paths
            ):
                raise ValueError("multiturn_cases_paths must be a nonempty list of paths")
            dataset = merge_multiturn_datasets([
                load_json(resolve_path(args.config, path)) for path in batch_paths
            ])
            status = validate_multiturn_dataset(dataset)
            if args.command == "validate-multiturn":
                print(json.dumps(status, ensure_ascii=False, indent=2))
                return 0
            if args.command == "difficulty-audit-multiturn":
                answers_path = resolve_path(args.config, args.answers)
                judgments_path = resolve_path(args.config, args.judgments)
                mt_rubric = load_json(resolve_path(
                    args.config, config.get("multiturn_rubric_path", "config/multiturn_rubric.json")
                ))
                report = audit_multiturn_difficulty(
                    dataset, load_jsonl(answers_path), load_jsonl(judgments_path),
                    load_json(answers_path.with_suffix(".manifest.json")),
                    load_json(judgments_path.with_suffix(".manifest.json")), mt_rubric,
                )
                if args.output:
                    target = resolve_path(args.config, args.output)
                    if target.exists():
                        raise FileExistsError(f"Refusing to overwrite difficulty report: {target}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("x", encoding="utf-8") as handle:
                        json.dump(report, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0
            if args.command == "compare-multiturn-judges":
                answers_path = resolve_path(args.config, args.answers)
                first_path = resolve_path(args.config, args.first)
                second_path = resolve_path(args.config, args.second)
                if first_path == second_path:
                    raise ValueError("Judge passes must use different files")
                mt_rubric = load_json(resolve_path(
                    args.config, config.get("multiturn_rubric_path", "config/multiturn_rubric.json")
                ))
                report = compare_multiturn_judge_passes(
                    dataset, load_jsonl(answers_path),
                    load_json(answers_path.with_suffix(".manifest.json")),
                    load_jsonl(first_path), load_json(first_path.with_suffix(".manifest.json")),
                    load_jsonl(second_path), load_json(second_path.with_suffix(".manifest.json")),
                    mt_rubric,
                )
                if args.output:
                    target = resolve_path(args.config, args.output)
                    if target.exists():
                        raise FileExistsError(f"Refusing to overwrite comparison report: {target}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("x", encoding="utf-8") as handle:
                        json.dump(report, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0
            if args.command == "export-multiturn-judge-packets":
                answers = load_jsonl(resolve_path(args.config, args.answers))
                packets = judge_packets_from_answers(dataset, answers)
                target = resolve_path(args.config, args.output)
                if target.exists():
                    raise FileExistsError(f"Refusing to overwrite: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8") as handle:
                    for packet in packets:
                        handle.write(json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n")
                print(json.dumps({"status": "draft_packets_not_clinical_scores", "packet_count": len(packets),
                                  "output": str(target)}, indent=2))
                return 0
            if args.command == "judge-multiturn-gemini":
                from datetime import datetime, timezone

                answers = load_jsonl(resolve_path(args.config, args.answers))
                packets = judge_packets_from_answers(dataset, answers)
                if not 1 <= args.limit <= len(packets):
                    raise ValueError(f"--limit must be between 1 and {len(packets)}")
                target = resolve_path(args.config, args.output)
                manifest_path = target.with_suffix(".manifest.json")
                if target.exists() or manifest_path.exists():
                    raise FileExistsError(f"Refusing to overwrite answer or manifest: {target}")
                env_path = resolve_path(args.config, args.env_file)
                model = args.model or read_setting(env_path, "GEMINI_JUDGE_MODEL")
                if not args.live:
                    print(json.dumps({"status": "dry_run_no_api_calls", "model": model,
                                      "planned_judgments": args.limit, "output": str(target)}, indent=2))
                    return 0
                instruction = resolve_path(
                    args.config, config.get("multiturn_judge_prompt_path", "config/multiturn_judge_prompt.txt")
                ).read_text(encoding="utf-8").strip()
                mt_rubric = load_json(resolve_path(
                    args.config, config.get("multiturn_rubric_path", "config/multiturn_rubric.json")
                ))
                judge = GeminiMultiturnJudge(
                    model=model, api_key=read_setting(env_path, "GEMINI_API_KEY", secret=True),
                    instruction=instruction,
                )
                results = []
                for packet in packets[:args.limit]:
                    judgment = judge.evaluate(packet)
                    results.append({
                        "case_id": packet["case_id"],
                        "case_content_hash": packet["case_content_hash"],
                        "judgment": judgment,
                        "score": score_judgment(judgment, packet, mt_rubric),
                    })
                manifest = {
                    "status": "experimental_unvalidated_single_ai_judge",
                    "provider": "google-gemini", "requested_model": model,
                    "returned_model": judge.model_version,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "case_count": len(results),
                    "judge_instruction_sha256": sha256_text(instruction),
                    "rubric_sha256": sha256_json(mt_rubric),
                    "actual_request_parameters": {"store": False, "response_format": "json_schema"},
                    "sampling_policy": "provider_default_unpinned",
                    "case_revisions": [
                        {"case_id": item["case_id"], "case_content_hash": item["case_content_hash"]}
                        for item in results
                    ],
                    "provenance": candidate_provenance(config, mt_rubric, Path(__file__).resolve().parents[1]),
                }
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8") as handle:
                    for item in results:
                        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
                with manifest_path.open("x", encoding="utf-8") as handle:
                    json.dump(manifest, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                print(json.dumps({"output": str(target), "manifest": str(manifest_path), **manifest}, ensure_ascii=False, indent=2))
                return 0
            if args.command == "judge-multiturn-contrast":
                pairs = load_json(resolve_path(
                    args.config, config.get("multiturn_contrasts_path", "data/multiturn/contrast_transcripts.json")
                ))["pairs"]
                if args.family_id:
                    if args.limit != 1:
                        raise ValueError("--family-id requires the default --limit 1")
                    pairs = [pair for pair in pairs if pair["family_id"] == args.family_id]
                    if not pairs:
                        raise ValueError(f"Unknown contrast family: {args.family_id}")
                if not 1 <= args.limit <= len(pairs):
                    raise ValueError(f"--limit must be between 1 and {len(pairs)}")
                selected_pairs = pairs[:args.limit]
                planned_calls = sum(3 if "partial_update_response" in pair else 2 for pair in selected_pairs)
                target = resolve_path(args.config, args.output)
                if target.exists():
                    raise FileExistsError(f"Refusing to overwrite contrast output: {target}")
                env_path = resolve_path(args.config, args.env_file)
                model = args.model or read_setting(env_path, "GEMINI_JUDGE_MODEL")
                if not args.live:
                    print(json.dumps({"status": "dry_run_no_api_calls", "model": model,
                                      "planned_pairs": args.limit, "planned_api_calls": planned_calls,
                                      "output": str(target)}, indent=2))
                    return 0
                instruction = resolve_path(
                    args.config, config.get("multiturn_judge_prompt_path", "config/multiturn_judge_prompt.txt")
                ).read_text(encoding="utf-8").strip()
                mt_rubric = load_json(resolve_path(
                    args.config, config.get("multiturn_rubric_path", "config/multiturn_rubric.json")
                ))
                judge = GeminiMultiturnJudge(
                    model=model, api_key=read_setting(env_path, "GEMINI_API_KEY", secret=True),
                    instruction=instruction,
                )
                result = assess_contrast_pairs(dataset, selected_pairs, judge, mt_rubric)
                from datetime import datetime, timezone

                result.update({
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "judge_instruction_sha256": sha256_text(instruction),
                    "rubric_sha256": sha256_json(mt_rubric),
                    "actual_request_parameters": {"store": False, "response_format": "json_schema"},
                    "provenance": candidate_provenance(config, mt_rubric, Path(__file__).resolve().parents[1]),
                })
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8") as handle:
                    json.dump(result, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                print(json.dumps({"output": str(target), **result}, ensure_ascii=False, indent=2))
                return 0
            if args.command == "judge-multiturn-bilingual-probes":
                probes = load_json(resolve_path(
                    args.config, config.get("multiturn_bilingual_probes_path", "data/multiturn/bilingual_judge_probes.json")
                ))
                if args.family_id:
                    selected = [pair for pair in probes["pairs"] if pair["family_id"] == args.family_id]
                    if not selected:
                        raise ValueError(f"Unknown bilingual probe family: {args.family_id}")
                    probes = {**probes, "pairs": selected}
                pairs = validate_probe_set(dataset, probes)
                target = resolve_path(args.config, args.output)
                if target.exists():
                    raise FileExistsError(f"Refusing to overwrite bilingual probe output: {target}")
                env_path = resolve_path(args.config, args.env_file)
                is_gemini_judge = args.provider == "gemini"
                model = args.model or read_setting(
                    env_path, "GEMINI_JUDGE_MODEL" if is_gemini_judge else "GROK_MODEL"
                )
                if not args.live:
                    print(json.dumps({"status": "dry_run_no_api_calls", "provider": args.provider,
                                      "model": model, "planned_pairs": len(pairs),
                                      "planned_api_calls": len(pairs) * 2,
                                      "output": str(target)}, indent=2))
                    return 0
                instruction = resolve_path(
                    args.config, config.get("multiturn_judge_prompt_path", "config/multiturn_judge_prompt.txt")
                ).read_text(encoding="utf-8").strip()
                mt_rubric = load_json(resolve_path(
                    args.config, config.get("multiturn_rubric_path", "config/multiturn_rubric.json")
                ))
                judge_class = GeminiMultiturnJudge if is_gemini_judge else GrokMultiturnJudge
                judge = judge_class(
                    model=model,
                    api_key=read_setting(env_path, "GEMINI_API_KEY" if is_gemini_judge else "GROK_API_KEY", secret=True),
                    instruction=instruction,
                    timeout=args.timeout,
                )
                result = run_bilingual_probes(dataset, probes, judge, mt_rubric)
                from datetime import datetime, timezone

                result.update({
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "probe_set_sha256": sha256_json(probes),
                    "judge_instruction_sha256": sha256_text(instruction),
                    "rubric_sha256": sha256_json(mt_rubric),
                    "actual_request_parameters": {"store": False, "response_format": "json_schema"},
                    "timeout_seconds": args.timeout,
                    "sampling_policy": "provider_default_unpinned",
                    "provenance": candidate_provenance(config, mt_rubric, Path(__file__).resolve().parents[1]),
                })
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8") as handle:
                    json.dump(result, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                print(json.dumps({
                    "output": str(target), "judge_provider": result["judge_provider"],
                    "judge_model_returned": result["judge_model_returned"],
                    "probe_count": result["probe_count"],
                    "positive_gap_count": result["positive_gap_count"],
                    "family_language_gaps": result["family_language_gaps"],
                }, ensure_ascii=False, indent=2))
                return 0
            selected = ordered_variants(dataset)
            if args.family_ids:
                if args.case_id:
                    raise ValueError("--family-ids and --case-id cannot be combined")
                requested = [item.strip() for item in args.family_ids.split(",")]
                known = {family["family_id"] for family in dataset["families"]}
                if (not requested or any(not item or item not in known for item in requested)
                    or len(requested) != len(set(requested))):
                    raise ValueError("--family-ids must list distinct configured family IDs")
                selected = [(family, language) for family, language in selected
                            if family["family_id"] in requested]
                if args.limit != len(selected):
                    raise ValueError(f"--family-ids selects {len(selected)} variants; set --limit {len(selected)}")
            if args.case_id:
                if args.limit != 1:
                    raise ValueError("--case-id requires the default --limit 1")
                selected = [(family, language) for family, language in selected
                            if variant_id(family, language) == args.case_id]
                if not selected:
                    raise ValueError(f"Unknown multi-turn case ID: {args.case_id}")
            if not 1 <= args.limit <= len(selected):
                raise ValueError(f"--limit must be between 1 and {len(selected)}")
            target = resolve_path(args.config, args.output)
            if target.exists() or target.with_suffix(".manifest.json").exists():
                raise FileExistsError(f"Refusing to overwrite answer or manifest: {target}")
            env_path = resolve_path(args.config, args.env_file)
            is_gemini_candidate = args.command == "generate-gemini-multiturn"
            model = args.model if is_gemini_candidate else args.model or read_setting(env_path, "GROK_MODEL")
            if not args.live:
                print(json.dumps({"status": "dry_run_no_api_calls", "model": model,
                                  "planned_variants": args.limit, "planned_api_calls": args.limit * 2,
                                  "output": str(target)}, indent=2))
                return 0
            instruction = resolve_path(
                args.config, config.get("candidate_prompt_path", "config/candidate_prompt.txt")
            ).read_text(encoding="utf-8").strip()
            if is_gemini_candidate:
                candidate = GeminiConversationProvider(
                    model=model, api_key=read_setting(env_path, "GEMINI_API_KEY", secret=True),
                    instruction=instruction,
                )
            else:
                candidate = GrokConversationProvider(
                    model=model, api_key=read_setting(env_path, "GROK_API_KEY", secret=True),
                    instruction=instruction,
                )
            result = write_batch(
                dataset, selected[:args.limit], candidate, target, instruction=instruction,
                provenance=candidate_provenance(config, rubric, Path(__file__).resolve().parents[1]),
            )
        except (ProviderRequestError, FileExistsError, ValueError, KeyError, OSError) as exc:
            print(f"Cannot process multi-turn pilot: {exc}")
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "judge-contrast-gemini":
        try:
            pairs = load_json(resolve_path(
                args.config, config.get("judge_contrasts_path", "data/alpha/judge_contrasts.json")
            ))["pairs"]
            if not 1 <= args.limit <= len(pairs):
                raise ValueError(f"--limit must be between 1 and {len(pairs)}")
            target = resolve_path(args.config, args.output)
            if target.exists():
                raise FileExistsError(f"Refusing to overwrite diagnostic output: {target}")
            model = args.model or read_setting(
                resolve_path(args.config, args.env_file), "GEMINI_JUDGE_MODEL"
            )
            if not args.live:
                print(json.dumps({
                    "status": "dry_run_no_api_calls", "model": model,
                    "planned_pairs": args.limit, "planned_api_calls": args.limit * 2,
                    "output": str(target),
                }, indent=2))
                return 0
            key = read_setting(resolve_path(args.config, args.env_file), "GEMINI_API_KEY", secret=True)
            instruction = resolve_path(
                args.config, config.get("absolute_judge_prompt_path", "config/absolute_judge_prompt.txt")
            ).read_text(encoding="utf-8").strip()
            judge = GeminiJudgeProvider(model=model, api_key=key, instruction=instruction)
            result = assess_contrasts(
                load_jsonl(cases_path), pairs[:args.limit], judge, rubric, config["scoring"]
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except (ProviderRequestError, FileExistsError, ValueError, KeyError, OSError) as exc:
            print(f"Cannot run judge contrasts: {exc}")
            return 2
        print(json.dumps({"output": str(target), **result}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate-data":
        target = resolve_path(args.config, args.cases) if args.cases else cases_path
        result = validate_dataset(
            target,
            rubric,
            config.get("authoring", {}),
            release_ready=args.release_ready,
        )
        if args.release_ready and result["valid"]:
            configured_reviews = config.get("reviews_path", "data/reviews")
            reviews_path = resolve_path(
                args.config, args.reviews if args.reviews else configured_reviews
            )
            review_report = assess_reviews(
                target,
                reviews_path,
                config.get("review_policy", {}),
            )
            evidence_issues = release_review_issues(load_jsonl(target), review_report)
            result["issues"].extend(evidence_issues)
            result["error_count"] += len(evidence_issues)
            result["valid"] = result["error_count"] == 0
            result["review_evidence"] = {
                "reviews_path": str(reviews_path),
                "review_record_count": review_report["review_record_count"],
                "error_count": review_report["error_count"],
            }
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(
                f"{target}: {result['case_count']} cases, "
                f"{result['error_count']} errors, {result['warning_count']} warnings"
            )
            for issue in result["issues"]:
                location = issue.get("case_id") or f"line {issue.get('line', '?')}"
                print(
                    f"{issue['level'].upper()} {issue['code']} "
                    f"[{location}] {issue['path']}: {issue['message']}"
                )
        return 1 if result["error_count"] else 0

    if args.command == "dataset-status":
        target = resolve_path(args.config, args.cases) if args.cases else cases_path
        result = summarize_dataset(target, rubric, config.get("authoring", {}))
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            queue = result["review_queue"]
            print(f"Dataset: {target}")
            print(
                f"Cases: {result['case_count']} | Families: {result['family_count']} | "
                f"Complete bilingual pairs: {result['complete_bilingual_families']}"
            )
            print(f"Families by category: {json.dumps(result['categories_by_family'], sort_keys=True)}")
            print(f"Languages: {json.dumps(result['languages_by_case'], sort_keys=True)}")
            print(f"Statuses: {json.dumps(result['statuses_by_case'], sort_keys=True)}")
            print(
                "Review queue: "
                f"clinical={len(queue['clinical_review_pending'])}, "
                f"language={len(queue['language_review_pending'])}, "
                f"sources={len(queue['source_review_pending'])}, "
                f"release_status={len(queue['release_status_pending'])}"
            )
            validation = result["development_validation"]
            print(
                "Development validation: "
                f"errors={validation['error_count']}, warnings={validation['warning_count']}"
            )
        return 0 if result["development_validation"]["valid"] else 1

    if args.command in {"validate-reviews", "review-status"}:
        configured_reviews = config.get("reviews_path", "data/reviews")
        reviews_path = resolve_path(
            args.config, args.reviews if args.reviews else configured_reviews
        )
        result = assess_reviews(
            cases_path,
            reviews_path,
            config.get("review_policy", {}),
        )
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "validate-reviews":
            print(
                f"{reviews_path}: {result['review_record_count']} reviews, "
                f"{result['error_count']} errors, {result['warning_count']} warnings"
            )
            for issue in result["issues"]:
                identity = issue.get("review_id") or issue["source"]
                print(
                    f"{issue['level'].upper()} {issue['code']} "
                    f"[{identity}] {issue['path']}: {issue['message']}"
                )
        else:
            queue = result["review_queue"]
            print(f"Reviews: {reviews_path}")
            print(
                f"Records: {result['review_record_count']} | "
                f"Errors: {result['error_count']} | Warnings: {result['warning_count']}"
            )
            print(f"Decisions: {json.dumps(result['decision_counts'], sort_keys=True)}")
            print(
                "Review gates: "
                f"clinical_pending={len(queue['clinical_review_pending'])}, "
                f"language_pending={len(queue['language_review_pending'])}, "
                f"complete={len(queue['review_gates_complete'])}"
            )
        return 0 if result["valid"] else 1

    if args.command == "review-template":
        cases = [case for case in load_jsonl(cases_path) if case.get("id") == args.case_id]
        if len(cases) != 1:
            print(f"Expected one case with ID {args.case_id!r}; found {len(cases)}.")
            return 2
        try:
            record = build_review_template(
                cases[0],
                review_type=args.review_type,
                reviewer_id=args.reviewer_id,
                role=args.role,
                qualification_scope=args.qualification_scope,
                jurisdiction_scope=args.jurisdiction_scope,
            )
        except ValueError as exc:
            print(f"Cannot create review template: {exc}")
            return 2
        encoded = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output_path = Path(args.output)
            if output_path.exists():
                print(f"Refusing to overwrite append-only review file: {output_path}")
                return 2
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(encoded, encoding="utf-8")
            print(output_path)
        else:
            print(encoded, end="")
        return 0

    if args.command == "export-review-packets":
        result = validate_dataset(cases_path, rubric, config.get("authoring", {}))
        if not result["valid"] or result["warning_count"]:
            print(
                "Resolve development validation errors and warnings before exporting packets."
            )
            return 1
        try:
            manifest = export_review_packets(
                load_jsonl(cases_path), resolve_path(args.config, args.output_dir)
            )
        except (ValueError, FileExistsError) as exc:
            print(f"Cannot export reviewer packets: {exc}")
            return 2
        print(
            json.dumps(
                {
                    "output_dir": manifest["output_dir"],
                    "family_count": manifest["family_count"],
                    "case_count": manifest["case_count"],
                },
                indent=2,
            )
        )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
