"""Prospective reporting/transport policy, deliberately not a live authorization."""

from copy import deepcopy
import json
from pathlib import Path
from scripts import mixed_panel_s51 as panel

PATH = "config/mixed_policy_s53_v1.json"
VERSION = "s53-mixed-panel-policy-draft-v1"


def policy(root):
    value = panel.read_json(root / PATH)
    spec = panel.plan(root)
    expected = {
        "version": VERSION, "status": "prospective_engineering_draft_not_live_authorization",
        "schedule_from": panel.PLAN, "candidate_requests": "unchanged_s38_for_saved_answer_compatibility",
        "judge": {"model": panel.saved.MODEL, "instruction_schema": "s47_observation_completeness",
            "max_output_tokens": 32768, "thinking_level": "medium", "sampling": "provider_defaults_unpinned",
            "uniform_across_controls_first_and_repeat": True},
        "scoring": {"arithmetic": "unchanged_s36", "labels": "unchanged_s51_inputs",
            "retrospective_rescoring": False, "score_band_fitting": False},
        "control_gate": {"expected_records": 36, **panel.old.GATE},
        "reporting": {"expected_conversations": 72, "held_conversations": 8, "hold_family": panel.HOLD,
            "held_scores": "raw_diagnostics_only_not_comparable", "held_criteria": "preserve_status_and_evidence_no_override",
            "missing_scores": "missing_never_zero", "cell_removal": False, "reweighting": False,
            "pooled_model_means": False, "model_rankings": False, "repeats": "separate_exact_payload_not_averaged",
            "clinical_validation": False},
        "transport": {"implementation": "frozen_s46_capture_mocked_in_s53", "maximum_proposed_requests": 452,
            "max_in_flight": 1, "automatic_retries": 0, "resume_allowed": False,
            "unknown_delivery_or_charge": "global_stop", "known_cost_invalid_response": "close_model_lane",
            "redirects": False},
        "authorization": {"live_call_allowance": 0, "live_budget_usd": None, "pricing_reverified": False,
            "approval_consumption_available": False}}
    if panel.guard._json_bytes(value) != panel.guard._json_bytes(expected):
        raise ValueError("Changed draft contract; no implicit policy or paid-scope expansion")
    if any(value["judge"][k] != spec["judge_draft"][k] for k in
           ("instruction_schema", "max_output_tokens", "thinking_level", "sampling")):
        raise ValueError("Uniform judging settings differ from S51")
    return value


def reporting_manifest(root):
    spec = policy(root)
    cells = panel.conversation_manifest(root)
    for cell in cells:
        held = cell["comparative_review_hold"]
        cell["score_use"] = "review_held_raw_diagnostic_only" if held else "provisional_case_diagnostic_after_control_gate"
        cell["review_issues"] = deepcopy(panel.plan(root)["review_holds"].get(cell["family_id"], {}))
    return {"policy_sha256": panel.sha256_json(spec), "conversations": cells,
        "reporting": deepcopy(spec["reporting"]), "computed_scores": False,
        "live_calls": 0, "clinical_validation": False}


if __name__ == "__main__":
    print(json.dumps(reporting_manifest(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
