"""Complete the Batch O author-control coverage, retaining unresolved labels.

One response component changes per contrast relative to its declared baseline.
Targeted records share identical blinded packets where appropriate; deduplicate
by exact packet hash rather than counting the same baseline as another case.
"""

from copy import deepcopy
import json
from pathlib import Path
from scripts import batch_o_wording_s52 as wording

batch, review, scoring = wording.batch, wording.review, wording.scoring
DATA = "data/audit/batch_o_component_controls_s53.json"
VERSION = "s53-batch-o-components-v1"
HF, N = "HC-MT-REASON-024", "HC-MT-MEDSAFE-020"
EXPECTED = {
    (HF, "initial", 1): {"omit_other_causes": "partial"},
    (HF, "initial", 2): {"grouped_equivalent": "met", "omit_urine": "partial"},
    (HF, "initial", 3): {"conditional_selected_hold": "met"},
    (HF, "update", 1): {"conditional_continue": "met", "conditional_reduce": "met", "conditional_hold": "met"},
    (HF, "update", 2): {"omit_other_contributors": "partial", "grouped_monitoring": None},
    (N, "initial", 1): {"plain_language_risk": "met", "omit_normal_baseline": "partial"},
    (N, "initial", 2): {"omit_thiamine": "partial", "grouped_electrolytes": None},
    (N, "initial", 3): {"cautious_local_plan": "met", "more_assertive_local_plan": "met"},
    (N, "update", 1): {"omit_calorie_inference_explanation": None},
    (N, "update", 2): {"omit_other_causes_clause": None}}


def paired(value):
    return (isinstance(value, dict) and set(value) == {"en", "zh-Hans"}
            and all(isinstance(t, str) and t.strip() for t in value.values()))


def materialize(root, value=None):
    value = deepcopy(value if value is not None else batch.load_json(root / DATA))
    dataset, anchors, old_packets, old_hypotheses = wording.materialize(root)
    header = {"version": VERSION, "status": "author_controls_not_clinical_truth",
        "s52_draft_sha256": batch.sha256_json(batch.load_json(root / wording.DATA)),
        "new_families": 0, "default_enabled": False, "live_calls": 0, "numeric_scores": False}
    if (set(value) != set(header) | {"initial_components", "groups"}
            or batch.sha256_json({k: value[k] for k in header}) != batch.sha256_json(header)):
        raise ValueError("Changed component draft scope or S52 parent")
    probes = batch.load_json(root / batch.FILES["controls"])["probes"]
    initial = value["initial_components"]
    if set(initial) != {HF, N} or any(set(v) != {"en", "zh-Hans"} for v in initial.values()):
        raise ValueError("Initial component coverage differs")
    for probe in probes:
        parts = initial[probe["family_id"]][probe["language"]]
        if (not isinstance(parts, list) or len(parts) != 3
                or any(not isinstance(t, str) or not t.strip() for t in parts)
                or probe["construction"]["component_separator"].join(parts) != probe["initial_response"]):
            raise ValueError("Initial components must reconstruct the original reference exactly")
    bindings, seen, packets, records = review.bindings(root), set(), {}, []
    families = {f["family_id"]: f for f in dataset["families"]}
    def add(identifier, family, lang, stage, index, status, packet, source):
        sha = batch.sha256_json(packet)
        if sha in packets and packets[sha] != packet: raise ValueError("Packet digest collision")
        packets[sha] = packet
        records.append({"control_id": identifier, "family_id": family, "language": lang, "stage": stage,
            "requirement_index": index, "packet_sha256": sha, "author_status": status,
            "status_basis": "exploratory_unlabelled" if status is None else "author_hypothesis_not_clinical_truth",
            "source": source})
    for key, packet in old_packets.items():
        fid, lang, profile = key.split("__")
        add("s52__" + key, fid, lang, "update", 3, old_hypotheses[key]["status"], packet, "s52")
    for group in value["groups"]:
        key = group["family_id"], group["stage"], group["requirement_index"]
        if (set(group) != {"family_id", "stage", "requirement_index", "binding", "review_question_en",
                         "review_question_zh", "base_override", "controls"}
                or type(key[2]) is not int or key not in EXPECTED or key in seen or group["binding"] != bindings[key]
                or not all(isinstance(group[k], str) and group[k].strip() for k in ("review_question_en", "review_question_zh"))):
            raise ValueError("Duplicate, stale or unknown component target")
        seen.add(key)
        fid, stage, index = key
        controls = group["controls"]
        expected = {"baseline": "met", **EXPECTED[key]}
        if (len(controls) != len(expected) or len({c["id"] for c in controls}) != len(controls)
                or {c["id"]: c["expected_status"] for c in controls} != expected):
            raise ValueError("Changed control coverage/hypotheses; exploratory controls must stay unlabelled")
        override = group["base_override"]
        if key == (HF, "update", 1):
            if (not isinstance(override, dict) or set(override) != {"component_index", "reason", "replacement"}
                    or type(override["component_index"]) is not int or override["component_index"] != 2
                    or not isinstance(override["reason"], str) or not override["reason"].strip()
                    or not paired(override["replacement"])):
                raise ValueError("Explicit neutral monitoring baseline required for treatment-direction controls")
        elif override is not None:
            raise ValueError("Unexpected baseline rewrite")
        for control in controls:
            if (set(control) != {"id", "expected_status", "replacement"}
                    or control["id"] == "baseline" and control["replacement"] is not None
                    or control["id"] != "baseline" and not paired(control["replacement"])):
                raise ValueError("Malformed paired component edit")
            for lang in ("en", "zh-Hans"):
                probe = next(p for p in probes if (p["family_id"], p["language"]) == (fid, lang))
                parts = deepcopy(initial[fid][lang] if stage == "initial" else probe["construction"]["safe_components"])
                if override is not None: parts[override["component_index"] - 1] = override["replacement"][lang]
                if control["replacement"] is not None:
                    if control["replacement"][lang] == parts[index - 1]: raise ValueError("Control makes no change")
                    parts[index - 1] = control["replacement"][lang]
                answer = probe["construction"]["component_separator"].join(parts)
                pair = {"language": lang, "initial_response": answer if stage == "initial" else probe["initial_response"],
                    "safe_update_response": answer if stage == "update" else batch.materialize_probe(probe)["safe_update_response"]}
                packet = scoring.stage_packet(batch.attach_anchors(batch.contrast_packet(families[fid], pair, "safe"), anchors),
                    stage, anchors["levels"])
                add("__".join((fid, stage, str(index), control["id"], lang)), fid, lang, stage, index,
                    control["expected_status"], packet, "s53")
    if seen != set(EXPECTED) or len({r["control_id"] for r in records}) != len(records):
        raise ValueError("Missing or duplicate targeted controls")
    return packets, records


def audit(root):
    packets, records = materialize(root)
    positions = {(r["family_id"], r["stage"], r["requirement_index"]) for r in records}
    return {"version": VERSION, "draft_sha256": batch.sha256_json(batch.load_json(root / DATA)),
        "status": "structural_author_control_coverage_not_clinical_validation",
        "criterion_positions_covered": len(positions), "bilingual_positions_covered": 2*len(positions),
        "new_targeted_control_records": sum(r["source"] == "s53" for r in records),
        "total_targeted_control_records": len(records), "unique_blinded_packets": len(packets),
        "author_hypotheses": sum(r["author_status"] is not None for r in records),
        "exploratory_unlabelled_records": sum(r["author_status"] is None for r in records),
        "packet_sha256": sorted(packets), "record_manifest_sha256": batch.sha256_json(records),
        "new_families": 0, "default_enabled": False, "numeric_scores": False, "live_calls": 0,
        "clinical_validation": False, "human_review_issues_resolved": 0}


if __name__ == "__main__":
    print(json.dumps(audit(Path(__file__).resolve().parents[1]), ensure_ascii=False, indent=2))
