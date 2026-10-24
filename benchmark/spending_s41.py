"""S41 production ledger; S40 policy and arithmetic are reused unchanged."""

from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path
import threading

from . import run_guard_s37 as guard, workflow_s38 as workflow
from .spending_s40 import policy, monitoring_delta, TICKS_PER_USD
from .provenance import sha256_json


class StopThreshold:
    """Durable, exact-prefix admission/settlement ledger with one in-flight slot.

    Directory reuse and resume are prohibited. An interrupted attempt remains
    outstanding/unknown. This ledger alone cannot authorize any network call.
    """
    def __init__(self, root, directory, phase="first", *, mode):
        if mode not in {"live", "offline_fixture"}:
            raise ValueError("Explicit execution mode required")
        self.mode = mode
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
            "version": self.policy["version"], "mode": self.mode,
            "policy_sha256": self.last_hash, "schedule_sha256": sha256_json(self.rows),
            "threshold_ticks": self.policy["threshold_usd_ticks"], "max_attempts": len(self.rows),
            "max_in_flight": 1, "automatic_retries": 0, "resume_allowed": False}))

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
                "state": "one_attempt_reserved_before_dispatch", "fixture_only": self.mode == "offline_fixture"}
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
            return {"mode": self.mode, "attempts": self.attempts,
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
