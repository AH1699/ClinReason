"""Build offline focused contrasts; hypotheses never enter a judge packet."""
import hashlib
import json
from pathlib import Path
from benchmark import workflow_s38 as workflow, scoring_s36 as score
from benchmark.provenance import sha256_json

DATA = "data/multiturn/s49_medication_boundaries_draft_v1.json"
LANGS = ("en", "zh-Hans")


def load(root):
    value = json.loads((root / DATA).read_text())
    if (value["version"] != "s49-medication-boundaries-draft-v1"
            or value["status"] != "offline_author_hypotheses_not_clinically_adjudicated"
            or value["new_case_families"] != 0 or value["live_calls_authorized"] != 0):
        raise ValueError("Draft scope changed")
    family, anchors = workflow.families(root)[value["family_id"]]
    if hashlib.sha256((root / value["anchor_file"]).read_bytes()).hexdigest() != value["anchor_file_sha256"]:
        raise ValueError("Existing anchors changed")
    if {lang: workflow.variant_hash(family, lang) for lang in LANGS} != value["case_hashes"]:
        raise ValueError("Existing cases changed")
    return value, family, anchors


def answers(value, profile, lang):
    common = value["common"]; c = profile["components"]; plans = value["plan_components"]
    def join(parts): return " ".join(p for p in parts if p)
    initial = [common["initial_base"][lang]]
    if profile["group"] == "initial_plan":
        initial += [plans[c[k]][lang] for k in ("route", "ketone", "hold") if c[k] is not None]
    else:
        initial += [plans[k][lang] for k in ("route_clinician", "ketone_question", "hold_question")]
        if c["initial_hold"]: initial += [common["initial_hold"][lang]]
    initial += [common["initial_warning"][lang]]
    update = [common["update_base"][lang]]
    if profile["group"] == "update_hold": update += [value["hold_actions"][c["update_action"]][lang]]
    return join(initial), join(update)


def packets(root):
    value, family, anchors = load(root); result = {}
    for p in value["profiles"]:
        for lang in LANGS:
            initial, update = answers(value, p, lang)
            full = workflow.full_packet(family, anchors, lang, initial, update)
            stage = score.stage_packet(full, p["stage"], anchors["levels"])
            selected = [a for a in stage["criterion_anchors"] if a["requirement_index"] == p["requirement_index"]]
            if len(selected) != 1: raise ValueError("Target requirement missing")
            key = p["id"] + "__" + lang
            if key in result: raise ValueError("Duplicate profile")
            result[key] = {k: stage[k] for k in ("case_id", "case_content_hash", "language", "scoring_stage", "transcript", "level_definitions")}
            result[key]["target_requirements"] = selected
    return result


def audit(root):
    value, _, _ = load(root); generated = packets(root)
    profiles = {p["id"]: p for p in value["profiles"]}
    if len(profiles) != 14 or len(generated) != 28: raise ValueError("Incomplete draft set")
    labelled = sum(p["author_hypothesis"] is not None for p in profiles.values()) * len(LANGS)
    if any(p["author_hypothesis"] not in (None, "met", "partial") for p in profiles.values()):
        raise ValueError("Invalid author hypothesis")
    for pair in value["contrasts"]:
        a, b = profiles[pair["a"]], profiles[pair["b"]]
        if (a["group"], a["stage"], a["requirement_index"]) != (b["group"], b["stage"], b["requirement_index"]):
            raise ValueError("Cross-target contrast")
        changes = [k for k in a["components"] if a["components"][k] != b["components"][k]]
        if changes != [pair["changed_component"]]: raise ValueError("Contrast is not one-component")
        for lang in LANGS:
            left, right = answers(value, a, lang), answers(value, b, lang)
            changed_turn = 0 if pair["changed_component"] != "update_action" else 1
            if left[changed_turn] == right[changed_turn] or left[1-changed_turn] != right[1-changed_turn]:
                raise ValueError("Contrast changed unexpected answer turn")
    return {"version": value["version"], "draft_sha256": sha256_json(value), "packets_sha256": sha256_json(generated),
        "case_hashes": value["case_hashes"], "anchor_file_sha256": value["anchor_file_sha256"],
        "packets": len(generated), "author_hypotheses": labelled, "unlabelled_packets": len(generated)-labelled,
        "one_component_contrasts": len(value["contrasts"])*len(LANGS), "new_case_families": 0,
        "live_calls": 0, "clinical_validation": False, "judge_boundary_accuracy_measured": False,
        "numeric_scores": False, "existing_labels_changed": False,
        "scope": "Mechanical provenance, packet blinding, stage isolation and contrast checks only; author hypotheses are not ground truth."}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
