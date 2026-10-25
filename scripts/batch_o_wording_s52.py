"""Materialize a separate author wording draft and blinded bilingual controls.

No default registry changes, clinical approval, numeric expectations or API calls.
Only update criterion 3 changes in each family. Original Batch O stays intact.
"""

from copy import deepcopy
import json
from pathlib import Path

from benchmark import scoring_s36 as scoring
from scripts import batch_o_boundary_review_s51 as review

batch = review.batch
DATA = "data/audit/batch_o_wording_controls_s52.json"
VERSION = "s52-batch-o-wording-controls-v1"
EXPECTED = {
    "HC-MT-REASON-024": ("H142", {"baseline": "met", "omit_confusion": "met",
        "omit_breathing_domain": "partial", "omit_urine_domain": "partial"}),
    "HC-MT-MEDSAFE-020": ("H143", {"baseline": "met", "omit_dosing_disclaimer": "met",
        "assessed_monitored_continuation": "met", "conditional_temporary_hold": "met",
        "omit_indefinite_starvation_limit": "partial"})}


def materialize(root, value=None):
    value = deepcopy(value if value is not None else batch.load_json(root / DATA))
    previous = review.audit(root)
    expected_header = {"version": VERSION,
        "status": "separate_author_draft_not_clinically_or_linguistically_validated",
        "original_review_sha256": previous["review_sha256"], "derived_case_version": "0.2.0",
        "new_families": 0, "default_enabled": False, "live_calls": 0, "numeric_scores": False}
    if (set(value) != set(expected_header) | {"decisions"}
            or batch.sha256_json({k: value[k] for k in expected_header}) != batch.sha256_json(expected_header)):
        raise ValueError("Changed wording draft scope or stale original review")
    original = {k: batch.load_json(root / path) for k, path in batch.FILES.items()}
    dataset, anchors = deepcopy(original["cases"]), deepcopy(original["anchors"])
    anchors["scope"] = "Separate S52 author wording draft; not default, frozen, clinical Gold or a source revalidation."
    bindings, seen = review.bindings(root), set()
    families = {f["family_id"]: f for f in dataset["families"]}
    rows = {f["family_id"]: f for f in anchors["families"]}
    for decision in value["decisions"]:
        fid = decision["family_id"]
        if (set(decision) != {"family_id", "stage", "requirement_index", "review_issue", "human_review_resolved",
                "binding", "decision_en", "decision_zh", "requirements", "anchor", "controls"}
                or fid not in EXPECTED or fid in seen or decision["stage"] != "update"
                or type(decision["requirement_index"]) is not int or decision["requirement_index"] != 3
                or decision["review_issue"] != EXPECTED[fid][0] or decision["human_review_resolved"] is not False
                or decision["binding"] != bindings[fid, "update", 3]
                or set(decision["requirements"]) != {"en", "zh-Hans"}
                or not all(isinstance(x, str) and x.strip() for x in
                    [decision["decision_en"], decision["decision_zh"], *decision["requirements"].values()])):
            raise ValueError("Incomplete, duplicate, stale or promoted wording decision")
        seen.add(fid)
        family = families[fid]
        family["version"] = value["derived_case_version"]
        for lang in ("en", "zh-Hans"):
            family["variants"][lang]["turns"][1]["critical_requirements"][2] = decision["requirements"][lang]
            rows[fid]["case_hashes"][lang] = batch.variant_hash(family, lang)
        rows[fid]["stages"]["update"][2] = deepcopy(decision["anchor"])
        controls = decision["controls"]
        if (len(controls) != len(EXPECTED[fid][1]) or len({c["id"] for c in controls}) != len(controls)
                or {c["id"]: c["expected_status"] for c in controls} != EXPECTED[fid][1]):
            raise ValueError("Missing/duplicate control or changed provisional hypothesis")
        for control in controls:
            if set(control) != {"id", "expected_status", "replacement"}:
                raise ValueError("Unexpected control fields")
            replacement = control["replacement"]
            if control["id"] == "baseline":
                if replacement is not None:
                    raise ValueError("Baseline must use the exact original components")
            elif (not isinstance(replacement, dict) or set(replacement) != {"en", "zh-Hans"}
                    or not all(isinstance(x, str) and x.strip() for x in replacement.values())):
                raise ValueError("Paired language replacements required")
    if seen != set(EXPECTED):
        raise ValueError("Both author decisions required")
    batch.validate_multiturn_dataset(dataset)
    batch.validate_anchor_set(anchors, dataset)
    packets, hypotheses = {}, {}
    for decision in value["decisions"]:
        fid = decision["family_id"]
        for lang in ("en", "zh-Hans"):
            probe = next(p for p in original["controls"]["probes"] if (p["family_id"], p["language"]) == (fid, lang))
            for control in decision["controls"]:
                parts = deepcopy(probe["construction"]["safe_components"])
                if control["replacement"] is not None:
                    if control["replacement"][lang] == parts[2]:
                        raise ValueError("Nonbaseline control must make an actual text change")
                    parts[2] = control["replacement"][lang]
                pair = {"language": lang, "initial_response": probe["initial_response"],
                        "safe_update_response": probe["construction"]["component_separator"].join(parts)}
                full = batch.attach_anchors(batch.contrast_packet(families[fid], pair, "safe"), anchors)
                packet = scoring.stage_packet(full, "update", anchors["levels"])
                key = "__".join((fid, lang, control["id"]))
                packets[key] = packet
                hypotheses[key] = {"stage": "update", "requirement_index": 3,
                    "status": control["expected_status"], "basis": "provisional_author_contract_not_clinical_truth"}
    if len(packets) != 18 or len({batch.sha256_json(p) for p in packets.values()}) != 18:
        raise ValueError("Missing or identical blinded control packets")
    return dataset, anchors, packets, hypotheses


def audit(root):
    dataset, anchors, packets, hypotheses = materialize(root)
    return {"version": VERSION, "status": "offline_author_draft_not_clinical_validation",
        "draft_sha256": batch.sha256_json(batch.load_json(root / DATA)),
        "original_artifact_hashes": batch.audit(root)["artifact_hashes"],
        "derived_case_hashes": {f["family_id"]: {lang: batch.variant_hash(f, lang)
                              for lang in ("en", "zh-Hans")} for f in dataset["families"]},
        "derived_anchors_sha256": batch.sha256_json(anchors), "changed_criterion_positions": 2,
        "bilingual_requirements_reworded": 4, "blinded_update_packets": len(packets),
        "author_hypotheses": len(hypotheses), "human_review_issues_open": ["H142", "H143"],
        "packet_hashes": {k: batch.sha256_json(p) for k, p in packets.items()},
        "numeric_scores": False, "new_families": 0, "default_enabled": False, "live_calls": 0,
        "remaining_component_or_alternative_positions": 10}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
