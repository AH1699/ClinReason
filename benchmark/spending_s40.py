"""Owner-selected first-phase stop threshold, exercised only offline in S40.

One request at a time. Accounting occurs AFTER a request; $55 is not a hard
ceiling or a provider invoice. Unknown charges and local failures stop the run.
"""

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import threading

from . import run_guard_s37 as guard, transport_s39 as capture, usage_s39 as usage, workflow_s38 as workflow
from .config import load_json
from .provenance import sha256_json

POLICY = "config/spending_s40_v1.json"
FREEZE = "config/spending_s40_frozen_v1.json"
TICKS_PER_USD = 10_000_000_000
TICKS_PER_MICROUSD = 10_000


def policy(root):
    value = load_json(root / POLICY)
    expected = {"phase": "first", "threshold_usd": "55.00", "threshold_usd_ticks": 55*TICKS_PER_USD,
        "usd_ticks_per_dollar": TICKS_PER_USD, "usd_ticks_per_microusd": TICKS_PER_MICROUSD,
        "max_attempts": 816, "max_in_flight": 1, "automatic_retries": 0, "resume_allowed": False,
        "live_call_allowance": 0, "overshoot_accepted": True, "hard_ceiling": False,
        "confirmation_policy_selected": False, "confirmation_threshold_usd": None,
        "confirmation_live_call_allowance": 0}
    if any(value.get(k) != v or type(value.get(k)) is not type(v) for k, v in expected.items()):
        raise ValueError("Unapproved spending-policy change")
    return value


def run_live(*args, **kwargs):
    raise guard.AdmissionBlocked("Policy choice is not live-run approval; S40 has no enabled production dispatcher")


def monitoring_delta(accounting, provider):
    """Return safe numeric fields only; unknown or malformed input never becomes 0."""
    unknown = {"source": "unknown", "delta_ticks": None, "reported_ticks": None, "estimate_microusd": None}
    if not isinstance(accounting, dict) or accounting.get("prospective_cap_proven") is not False:
        return unknown
    status = accounting.get("status")
    reported, estimate = accounting.get("provider_billed_usd_ticks"), accounting.get("undiscounted_token_estimate_microusd")
    if (provider == "grok" and status == "provider_reported_charge" and type(reported) is int
            and reported >= 0 and estimate is None):
        return {"source": "provider_reported_charge", "delta_ticks": reported,
                "reported_ticks": reported, "estimate_microusd": None}
    if (provider in {"gemini", "minimax"} and status == "token_estimate_only" and type(estimate) is int
            and estimate >= 0 and reported is None):
        return {"source": "token_estimate_only", "delta_ticks": estimate*TICKS_PER_MICROUSD,
                "reported_ticks": None, "estimate_microusd": estimate}
    return unknown


class StopThreshold:
    """Durable, exact-prefix admission/settlement ledger with one in-flight slot.

    Directory reuse and resume are prohibited. An interrupted attempt remains
    outstanding/unknown. This ledger alone cannot authorize any network call.
    """
    def __init__(self, root, directory, phase="first"):
        if phase != "first":
            raise guard.AdmissionBlocked("Confirmation budget policy has not been selected")
        self.policy = policy(root)
        self.rows = workflow.schedule(root, phase)
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        self.lock = threading.RLock()
        self.attempts, self.monitored, self.reported, self.estimated, self.unknown = 0, 0, 0, 0, 0
        self.pending = None
        self.stop_reason = None
        self.last_hash = sha256_json(self.policy)
        self.records = []
        guard._write_exclusive(self.directory / "run.json", guard._json_bytes({
            "version": self.policy["version"], "mode": "offline_threshold_rehearsal",
            "policy_sha256": self.last_hash, "schedule_sha256": sha256_json(self.rows),
            "threshold_ticks": self.policy["threshold_usd_ticks"], "max_attempts": len(self.rows),
            "max_in_flight": 1, "automatic_retries": 0, "resume_allowed": False, "live_calls": 0}))

    def can_dispatch(self):
        with self.lock:
            return (self.stop_reason is None and self.pending is None and self.unknown == 0
                    and self.attempts < len(self.rows) and self.monitored < self.policy["threshold_usd_ticks"])

    def begin(self, row, payload):
        with self.lock:
            if not self.can_dispatch():
                raise guard.AdmissionBlocked("Stopped, unsettled attempt, threshold or attempt limit reached")
            if row != self.rows[self.attempts] or not isinstance(payload, dict) or payload.get("model") != row["model"]:
                raise guard.AdmissionBlocked("Request must be the exact next scheduled row")
            body = guard._json_bytes(payload)
            sequence = self.attempts + 1
            record = {"sequence": sequence, "row": deepcopy(row), "policy_sha256": sha256_json(self.policy),
                "previous_record_sha256": self.last_hash, "monitoring_before_ticks": self.monitored,
                "payload_sha256": hashlib.sha256(body).hexdigest(), "prospective_cost_bound_ticks": None,
                "state": "one_attempt_reserved_before_dispatch", "fixture_only": True}
            self.stop_reason = "journal_write_failure"  # Fail closed even if persistence fails.
            self.pending = deepcopy(record)
            self.attempts = sequence
            guard._write_exclusive(self.directory / f"{sequence:04d}.admission.json", guard._json_bytes(record))
            guard._write_exclusive(self.directory / f"{sequence:04d}.payload.json", body)
            self.stop_reason = None
            return deepcopy(record)

    def settle(self, accounting, accepted):
        with self.lock:
            if self.pending is None or self.stop_reason is not None:
                raise guard.AdmissionBlocked("No settleable outstanding attempt")
            if type(accepted) is not bool:
                raise ValueError("Acceptance must be explicit boolean")
            delta = monitoring_delta(accounting, self.pending["row"]["provider"])
            after = self.monitored + (delta["delta_ticks"] or 0)
            stop = ("unknown_charge" if delta["delta_ticks"] is None else "technical_failure" if not accepted
                    else "spend_threshold_reached" if after >= self.policy["threshold_usd_ticks"] else None)
            record = {"sequence": self.pending["sequence"], "admission_sha256": sha256_json(self.pending),
                **delta, "monitoring_after_ticks": after, "capture_accepted": accepted, "stop_reason": stop,
                "threshold_reached": after >= self.policy["threshold_usd_ticks"], "hard_ceiling": False}
            self.stop_reason = "journal_write_failure"
            guard._write_exclusive(self.directory / f'{self.pending["sequence"]:04d}.settlement.json', guard._json_bytes(record))
            self.monitored = after
            self.reported += delta["reported_ticks"] or 0
            self.estimated += delta["estimate_microusd"] or 0
            self.unknown += delta["delta_ticks"] is None
            self.last_hash = sha256_json(record)
            self.records.append(deepcopy(record))
            self.pending = None
            self.stop_reason = stop
            return deepcopy(record)

    def report(self):
        with self.lock:
            return {"mode": "offline_threshold_rehearsal", "live_calls": 0, "attempts": self.attempts,
                "settled_attempts": len(self.records), "outstanding_attempts": int(self.pending is not None),
                "unknown_settled_charges": self.unknown, "stop_reason": self.stop_reason,
                "monitoring_amount_ticks": self.monitored,
                "monitoring_amount_usd": format(Decimal(self.monitored)/TICKS_PER_USD, "f"),
                "provider_reported_subtotal_ticks": self.reported,
                "token_estimate_subtotal_microusd": self.estimated,
                "threshold_ticks": self.policy["threshold_usd_ticks"],
                "monitoring_overrun_ticks": max(0, self.monitored-self.policy["threshold_usd_ticks"]),
                "threshold_reached": self.monitored >= self.policy["threshold_usd_ticks"],
                "invoice_total_usd": None, "hard_ceiling": False, "can_dispatch": self.can_dispatch()}


class ThresholdRehearsal:
    """Integrated S38 + S39 + selected spending policy; supplied fake connections only."""
    def __init__(self, root, directory):
        self.root = root
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        guard._sync_dir(self.directory.parent)
        self.session = workflow.OfflineSession(root, self.directory / "workflow")
        self.capture = capture.CaptureJournal(root, self.directory / "capture", 816)
        self.monitor = StopThreshold(root, self.directory / "spending")
        self.terminal = None
        self.lock = threading.Lock()

    def step(self, *, connection_factory):
        with self.lock:
            if self.terminal:
                return None
            if not self.monitor.can_dispatch():
                self.terminal = self.monitor.stop_reason or "attempt_limit"
                return None
            payload = self.session.next_request()
            if payload is None:
                self.terminal = self.session.stop_reason or "schedule_complete"
                return None
            row = self.session.pending
            context = self.session.contexts[row["sequence"]]
            self.monitor.begin(row, payload)
            result = None
            try:
                def validate(raw):
                    if row["kind"] == "candidate":
                        return workflow.decode_candidate(raw, row["provider"], row["model"])
                    return workflow.score.decode(raw, row["provider"], row["model"], context["packet"])
                result = self.capture.exchange(row["provider"], payload, validate, connection_factory=connection_factory)
                if result["accepted"]:
                    raw_path = self.capture.directory / f'{row["sequence"]:04d}.raw.bin'
                    mirrored = self.session.accept_reply(raw_path.read_bytes())
                    accepted = mirrored["accepted"]
                else:
                    self.session.accept_reply(RuntimeError("capture_failure"))
                    accepted = False
                settled = self.monitor.settle(result["accounting"], accepted)
                if not accepted:
                    self.terminal = result["category"] if not result["accepted"] else "workflow_validation_failure"
                elif settled["stop_reason"]:
                    self.terminal = settled["stop_reason"]
                elif self.session.index == len(self.session.rows):
                    self.terminal = "schedule_complete"
                return {"accepted": accepted, "sequence": row["sequence"], "terminal": self.terminal,
                        "settlement": settled}
            except BaseException:
                self.terminal = "local_failure_or_interruption"
                if self.monitor.pending is not None and self.monitor.stop_reason is None:
                    # If capture wrote valid accounting before an interruption, retain it.
                    account_path = self.capture.directory / f'{row["sequence"]:04d}.accounting.json'
                    accounting = usage.account(None, {"model": row["model"]})
                    if account_path.exists():
                        try:
                            accounting = load_json(account_path)
                        except (ValueError, OSError):
                            pass
                    self.monitor.settle(accounting, False)
                raise

    def report(self):
        return {"mode": "offline_threshold_rehearsal_not_model_results", "live_calls": 0,
            "terminal": self.terminal, "spending": self.monitor.report(), "workflow": self.session.report(),
            "capture_accounting": usage.summarize(self.capture.accounts)}


def approval_scope(root):
    """Preparation record only. No approval, no credential lookup, no data export."""
    plan, rows = workflow.design(root), workflow.schedule(root)
    return {"version": "s40-first-phase-scope-v1", "status": "preparation_not_live_authorized",
        "budget_policy_selected": True, "data_export_approved": False, "paid_calls_approved": False,
        "phase": "first", "maximum_attempts": 816, "candidate_attempts": 216, "judge_attempts": 600,
        "automatic_retries": 0, "max_in_flight": 1, "stop_threshold_usd": "55.00", "hard_ceiling": False,
        "candidate_models": plan["candidates"], "judges": plan["judges"],
        "family_ids": sorted({r["family_id"] for r in rows}), "languages": plan["languages"],
        "candidate_data": "Public synthetic case turns and that candidate's visible prior answer; no labels or future turn",
        "judge_data": "Stage-isolated prompts, visible answers, scoring instructions and criterion/error labels; no model identity",
        "excluded": ["Confirmation-only cases", "Xi'an encounter", "Purchased source files", "Local secrets"],
        "schedule_sha256": sha256_json(rows), "policy_sha256": sha256_json(policy(root)),
        "confirmation_authorized": False, "live_call_allowance": 0}


def snapshot(root):
    paths = [POLICY, capture.FREEZE, "benchmark/spending_s40.py", "tests/test_spending_s40.py"]
    return {"version": "s40-stop-threshold-rehearsal-v1", "live_call_allowance": 0,
        "files": {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
        "approval_scope_sha256": sha256_json(approval_scope(root))}


def audit(root):
    capture.audit(root)
    if snapshot(root) != load_json(root / FREEZE):
        raise ValueError("S40 spending snapshot changed")
    if approval_scope(root) != load_json(root / "config/first_phase_s40_scope_v1.json"):
        raise ValueError("S40 preparation scope changed")
    return {"version": "s40-stop-threshold-rehearsal-v1", "live_calls": 0, "new_cases": 0,
        "new_model_scores": 0, "policy_selected": "first_phase_55_usd_soft_stop_threshold",
        "hard_ceiling": False, "overshoot_accepted": True, "confirmation_policy_selected": False,
        "live_authorized": False, "snapshot_sha256": sha256_json(snapshot(root))}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), indent=2))
