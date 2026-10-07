from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_jsonl


REVIEW_SCHEMA_VERSION = "0.2.0"
REVIEW_TYPES = {"clinical", "language_equivalence", "methodology", "adjudication"}
DECISIONS = {"approve", "approve_with_changes", "revise", "reject", "needs_specialist"}
ROLES = {
    "clinician",
    "pharmacist",
    "language_reviewer",
    "domain_expert",
    "adjudicator",
    "other",
}
ROLE_POLICY = {
    "clinical": {"clinician", "pharmacist", "domain_expert"},
    "language_equivalence": {"language_reviewer", "domain_expert"},
    "methodology": {"domain_expert", "adjudicator"},
    "adjudication": {"adjudicator"},
}
CHECK_FIELDS = {
    "prompt_valid",
    "reference_valid",
    "requirements_observable",
    "critical_errors_valid",
    "sources_sufficient",
    "scope_appropriate",
    "language_equivalent",
}
REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "case_id",
    "case_version",
    "case_content_hash",
    "reviewer",
    "review_type",
    "decision",
    "checks",
    "required_changes",
    "notes",
    "created_at",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | {"supersedes_review_id"}
CASE_ID_PATTERN = re.compile(r"^[A-Z0-9_-]+$")
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
HASH_EXCLUDED_METADATA_FIELDS = {
    "clinician_validated",
    "reviewer_ids",
    "translation_method",
    "translation_reviewer_id",
    "change_rationale",
}


def case_content_hash(case: dict[str, Any]) -> str:
    """Return a SHA-256 identity of reviewable content, excluding promotion state."""
    payload = dict(case)
    payload.pop("status", None)
    metadata = dict(payload.get("metadata", {}))
    for field in HASH_EXCLUDED_METADATA_FIELDS:
        metadata.pop(field, None)
    payload["metadata"] = metadata
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _issue(
    level: str,
    code: str,
    message: str,
    *,
    source: str,
    review_id: str | None = None,
    path: str = "$",
) -> dict[str, Any]:
    issue = {
        "level": level,
        "code": code,
        "message": message,
        "source": source,
        "path": path,
    }
    if review_id:
        issue["review_id"] = review_id
    return issue


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _read_review_records(path: str | Path) -> tuple[list[tuple[str, dict[str, Any]]], list[dict[str, Any]]]:
    target = Path(path)
    records: list[tuple[str, dict[str, Any]]] = []
    issues: list[dict[str, Any]] = []
    if not target.exists():
        return records, [
            _issue(
                "error",
                "REVIEW_PATH_NOT_FOUND",
                f"Review path does not exist: {target}",
                source=str(target),
            )
        ]

    files = [target] if target.is_file() else sorted(
        item for item in target.rglob("*") if item.suffix in {".json", ".jsonl"}
    )
    for file_path in files:
        try:
            if file_path.suffix == ".jsonl":
                rows = []
                with file_path.open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, 1):
                        if not line.strip():
                            continue
                        try:
                            rows.append((line_number, json.loads(line)))
                        except json.JSONDecodeError as exc:
                            issues.append(
                                _issue(
                                    "error",
                                    "INVALID_REVIEW_JSON",
                                    f"Invalid JSON at line {line_number}: {exc.msg}.",
                                    source=str(file_path),
                                )
                            )
                for line_number, row in rows:
                    if isinstance(row, dict):
                        records.append((f"{file_path}:{line_number}", row))
                    else:
                        issues.append(
                            _issue(
                                "error",
                                "REVIEW_NOT_OBJECT",
                                f"Review at line {line_number} must be an object.",
                                source=str(file_path),
                            )
                        )
            else:
                row = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(row, dict):
                    records.append((str(file_path), row))
                else:
                    issues.append(
                        _issue(
                            "error",
                            "REVIEW_NOT_OBJECT",
                            "Review JSON must contain one object.",
                            source=str(file_path),
                        )
                    )
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "error",
                    "INVALID_REVIEW_JSON",
                    f"Invalid JSON: {exc.msg}.",
                    source=str(file_path),
                )
            )
    return records, issues


def _validate_record(
    review: dict[str, Any],
    source: str,
    cases: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    review_id = review.get("id") if isinstance(review.get("id"), str) else None

    def add(level: str, code: str, message: str, path: str = "$") -> None:
        issues.append(
            _issue(
                level,
                code,
                message,
                source=source,
                review_id=review_id,
                path=path,
            )
        )

    for field in sorted(REQUIRED_FIELDS - set(review)):
        add("error", "MISSING_REVIEW_FIELD", f"Required field '{field}' is missing.", f"$.{field}")
    for field in sorted(set(review) - ALLOWED_FIELDS):
        add("error", "UNKNOWN_REVIEW_FIELD", f"Unknown field '{field}'.", f"$.{field}")

    for field in ("id", "case_id", "case_version", "case_content_hash", "notes"):
        if field in review and not isinstance(review[field], str):
            add("error", "INVALID_REVIEW_FIELD", f"'{field}' must be a string.", f"$.{field}")
    if not isinstance(review.get("id"), str) or not review["id"].strip():
        add("error", "INVALID_REVIEW_ID", "id must be a non-empty string.", "$.id")
    if not isinstance(review.get("case_id"), str) or not CASE_ID_PATTERN.fullmatch(review["case_id"]):
        add("error", "INVALID_CASE_ID", "case_id must match ^[A-Z0-9_-]+$.", "$.case_id")
    if not isinstance(review.get("case_version"), str) or not SEMVER_PATTERN.fullmatch(review["case_version"]):
        add("error", "INVALID_CASE_VERSION", "case_version must use X.Y.Z semantic versioning.", "$.case_version")
    supersedes = review.get("supersedes_review_id")
    if supersedes is not None and (not isinstance(supersedes, str) or not supersedes.strip()):
        add("error", "INVALID_SUPERSESSION_ID", "supersedes_review_id must be a non-empty string.", "$.supersedes_review_id")
    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        add(
            "error",
            "UNSUPPORTED_REVIEW_SCHEMA",
            f"schema_version must be '{REVIEW_SCHEMA_VERSION}'.",
            "$.schema_version",
        )
    digest = review.get("case_content_hash")
    if not isinstance(digest, str) or len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        add("error", "INVALID_CASE_HASH", "case_content_hash must be a lowercase SHA-256 hex digest.", "$.case_content_hash")

    review_type = review.get("review_type")
    if review_type not in REVIEW_TYPES:
        add("error", "INVALID_REVIEW_TYPE", f"review_type must be one of {sorted(REVIEW_TYPES)}.", "$.review_type")
    decision = review.get("decision")
    if decision not in DECISIONS:
        add("error", "INVALID_REVIEW_DECISION", f"decision must be one of {sorted(DECISIONS)}.", "$.decision")

    reviewer = review.get("reviewer")
    reviewer_id = None
    role = None
    if not isinstance(reviewer, dict):
        add("error", "INVALID_REVIEWER", "reviewer must be an object.", "$.reviewer")
    else:
        expected = {
            "pseudonymous_id",
            "role",
            "qualification_scope",
            "jurisdiction_scope",
            "conflict_disclosed",
        }
        for field in sorted(expected - set(reviewer)):
            add("error", "MISSING_REVIEWER_FIELD", f"Reviewer field '{field}' is required.", f"$.reviewer.{field}")
        for field in sorted(set(reviewer) - expected):
            add("error", "UNKNOWN_REVIEWER_FIELD", f"Unknown reviewer field '{field}'.", f"$.reviewer.{field}")
        reviewer_id = reviewer.get("pseudonymous_id")
        role = reviewer.get("role")
        for field in ("pseudonymous_id", "qualification_scope", "jurisdiction_scope"):
            if not isinstance(reviewer.get(field), str) or not reviewer[field].strip():
                add("error", "INVALID_REVIEWER_FIELD", f"Reviewer field '{field}' must be non-empty.", f"$.reviewer.{field}")
        if role not in ROLES:
            add("error", "INVALID_REVIEWER_ROLE", f"role must be one of {sorted(ROLES)}.", "$.reviewer.role")
        if type(reviewer.get("conflict_disclosed")) is not bool:
            add("error", "INVALID_CONFLICT_DISCLOSURE", "conflict_disclosed must be boolean.", "$.reviewer.conflict_disclosed")
        if review_type in ROLE_POLICY and role not in ROLE_POLICY[review_type]:
            add(
                "error",
                "REVIEWER_ROLE_MISMATCH",
                f"Role '{role}' is not permitted for {review_type} review.",
                "$.reviewer.role",
            )

    checks = review.get("checks")
    if not isinstance(checks, dict):
        add("error", "INVALID_REVIEW_CHECKS", "checks must be an object.", "$.checks")
        checks = {}
    else:
        for field in sorted(CHECK_FIELDS - set(checks)):
            add("error", "MISSING_REVIEW_CHECK", f"Check '{field}' is required.", f"$.checks.{field}")
        for field in sorted(set(checks) - CHECK_FIELDS):
            add("error", "UNKNOWN_REVIEW_CHECK", f"Unknown check '{field}'.", f"$.checks.{field}")
        for field in CHECK_FIELDS - {"language_equivalent"}:
            if field in checks and type(checks[field]) is not bool:
                add("error", "INVALID_REVIEW_CHECK", f"Check '{field}' must be boolean.", f"$.checks.{field}")
        if "language_equivalent" in checks and checks["language_equivalent"] is not None and type(checks["language_equivalent"]) is not bool:
            add("error", "INVALID_REVIEW_CHECK", "language_equivalent must be boolean or null.", "$.checks.language_equivalent")

    changes = review.get("required_changes")
    if not isinstance(changes, list) or any(not isinstance(item, str) or not item.strip() for item in changes):
        add("error", "INVALID_REQUIRED_CHANGES", "required_changes must contain non-empty strings.", "$.required_changes")
        changes = []

    if _parse_timestamp(review.get("created_at")) is None:
        add("error", "INVALID_REVIEW_TIMESTAMP", "created_at must be an ISO-8601 timestamp with timezone.", "$.created_at")

    identity = (review.get("case_id"), review.get("case_version"))
    case = cases.get(identity)
    if case is None:
        add("error", "REVIEW_CASE_NOT_FOUND", f"No case matches {identity[0]}@{identity[1]}.", "$.case_id")
    else:
        expected_hash = case_content_hash(case)
        if digest != expected_hash:
            add("error", "STALE_CASE_REVIEW", "case_content_hash does not match the current case content.", "$.case_content_hash")
        author_id = case.get("metadata", {}).get("author_id")
        if reviewer_id and author_id and reviewer_id == author_id:
            add("error", "SELF_REVIEW", "The case author cannot independently approve the same case.", "$.reviewer.pseudonymous_id")
        if review_type == "language_equivalence" and case.get("metadata", {}).get("translation_method") == "original":
            add("warning", "LANGUAGE_REVIEW_ON_ORIGINAL", "Language-equivalence review normally targets the translated variant.", "$.review_type")

    required_true = {
        "clinical": {
            "prompt_valid",
            "reference_valid",
            "requirements_observable",
            "critical_errors_valid",
            "sources_sufficient",
            "scope_appropriate",
        },
        "language_equivalence": {"language_equivalent", "scope_appropriate"},
        "methodology": {"requirements_observable", "critical_errors_valid", "scope_appropriate"},
        "adjudication": {"scope_appropriate"},
    }
    if decision == "approve":
        failed = sorted(field for field in required_true.get(review_type, set()) if checks.get(field) is not True)
        if failed:
            add("error", "APPROVAL_CHECKS_FAILED", f"An approval requires true checks: {failed}.", "$.checks")
        if changes:
            add("error", "APPROVAL_HAS_REQUIRED_CHANGES", "An approval cannot retain required changes.", "$.required_changes")
    if decision == "approve_with_changes" and not changes:
        add("error", "CHANGES_NOT_LISTED", "approve_with_changes requires at least one requested change.", "$.required_changes")
    if decision in {"revise", "reject", "needs_specialist"} and not changes and not str(review.get("notes", "")).strip():
        add("error", "REVIEW_RATIONALE_MISSING", "A non-approval requires notes or requested changes.", "$.notes")

    return issues


def assess_reviews(
    cases_path: str | Path,
    reviews_path: str | Path,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate append-only reviews and calculate current review-gate status."""
    policy = policy or {}
    cases = load_jsonl(cases_path)
    cases_by_identity = {(case["id"], case["version"]): case for case in cases}
    sourced_records, issues = _read_review_records(reviews_path)
    for source, review in sourced_records:
        issues.extend(_validate_record(review, source, cases_by_identity))

    id_sources: dict[str, list[str]] = {}
    for source, review in sourced_records:
        review_id = review.get("id")
        if isinstance(review_id, str):
            id_sources.setdefault(review_id, []).append(source)
    for review_id, sources in id_sources.items():
        if len(sources) > 1:
            for source in sources:
                issues.append(
                    _issue(
                        "error",
                        "DUPLICATE_REVIEW_ID",
                        f"Review ID '{review_id}' appears more than once.",
                        source=source,
                        review_id=review_id,
                        path="$.id",
                    )
                )

    known_ids = set(id_sources)
    reviews_by_id = {
        review["id"]: review
        for _, review in sourced_records
        if isinstance(review.get("id"), str) and review["id"]
    }
    for source, review in sourced_records:
        supersedes = review.get("supersedes_review_id")
        if supersedes is not None and supersedes not in known_ids:
            issues.append(
                _issue(
                    "error",
                    "SUPERSEDED_REVIEW_NOT_FOUND",
                    f"supersedes_review_id '{supersedes}' was not found.",
                    source=source,
                    review_id=review.get("id"),
                    path="$.supersedes_review_id",
                )
            )
        elif supersedes is not None:
            prior = reviews_by_id[supersedes]
            current_reviewer = (review.get("reviewer") or {}).get("pseudonymous_id")
            prior_reviewer = (prior.get("reviewer") or {}).get("pseudonymous_id")
            current_scope = (
                review.get("case_id"),
                review.get("case_version"),
                review.get("review_type"),
                current_reviewer,
            )
            prior_scope = (
                prior.get("case_id"),
                prior.get("case_version"),
                prior.get("review_type"),
                prior_reviewer,
            )
            if current_scope != prior_scope:
                issues.append(
                    _issue(
                        "error",
                        "INVALID_SUPERSESSION_SCOPE",
                        "A review may supersede only the same case version, review type, and reviewer.",
                        source=source,
                        review_id=review.get("id"),
                        path="$.supersedes_review_id",
                    )
                )
            current_time = _parse_timestamp(review.get("created_at"))
            prior_time = _parse_timestamp(prior.get("created_at"))
            if current_time is not None and prior_time is not None and current_time <= prior_time:
                issues.append(
                    _issue(
                        "error",
                        "INVALID_SUPERSESSION_TIME",
                        "A superseding review must be created after the prior review.",
                        source=source,
                        review_id=review.get("id"),
                        path="$.created_at",
                    )
                )

    invalid_ids = {
        issue.get("review_id")
        for issue in issues
        if issue["level"] == "error" and issue.get("review_id")
    }
    latest: dict[tuple[str, str, str, str], tuple[datetime, dict[str, Any]]] = {}
    for _, review in sourced_records:
        review_id = review.get("id")
        if not isinstance(review_id, str) or not review_id:
            continue
        timestamp = _parse_timestamp(review.get("created_at"))
        reviewer_id = (review.get("reviewer") or {}).get("pseudonymous_id")
        key = (
            str(review.get("case_id")),
            str(review.get("case_version")),
            str(review.get("review_type")),
            str(reviewer_id),
        )
        if review_id in invalid_ids or timestamp is None:
            continue
        if key not in latest or timestamp > latest[key][0]:
            latest[key] = (timestamp, review)

    approvals: dict[tuple[str, str], dict[str, set[str]]] = {}
    for _, review in latest.values():
        if review.get("decision") != "approve":
            continue
        identity = (str(review.get("case_id")), str(review.get("case_version")))
        reviewer_id = str((review.get("reviewer") or {}).get("pseudonymous_id"))
        approvals.setdefault(identity, {}).setdefault(str(review.get("review_type")), set()).add(reviewer_id)

    clinical_required = max(1, int(policy.get("required_clinical_approvals", 1)))
    language_required = max(1, int(policy.get("required_language_approvals", 1)))
    case_status: list[dict[str, Any]] = []
    clinical_pending: list[str] = []
    language_pending: list[str] = []
    promotion_eligible: list[str] = []
    for case in cases:
        identity = (case["id"], case["version"])
        by_type = approvals.get(identity, {})
        clinical_count = len(by_type.get("clinical", set()))
        needs_language = case.get("metadata", {}).get("translation_method") != "original"
        language_count = len(by_type.get("language_equivalence", set()))
        clinical_complete = clinical_count >= clinical_required
        language_complete = not needs_language or language_count >= language_required
        if not clinical_complete:
            clinical_pending.append(case["id"])
        if not language_complete:
            language_pending.append(case["id"])
        if clinical_complete and language_complete:
            promotion_eligible.append(case["id"])
        case_status.append(
            {
                "case_id": case["id"],
                "case_version": case["version"],
                "clinical_approvals": clinical_count,
                "clinical_complete": clinical_complete,
                "language_review_required": needs_language,
                "language_approvals": language_count,
                "language_complete": language_complete,
                "review_gates_complete": clinical_complete and language_complete,
            }
        )

    errors = sum(issue["level"] == "error" for issue in issues)
    warnings = sum(issue["level"] == "warning" for issue in issues)
    return {
        "cases_path": str(Path(cases_path).resolve()),
        "reviews_path": str(Path(reviews_path).resolve()),
        "review_record_count": len(sourced_records),
        "decision_counts": dict(sorted(Counter(review.get("decision", "missing") for _, review in sourced_records).items())),
        "valid": errors == 0,
        "error_count": errors,
        "warning_count": warnings,
        "issues": issues,
        "review_queue": {
            "clinical_review_pending": sorted(clinical_pending),
            "language_review_pending": sorted(language_pending),
            "review_gates_complete": sorted(promotion_eligible),
        },
        "case_status": case_status,
    }


def build_review_template(
    case: dict[str, Any],
    *,
    review_type: str,
    reviewer_id: str,
    role: str,
    qualification_scope: str,
    jurisdiction_scope: str,
) -> dict[str, Any]:
    """Build a prefilled, non-approved review record for one exact case revision."""
    if review_type not in REVIEW_TYPES:
        raise ValueError(f"Unsupported review type: {review_type}")
    if role not in ROLES:
        raise ValueError(f"Unsupported reviewer role: {role}")
    if role not in ROLE_POLICY[review_type]:
        raise ValueError(f"Role '{role}' is not permitted for {review_type} review")
    if reviewer_id == case.get("metadata", {}).get("author_id"):
        raise ValueError("The case author cannot be assigned as its independent reviewer")
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "id": f"review_{case['id'].lower()}_{review_type}_{stamp}",
        "case_id": case["id"],
        "case_version": case["version"],
        "case_content_hash": case_content_hash(case),
        "reviewer": {
            "pseudonymous_id": reviewer_id,
            "role": role,
            "qualification_scope": qualification_scope,
            "jurisdiction_scope": jurisdiction_scope,
            "conflict_disclosed": False,
        },
        "review_type": review_type,
        "decision": "revise",
        "checks": {
            "prompt_valid": False,
            "reference_valid": False,
            "requirements_observable": False,
            "critical_errors_valid": False,
            "sources_sufficient": False,
            "scope_appropriate": False,
            "language_equivalent": None,
        },
        "required_changes": [],
        "notes": "Complete this review; the generated record is not an approval.",
        "created_at": now.isoformat().replace("+00:00", "Z"),
    }
