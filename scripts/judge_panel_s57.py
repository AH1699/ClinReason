"""Pure judge-only state machine with bounded, visible format failures.

No credentials, HTTP or clinical rule changes. Compatibility is checked here;
the live admission path must additionally verify the bank's raw provenance.
"""

from copy import deepcopy
from decimal import Decimal

from scripts import judge_saved_bank_s56 as saved

panel, workflow, score, guard = saved.panel, saved.workflow, saved.score, saved.guard
VERSION = "s57-saved-panel-live-v1"
FAILURE_POLICY = {
    "invalid_control": "stop_immediately",
    "failed_control_gate": "stop_before_development",
    "development_known_cost_format": "retain_rejected_missing_continue_independent_rows",
    "maximum_development_format_failures": 3,
    "failure_count_scope": "cumulative_across_first_and_repeat",
    "repeat_without_accepted_first": "skip_not_retry",
    "model_identity_or_completion": "stop_immediately",
    "unknown_cost_or_transport": "stop_immediately",
    "automatic_retries": 0, "resume_allowed": False, "repair_or_rescore": False,
}


class Core(panel.Rehearsal):
    """Reuse frozen control gate, duplicate protection and score validation."""

    def __init__(self, root, bank, threshold):
        amount = Decimal(threshold)
        if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
            raise ValueError("Invalid USD stop threshold")
        self.root, self.rows = root, saved.schedule(root)
        self.catalog, self.controls = workflow.families(root), score.controls(root)
        self.answers = saved.validate_records(root, bank["answers"])
        self.contexts, self.judgments, self.outcomes, self.first_payloads = {}, {}, {}, {}
        self.accounts, self.closed_lanes = [], {}
        self.index, self.monitored, self.unknown, self.format_failures = 0, 0, 0, 0
        self.threshold = int(amount * panel.old.TICKS_PER_USD)
        self.pending, self.terminal = None, None

    def prepare(self):
        if self.pending is not None:
            raise ValueError("Reply pending; no duplicate dispatch")
        if self.terminal:
            return None
        while self.index < len(self.rows):
            row = self.rows[self.index]
            if row["block"] == "development" and not self.gate()["pass"]:
                self.terminal = "control_gate_failed"
                return None
            reason = self.skip_reason(row)
            if reason:
                self.outcomes[row["sequence"]] = {"status": "skipped", "reason": reason}
                self.index += 1
                continue
            try:
                context = saved.request_context(self.root, row, self.catalog, self.controls, self.answers)
                body = guard._json_bytes(context["payload"])
                key = workflow.judgment_key({**row, "repeat": False})
                if row["repeat"] and body != self.first_payloads[key]:
                    raise ValueError("Repeated payload changed")
                self.first_payloads.setdefault(key, body)
                self.contexts[row["sequence"]] = context
                self.pending = deepcopy(row)
                return {"row": deepcopy(row), "payload": deepcopy(context["payload"])}
            except Exception:
                self.terminal = "local_context_failure"
                raise
        self.terminal = "schedule_complete"
        return None

    def _record(self, raw_bytes):
        row = self.pending
        context = self.contexts[row["sequence"]]
        spec = next(s for s in workflow.design(self.root)["judges"] if s["model"] == row["model"])
        raw = None
        try:
            raw = panel.saved.capture.strict_json(raw_bytes)
        except (ValueError, TypeError, UnicodeDecodeError):
            pass
        account = panel.saved.previous.account(raw, spec, context["payload"])
        self.accounts.append(account)
        delta = panel.old.monitoring_delta(account, row["provider"])["delta_ticks"]
        self.monitored += delta or 0
        category, result = "accepted", None
        if delta is None:
            self.unknown += 1
            category = self.terminal = "unknown_charge"
        else:
            try:
                result = score.decode(raw, row["provider"], row["model"], context["packet"])
            except score.JudgmentFailure as exc:
                category = "judgment_" + exc.category
                if row["block"] == "control":
                    self.terminal = "invalid_control"
                elif exc.category == "format":
                    self.format_failures += 1
                    if self.format_failures >= FAILURE_POLICY["maximum_development_format_failures"]:
                        self.terminal = "development_format_failure_limit"
                else:
                    self.terminal = category
            if self.monitored >= self.threshold:
                self.terminal = "spend_threshold_reached"
        if category == "accepted":
            self.judgments[workflow.judgment_key(row)] = result
        outcome = {"status": "accepted" if category == "accepted" else "rejected", "category": category}
        self.outcomes[row["sequence"]] = outcome
        self.index += 1
        self.pending = None
        return deepcopy(outcome)

    def report(self):
        value = super().report()
        value.update(version=VERSION, proposed_new_requests=324,
            development_format_failures=self.format_failures, failure_policy=deepcopy(FAILURE_POLICY))
        for cell in value["conversations"]:
            origin = "saved_upstream_import" if cell["family_id"] == panel.HOLD else "saved_s54_candidate"
            cell["answer_stage_origins"] = dict.fromkeys(score.STAGES, origin)
        return value


def report(core, mode, attempted, interrupted=False):
    value = saved.live.report(core, mode, attempted, interrupted)
    diagnostics = saved.source.diagnostics(core)
    cells = diagnostics["conversations"]
    for cell in cells:
        origin = "saved_upstream_import" if cell["family_id"] == panel.HOLD else "saved_s54_candidate"
        cell["answer_stage_origins"] = dict.fromkeys(score.STAGES, origin)
    return {**value, "version": VERSION, "new_candidate_calls": 0,
        "numeric_scores": any(c["first"] is not None or c["repeat"] is not None for c in cells),
        "first_complete_pairs": sum(c["first"] is not None for c in cells),
        "repeat_complete_pairs": sum(c["repeat"] is not None for c in cells),
        "all_pairs_complete": all(c["first"] is not None and c["repeat"] is not None for c in cells),
        "all_schedule_rows_disposed": core.index == len(core.rows),
        "historical_judgments_reused": False, "raw_text_exported": False,
        "case_diagnostics": cells, "control_diagnostics": diagnostics["controls"],
        "dispositions": [{"sequence": r["sequence"], **core.outcomes.get(r["sequence"],
            {"status": "unattempted", "reason": core.terminal or "incomplete_prefix"})} for r in core.rows]}
