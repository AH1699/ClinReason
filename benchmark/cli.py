from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_json, load_jsonl, resolve_path
from .dataset_status import summarize_dataset
from .pipeline import (
    bootstrap,
    create_run,
    generate_responses,
    judge_responses,
    report_run,
    score_run,
)
from .providers.mock import MockCandidateProvider, MockJudgeProvider
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
    report = sub.add_parser("report", help="Print a JSON report for a run")
    report.add_argument("run_id")
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

    if args.command == "report":
        print(json.dumps(report_run(db_path, args.run_id), ensure_ascii=False, indent=2))
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
