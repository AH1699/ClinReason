from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ID_PATTERN = re.compile(r"^[A-Z0-9_-]+$")
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
CASE_STATUSES = {"draft", "example_unvalidated", "clinician_validated", "gold"}
DIFFICULTIES = {"easy", "medium", "hard", "adversarial"}
REQUIRED_FIELDS = {
    "id",
    "version",
    "status",
    "sector",
    "category",
    "prompt",
    "reference_answer",
    "critical_requirements",
    "critical_errors",
    "applicable_dimensions",
    "metadata",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | {
    "language",
    "subsector",
    "subcategory",
    "difficulty",
}
REQUIRED_METADATA_FIELDS = {
    "synthetic",
    "clinician_validated",
    "medical_advice",
    "source_refs",
}


def _issue(
    level: str,
    code: str,
    message: str,
    *,
    path: str = "$",
    case_id: str | None = None,
    line: int | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {
        "level": level,
        "code": code,
        "path": path,
        "message": message,
    }
    if case_id:
        issue["case_id"] = case_id
    if line is not None:
        issue["line"] = line
    return issue


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_placeholder(value: Any) -> bool:
    if not _nonempty_string(value):
        return True
    normalized = value.strip().casefold()
    return normalized in {"tbd", "todo", "unknown", "replace_me"} or normalized.startswith(
        "replace with"
    )


def validate_case(
    case: Any,
    rubric: dict[str, Any],
    authoring: dict[str, Any] | None = None,
    *,
    release_ready: bool = False,
    line: int | None = None,
) -> list[dict[str, Any]]:
    """Validate one case against the v0.1 case contract and release policy."""
    authoring = authoring or {}
    issues: list[dict[str, Any]] = []
    if not isinstance(case, dict):
        return [
            _issue(
                "error",
                "CASE_NOT_OBJECT",
                "Each JSONL row must be an object.",
                line=line,
            )
        ]

    case_id = case.get("id") if isinstance(case.get("id"), str) else None

    def add(level: str, code: str, message: str, path: str = "$") -> None:
        issues.append(
            _issue(
                level,
                code,
                message,
                path=path,
                case_id=case_id,
                line=line,
            )
        )

    for field in sorted(REQUIRED_FIELDS - set(case)):
        add("error", "MISSING_FIELD", f"Required field '{field}' is missing.", f"$.{field}")
    for field in sorted(set(case) - ALLOWED_FIELDS):
        add("error", "UNKNOWN_FIELD", f"Unknown field '{field}'.", f"$.{field}")

    if "id" in case and (
        not _nonempty_string(case["id"]) or not ID_PATTERN.fullmatch(case["id"])
    ):
        add("error", "INVALID_ID", "ID must match ^[A-Z0-9_-]+$.", "$.id")
    if "version" in case and (
        not isinstance(case["version"], str)
        or not SEMVER_PATTERN.fullmatch(case["version"])
    ):
        add("error", "INVALID_VERSION", "Version must be exact semantic version X.Y.Z.", "$.version")
    if case.get("status") not in CASE_STATUSES:
        add("error", "INVALID_STATUS", f"Status must be one of {sorted(CASE_STATUSES)}.", "$.status")
    if "difficulty" in case and case.get("difficulty") not in DIFFICULTIES:
        add(
            "error",
            "INVALID_DIFFICULTY",
            f"Difficulty must be one of {sorted(DIFFICULTIES)}.",
            "$.difficulty",
        )

    supported_languages = authoring.get("supported_languages", ["en", "zh-CN"])
    if not _nonempty_string(case.get("language")):
        add("error", "MISSING_LANGUAGE", "Language is required by the authoring policy.", "$.language")
    elif case["language"] not in supported_languages:
        add(
            "error",
            "UNSUPPORTED_LANGUAGE",
            f"Language must be one of {supported_languages}.",
            "$.language",
        )

    for field in ("sector", "category", "prompt", "reference_answer"):
        if field in case and not _nonempty_string(case[field]):
            add("error", "EMPTY_FIELD", f"'{field}' must be a non-empty string.", f"$.{field}")

    allowed_categories = authoring.get("allowed_categories")
    if allowed_categories and case.get("category") not in allowed_categories:
        add(
            "error",
            "UNKNOWN_CATEGORY",
            f"Category must be one of {allowed_categories}.",
            "$.category",
        )

    for field in ("critical_requirements", "critical_errors", "applicable_dimensions"):
        if field in case and not isinstance(case[field], list):
            add("error", "INVALID_TYPE", f"'{field}' must be an array.", f"$.{field}")

    requirements = case.get("critical_requirements")
    if isinstance(requirements, list):
        if not requirements:
            add(
                "error",
                "NO_CRITICAL_REQUIREMENTS",
                "At least one observable critical requirement is required.",
                "$.critical_requirements",
            )
        for index, item in enumerate(requirements):
            if not _nonempty_string(item):
                add(
                    "error",
                    "INVALID_REQUIREMENT",
                    "Each critical requirement must be a non-empty string.",
                    f"$.critical_requirements[{index}]",
                )
        if len(requirements) != len(set(requirements)):
            add(
                "error",
                "DUPLICATE_REQUIREMENT",
                "Critical requirements must be unique within a case.",
                "$.critical_requirements",
            )

    critical_errors = case.get("critical_errors")
    if isinstance(critical_errors, list):
        error_ids: list[str] = []
        for index, error in enumerate(critical_errors):
            base = f"$.critical_errors[{index}]"
            if not isinstance(error, dict):
                add("error", "INVALID_CRITICAL_ERROR", "Critical error must be an object.", base)
                continue
            unknown = set(error) - {"id", "severity", "description", "trigger_terms"}
            missing = {"id", "severity", "description"} - set(error)
            for field in sorted(missing):
                add("error", "MISSING_CRITICAL_ERROR_FIELD", f"Missing '{field}'.", f"{base}.{field}")
            for field in sorted(unknown):
                add("error", "UNKNOWN_CRITICAL_ERROR_FIELD", f"Unknown '{field}'.", f"{base}.{field}")
            if _nonempty_string(error.get("id")):
                error_ids.append(error["id"])
            else:
                add("error", "INVALID_CRITICAL_ERROR_ID", "Critical-error ID is required.", f"{base}.id")
            if type(error.get("severity")) is not int or error.get("severity") not in {1, 2, 3}:
                add("error", "INVALID_SEVERITY", "Severity must be integer 1, 2, or 3.", f"{base}.severity")
            if not _nonempty_string(error.get("description")):
                add("error", "INVALID_DESCRIPTION", "Description is required.", f"{base}.description")
            trigger_terms = error.get("trigger_terms")
            if trigger_terms is not None and (
                not isinstance(trigger_terms, list)
                or any(not _nonempty_string(item) for item in trigger_terms)
            ):
                add("error", "INVALID_TRIGGER_TERMS", "Trigger terms must be strings.", f"{base}.trigger_terms")
        if len(error_ids) != len(set(error_ids)):
            add("error", "DUPLICATE_CRITICAL_ERROR_ID", "Critical-error IDs must be unique.", "$.critical_errors")

    rubric_dimensions = {item["id"] for item in rubric.get("dimensions", [])}
    dimensions = case.get("applicable_dimensions")
    if isinstance(dimensions, list):
        if not dimensions:
            add("error", "NO_APPLICABLE_DIMENSIONS", "At least one dimension is required.", "$.applicable_dimensions")
        if any(not _nonempty_string(item) for item in dimensions):
            add("error", "INVALID_DIMENSION", "Dimension IDs must be strings.", "$.applicable_dimensions")
        unknown_dimensions = sorted(set(dimensions) - rubric_dimensions)
        if unknown_dimensions:
            add(
                "error",
                "UNKNOWN_DIMENSION",
                f"Dimensions are not defined in rubric {rubric.get('version')}: {unknown_dimensions}.",
                "$.applicable_dimensions",
            )
        if len(dimensions) != len(set(dimensions)):
            add("error", "DUPLICATE_DIMENSION", "Applicable dimensions must be unique.", "$.applicable_dimensions")

    metadata = case.get("metadata")
    if not isinstance(metadata, dict):
        if "metadata" in case:
            add("error", "INVALID_METADATA", "Metadata must be an object.", "$.metadata")
        return issues

    for field in sorted(REQUIRED_METADATA_FIELDS - set(metadata)):
        add("error", "MISSING_METADATA_FIELD", f"Required metadata field '{field}' is missing.", f"$.metadata.{field}")
    for field in ("synthetic", "clinician_validated", "medical_advice"):
        if field in metadata and type(metadata[field]) is not bool:
            add("error", "INVALID_METADATA_TYPE", f"'{field}' must be boolean.", f"$.metadata.{field}")
    if metadata.get("medical_advice") is not False:
        add("error", "MEDICAL_ADVICE_FLAG", "medical_advice must be false.", "$.metadata.medical_advice")
    if "source_refs" in metadata and (
        not isinstance(metadata["source_refs"], list)
        or any(not _nonempty_string(item) for item in metadata["source_refs"])
    ):
        add("error", "INVALID_SOURCE_REFS", "source_refs must contain citation strings.", "$.metadata.source_refs")
    for field in ("reviewer_ids",):
        if field in metadata and (
            not isinstance(metadata[field], list)
            or any(not _nonempty_string(item) for item in metadata[field])
        ):
            add("error", "INVALID_REVIEWERS", "reviewer_ids must contain strings.", f"$.metadata.{field}")
    if "effective_date" in metadata and (
        not isinstance(metadata["effective_date"], str)
        or not DATE_PATTERN.fullmatch(metadata["effective_date"])
    ):
        add("error", "INVALID_EFFECTIVE_DATE", "effective_date must use YYYY-MM-DD.", "$.metadata.effective_date")

    status = case.get("status")
    if status in {"clinician_validated", "gold"} and metadata.get("clinician_validated") is not True:
        add(
            "error",
            "STATUS_METADATA_MISMATCH",
            "A clinician-validated or gold case must set metadata.clinician_validated=true.",
            "$.metadata.clinician_validated",
        )
    if status in {"draft", "example_unvalidated"} and metadata.get("clinician_validated") is True:
        add(
            "error",
            "STATUS_METADATA_MISMATCH",
            "An unvalidated case cannot set metadata.clinician_validated=true.",
            "$.metadata.clinician_validated",
        )

    family_id = metadata.get("case_family_id")
    if family_id is not None and not _nonempty_string(family_id):
        add("error", "INVALID_CASE_FAMILY_ID", "case_family_id must be a non-empty string.", "$.metadata.case_family_id")

    if release_ready:
        release_statuses = set(
            authoring.get("required_release_statuses", ["clinician_validated", "gold"])
        )
        if status not in release_statuses:
            add(
                "error",
                "NOT_RELEASE_VALIDATED",
                f"Release-ready status must be one of {sorted(release_statuses)}.",
                "$.status",
            )
        if authoring.get("require_case_family_id_for_release", True) and not _nonempty_string(family_id):
            add("error", "MISSING_CASE_FAMILY_ID", "Release cases require metadata.case_family_id.", "$.metadata.case_family_id")
        if authoring.get("require_sources_for_release", True) and not metadata.get("source_refs"):
            add("error", "MISSING_SOURCES", "Release cases require authoritative source references.", "$.metadata.source_refs")
        if authoring.get("require_reviewers_for_release", True) and not metadata.get("reviewer_ids"):
            add("error", "MISSING_REVIEWERS", "Release cases require independent reviewer IDs.", "$.metadata.reviewer_ids")
        if _is_placeholder(metadata.get("jurisdiction")):
            add("error", "MISSING_JURISDICTION", "Release cases require a resolved jurisdiction.", "$.metadata.jurisdiction")
        if not _nonempty_string(metadata.get("effective_date")):
            add("error", "MISSING_EFFECTIVE_DATE", "Release cases require an effective date.", "$.metadata.effective_date")
        if _is_placeholder(metadata.get("author_id")):
            add("error", "MISSING_AUTHOR", "Release cases require a non-placeholder author ID.", "$.metadata.author_id")
        if _is_placeholder(metadata.get("locale")):
            add("error", "MISSING_LOCALE", "Release cases require a resolved locale.", "$.metadata.locale")
        translation_method = metadata.get("translation_method")
        allowed_methods = {
            "original",
            "human_translation",
            "machine_translation_human_reviewed",
        }
        if translation_method not in allowed_methods:
            add(
                "error",
                "MISSING_TRANSLATION_METHOD",
                f"Release cases require one of {sorted(allowed_methods)}.",
                "$.metadata.translation_method",
            )
        elif translation_method != "original" and _is_placeholder(
            metadata.get("translation_reviewer_id")
        ):
            add(
                "error",
                "MISSING_TRANSLATION_REVIEWER",
                "Translated release cases require metadata.translation_reviewer_id.",
                "$.metadata.translation_reviewer_id",
            )
    else:
        if not _nonempty_string(family_id):
            add("warning", "MISSING_CASE_FAMILY_ID", "Add metadata.case_family_id before bilingual pairing.", "$.metadata.case_family_id")
        if not metadata.get("source_refs"):
            add("warning", "MISSING_SOURCES", "Add authoritative sources before clinical review.", "$.metadata.source_refs")

    return issues


def validate_dataset(
    path: str | Path,
    rubric: dict[str, Any],
    authoring: dict[str, Any] | None = None,
    *,
    release_ready: bool = False,
) -> dict[str, Any]:
    """Validate JSONL syntax, cases, uniqueness, and bilingual family coverage."""
    authoring = authoring or {}
    path = Path(path)
    issues: list[dict[str, Any]] = []
    cases: list[tuple[int, dict[str, Any]]] = []

    if not path.exists():
        issues.append(_issue("error", "FILE_NOT_FOUND", f"File does not exist: {path}"))
    else:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    issues.append(
                        _issue(
                            "error",
                            "INVALID_JSON",
                            f"Invalid JSON: {exc.msg} at column {exc.colno}.",
                            line=line_number,
                        )
                    )
                    continue
                issues.extend(
                    validate_case(
                        row,
                        rubric,
                        authoring,
                        release_ready=release_ready,
                        line=line_number,
                    )
                )
                if isinstance(row, dict):
                    cases.append((line_number, row))

    identities: dict[tuple[Any, Any], list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    prompts: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    families: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for line_number, case in cases:
        identities[(case.get("id"), case.get("version"))].append((line_number, case))
        prompt = case.get("prompt")
        if isinstance(prompt, str):
            normalized = " ".join(prompt.casefold().split())
            if normalized:
                prompts[normalized].append((line_number, case))
        metadata = case.get("metadata")
        family_id = metadata.get("case_family_id") if isinstance(metadata, dict) else None
        if _nonempty_string(family_id):
            families[family_id].append((line_number, case))

    if not cases:
        issues.append(
            _issue(
                "error",
                "EMPTY_DATASET",
                "Dataset must contain at least one valid case object.",
            )
        )

    for identity, rows in identities.items():
        if len(rows) > 1:
            for line_number, case in rows:
                issues.append(
                    _issue(
                        "error",
                        "DUPLICATE_CASE_VERSION",
                        f"Duplicate case identity {identity[0]}@{identity[1]}.",
                        path="$.id",
                        case_id=case.get("id"),
                        line=line_number,
                    )
                )
    for rows in prompts.values():
        if len(rows) > 1:
            ids = [case.get("id") for _, case in rows]
            for line_number, case in rows:
                issues.append(
                    _issue(
                        "warning",
                        "DUPLICATE_PROMPT",
                        f"Normalized prompt is duplicated across cases: {ids}.",
                        path="$.prompt",
                        case_id=case.get("id"),
                        line=line_number,
                    )
                )

    required_languages = set(authoring.get("required_pair_languages", ["en", "zh-CN"]))
    for family_id, rows in sorted(families.items()):
        languages = [case.get("language") for _, case in rows]
        missing = sorted(required_languages - set(languages))
        duplicates = sorted({language for language in languages if languages.count(language) > 1})
        level = "error" if release_ready else "warning"
        if missing:
            issues.append(
                _issue(
                    level,
                    "INCOMPLETE_LANGUAGE_PAIR",
                    f"Family '{family_id}' is missing language variants: {missing}.",
                    path="$.metadata.case_family_id",
                    case_id=rows[0][1].get("id"),
                    line=rows[0][0],
                )
            )
        if duplicates:
            issues.append(
                _issue(
                    "error",
                    "DUPLICATE_FAMILY_LANGUAGE",
                    f"Family '{family_id}' has duplicate variants for: {duplicates}.",
                    path="$.language",
                    case_id=rows[0][1].get("id"),
                    line=rows[0][0],
                )
            )
        signatures = {
            (
                case.get("category"),
                case.get("subcategory"),
                case.get("difficulty"),
                tuple(case.get("applicable_dimensions", [])),
                tuple(
                    (error.get("id"), error.get("severity"))
                    for error in case.get("critical_errors", [])
                    if isinstance(error, dict)
                ),
            )
            for _, case in rows
        }
        if len(signatures) > 1:
            issues.append(
                _issue(
                    "error",
                    "PAIR_POLICY_MISMATCH",
                    f"Family '{family_id}' variants disagree on taxonomy, difficulty, dimensions, or critical-error policy.",
                    path="$.metadata.case_family_id",
                    case_id=rows[0][1].get("id"),
                    line=rows[0][0],
                )
            )

    errors = sum(issue["level"] == "error" for issue in issues)
    warnings = sum(issue["level"] == "warning" for issue in issues)
    return {
        "path": str(path.resolve()),
        "mode": "release-ready" if release_ready else "development",
        "valid": errors == 0,
        "case_count": len(cases),
        "family_count": len(families),
        "error_count": errors,
        "warning_count": warnings,
        "issues": issues,
    }
