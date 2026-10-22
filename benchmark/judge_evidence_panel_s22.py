"""Separately authorized S22 run around the frozen S21 exact-packet implementation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import load_json
from . import judge_evidence_panel_s21 as base
from .provenance import sha256_json, sha256_text


POLICY_PATH = "config/judge_evidence_panel_s22_v1.json"


def _sha256_file(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def plan(root: Path) -> dict[str, Any]:
    policy = load_json(root / POLICY_PATH)
    if (policy.get("version") != "s22-v1-prospective-operational-replacement"
        or policy.get("status") != "development_only_new_run_not_s21_resume_or_clinical_calibration"
        or policy.get("new_first_judge_calls") != 24
        or policy.get("new_partial_repeat_calls") != 8
        or policy.get("maximum_additional_judge_calls") != 32
        or policy.get("candidate_calls") != 0 or policy.get("automatic_retries") != 0
        or policy.get("prior_attempt", {}).get("attempted_judge_requests") != 1
        or policy.get("prior_attempt", {}).get("provider_receipt_or_billing") != "unknown"):
        raise ValueError("Unknown S22 replacement protocol")
    if (_sha256_file(root / base.POLICY_PATH) != policy["base_s21_policy_file_sha256"]
        or _sha256_file(root / "benchmark/judge_evidence_panel_s21.py") != policy["base_s21_runner_file_sha256"]):
        raise ValueError("Frozen underlying S21 implementation changed")
    frozen = base.plan(root)
    if sha256_json(frozen) != policy["base_s21_plan_sha256"]:
        raise ValueError("Frozen S22 exact packets differ from preregistration")
    connectivity = policy.get("keyless_connectivity_preflight", {})
    if (connectivity.get("method") != "HEAD" or connectivity.get("timeout_seconds") != 10
        or connectivity.get("urls") != ["https://generativelanguage.googleapis.com/", "https://api.x.ai/"]):
        raise ValueError("S22 keyless connectivity preflight changed")
    return {"status": "s22_offline_plan_no_api_calls", "policy_sha256": sha256_json(policy),
            "base_plan_sha256": sha256_json(frozen), "packets": frozen["packet_hashes"],
            "prior_attempt": policy["prior_attempt"], "new_first_judge_calls": 24,
            "new_partial_repeat_calls": 8, "maximum_additional_judge_calls": 32,
            "candidate_calls": 0, "automatic_retries": 0,
            "connectivity": connectivity, "limits": policy["limits"]}


def head_check(url: str, *, timeout: float = 10,
               opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    """Check reachability without keys, case packets or a scored POST."""
    request = Request(url, method="HEAD")
    try:
        with opener(request, timeout=timeout) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code  # 4xx at an API root still proves the host answered.
    except (URLError, TimeoutError, OSError):
        raise ValueError(f"S22 keyless host preflight failed for {url}") from None
    if not isinstance(status, int) or not 100 <= status <= 599:
        raise ValueError(f"S22 keyless host preflight returned no HTTP status for {url}")
    return {"url": url, "method": "HEAD", "http_status": status}


def _preflight(plan_data: dict[str, Any], *, checker: Callable[..., dict[str, Any]] = head_check) -> dict[str, Any]:
    settings = plan_data["connectivity"]
    responses = [checker(url, timeout=settings["timeout_seconds"]) for url in settings["urls"]]
    if ([row.get("url") for row in responses] != settings["urls"]
        or any(row.get("method") != "HEAD" or type(row.get("http_status")) is not int
               for row in responses)):
        raise ValueError("S22 keyless connectivity preflight returned invalid evidence")
    return {"status": "s22_both_hosts_reached_without_keys", "checked_at": datetime.now(timezone.utc).isoformat(),
            "responses": responses}


def _write(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _outer(root: Path, path: Path) -> Path:
    return base._target(root, path)


def _check_outer(root: Path, outer: Path) -> dict[str, Any]:
    frozen = plan(root)
    if load_json(outer / "s22-plan.json") != frozen:
        raise ValueError("S22 outer plan differs from preregistration")
    return frozen


def _check_connectivity_record(path: Path, frozen: dict[str, Any]) -> None:
    record = load_json(path)
    responses = record.get("responses", [])
    if (record.get("status") != "s22_both_hosts_reached_without_keys"
        or not isinstance(record.get("checked_at"), str)
        or [row.get("url") for row in responses] != frozen["connectivity"]["urls"]
        or any(row.get("method") != "HEAD" or type(row.get("http_status")) is not int
               or not 100 <= row["http_status"] <= 599 for row in responses)):
        raise ValueError("S22 keyless connectivity record is missing or invalid")


def run_first(root: Path, outer: Path, *, env_file: Path, max_api_calls: int,
              timeout: float, checker: Callable[..., dict[str, Any]] = head_check) -> dict[str, Any]:
    if max_api_calls != 24 or timeout <= 0:
        raise ValueError("S22 first stage requires exactly 24 permitted judge calls")
    outer = _outer(root, outer)
    frozen = plan(root)
    reached = _preflight(frozen, checker=checker)
    outer.mkdir(parents=True)
    _write(outer / "s22-plan.json", frozen)
    _write(outer / "s22-connectivity-first.json", reached)
    try:
        base.run_first(root, outer / "first", env_file=env_file,
                       max_api_calls=24, timeout=timeout)
        verified = base.audit_first(root, outer / "first")
    except Exception as exc:
        _write(outer / "s22-abort-first.json", {
            "status": "s22_first_aborted_do_not_resume_or_pool",
            "error_type": type(exc).__name__, "provider_receipt_or_billing": "unknown",
            "disposition": "stop_no_retry"})
        raise
    record = {"status": "s22_first_24_cells_saved_and_audited_not_calibration",
              "policy_sha256": frozen["policy_sha256"], "verified": verified}
    _write(outer / "s22-first-complete.json", record)
    return record


def audit_first(root: Path, outer: Path) -> dict[str, Any]:
    frozen = _check_outer(root, outer)
    _check_connectivity_record(outer / "s22-connectivity-first.json", frozen)
    verified = base.audit_first(root, outer / "first")
    record = load_json(outer / "s22-first-complete.json")
    if record != {"status": "s22_first_24_cells_saved_and_audited_not_calibration",
                   "policy_sha256": frozen["policy_sha256"], "verified": verified}:
        raise ValueError("S22 first-stage completion record differs from saved judgments")
    return record


def run_repeat(root: Path, outer: Path, *, env_file: Path, max_api_calls: int,
               timeout: float, checker: Callable[..., dict[str, Any]] = head_check) -> dict[str, Any]:
    if max_api_calls != 8 or timeout <= 0:
        raise ValueError("S22 repeat stage requires exactly 8 permitted judge calls")
    outer = outer.resolve()
    if (not outer.is_relative_to((root / "work").resolve())
        or (outer / "repeat").exists() or (outer / "s22-connectivity-repeat.json").exists()
        or (outer / "s22-abort-first.json").exists()):
        raise ValueError("S22 repeat requires a completed fresh first stage")
    audit_first(root, outer)
    frozen = plan(root)
    reached = _preflight(frozen, checker=checker)
    _write(outer / "s22-connectivity-repeat.json", reached)
    try:
        base.run_repeat(root, outer / "first", outer / "repeat", env_file=env_file,
                        max_api_calls=8, timeout=timeout)
        verified = base.audit(root, outer / "first", outer / "repeat")
    except Exception as exc:
        _write(outer / "s22-abort-repeat.json", {
            "status": "s22_repeat_aborted_do_not_resume_or_pool",
            "error_type": type(exc).__name__, "provider_receipt_or_billing": "unknown",
            "disposition": "stop_no_retry"})
        raise
    record = {"status": "s22_32_new_judge_cells_saved_and_audited_not_calibration",
              "policy_sha256": frozen["policy_sha256"], "verified": verified}
    _write(outer / "s22-complete.json", record)
    return record


def audit(root: Path, outer: Path) -> dict[str, Any]:
    frozen = _check_outer(root, outer)
    audit_first(root, outer)
    _check_connectivity_record(outer / "s22-connectivity-repeat.json", frozen)
    verified = base.audit(root, outer / "first", outer / "repeat")
    record = load_json(outer / "s22-complete.json")
    if record != {"status": "s22_32_new_judge_cells_saved_and_audited_not_calibration",
                   "policy_sha256": frozen["policy_sha256"], "verified": verified}:
        raise ValueError("S22 completion record differs from saved judgments")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S22 independently authorized, bounded judge-only panel")
    parser.add_argument("command", choices=("plan", "run-first", "audit-first", "run-repeat", "audit"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = plan(args.root)
    else:
        if args.output_dir is None:
            parser.error(f"{args.command} requires --output-dir")
        if args.command == "run-first":
            result = run_first(args.root, args.output_dir, env_file=args.env_file,
                               max_api_calls=args.max_api_calls, timeout=args.timeout)
        elif args.command == "audit-first":
            result = audit_first(args.root, args.output_dir)
        elif args.command == "run-repeat":
            result = run_repeat(args.root, args.output_dir, env_file=args.env_file,
                                max_api_calls=args.max_api_calls, timeout=args.timeout)
        else:
            result = audit(args.root, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
