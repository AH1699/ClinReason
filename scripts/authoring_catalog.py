"""Read-only public draft inventory. No scoring, promotion or provider calls."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from benchmark.config import load_json, load_jsonl
from benchmark.provenance import sha256_json

PLAN = "config/authoring_catalog_v1.json"


def local_file(root, relative):
    path = Path(relative)
    if (path.is_absolute() or ".." in path.parts or path.parts[0] not in {"config", "data"}
            or (root / path).is_symlink() or not (root / path).resolve().is_relative_to(root.resolve())):
        raise ValueError("Only repository public config/data paths belong in the catalog")
    if not (root / path).is_file():
        raise ValueError("Catalog source missing")
    return root / path


def catalog(root):
    root = Path(root)
    spec = load_json(root / PLAN)
    if spec["version"] != "authoring-catalog-v1" or spec["changes_default_registry"] is not False:
        raise ValueError("Not an authoring-only catalog")
    config = load_json(local_file(root, spec["registered_config"]))
    paths = config["multiturn_cases_paths"] + config["professional_cases_paths"] + spec["standalone_case_paths"]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate or registered standalone dataset")
    entries, seen = [], set()
    def add(value):
        if value["family_id"] in seen:
            raise ValueError("Family identity overlaps catalog datasets")
        if value["languages"] != ["en", "zh-Hans"]:
            raise ValueError("Exactly one EN/ZH pair required")
        seen.add(value["family_id"]); entries.append(value)

    alpha = defaultdict(list)
    for row in load_jsonl(local_file(root, config["cases_path"])):
        alpha[row["metadata"]["case_family_id"]].append(row)
    for fid, rows in alpha.items():
        add({"family_id": fid, "track": "alpha_single_turn", "registration": "registered_development",
             "category": rows[0]["category"], "case_path": config["cases_path"],
             "languages": sorted(r["language"] for r in rows),
             "content_sha256": sha256_json(rows), "label_location": "inline reference_answer, critical_requirements and critical_errors",
             "source_refs": list(dict.fromkeys(s for r in rows for s in r["metadata"]["source_refs"])),
             "clinical_validation": False, "empirical_difficulty": "not_inferred_by_catalog"})
    for relative in paths:
        dataset = load_json(local_file(root, relative))
        professional = relative in config["professional_cases_paths"]
        standalone = relative in spec["standalone_case_paths"]
        for family in dataset["families"]:
            add({"family_id": family["family_id"], "track": "professional" if professional else "patient_multiturn",
                 "registration": "standalone_authoring" if standalone else "registered_development",
                 "category": family.get("category", family.get("workflow")), "case_path": relative,
                 "languages": sorted(family["variants"]), "content_sha256": sha256_json(family),
                 "label_location": "inline reference_elements and critical_errors; professional scoring disabled" if professional else
                     "inline stage critical_requirements and critical_errors; experiment must separately bind exact anchors",
                 "source_refs": family["source_refs"], "clinical_validation": False,
                 "empirical_difficulty": "not_inferred_by_catalog"})
    registered = [r for r in entries if r["registration"] == "registered_development"]
    standalone = [r for r in entries if r["registration"] == "standalone_authoring"]
    return {"version": spec["version"], "counts": {
                "registered_families": len(registered), "registered_variants": sum(len(r["languages"]) for r in registered),
                "standalone_families": len(standalone), "standalone_variants": sum(len(r["languages"]) for r in standalone),
                "distinct_public_draft_families": len(entries),
                "target_distinct_families": spec["target_distinct_families"],
                "additional_draft_families_to_target": max(0, spec["target_distinct_families"] - len(entries)),
                "registered_by_track": dict(Counter(r["track"] for r in registered)),
            }, "scope": {"default_registry_changed": False, "calibration_or_confirmation_drafts_included": False,
                "private_records_included": False, "new_cases_created": 0, "live_calls": 0,
                "clinical_validation": False, "difficulty_or_release_readiness_estimated": False},
            "families": entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    value = catalog(Path(__file__).resolve().parents[1])
    if args.summary: value.pop("families")
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
