"""Build a private page-level manual-review queue from local clinical OCR.

No OCR text or matched identifier value appears in stdout or tracked files.
All pages remain held; a regex match is neither de-identification nor approval.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path


SIGNALS = {
    "identity_field": re.compile(r"姓名|身份证|住院号|病案号|病历号|患者编号"),
    "contact_field": re.compile(r"电话|手机|住址|地址|联系人"),
    "date_like": re.compile(r"(?:19|20)\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}"),
    "long_digit_sequence": re.compile(r"(?<!\d)\d{11,18}(?!\d)"),
}


def page_signals(text: str) -> dict[str, int]:
    return {name: len(pattern.findall(text)) for name, pattern in SIGNALS.items()}


def build_worklist(intake: dict, ocr_records: list[dict]) -> dict:
    expected = {record["sha256"]: record for record in intake["files"]}
    actual = {record["sha256"]: record for record in ocr_records}
    if len(expected) != len(intake["files"]) or len(actual) != len(ocr_records) or expected.keys() != actual.keys():
        raise ValueError("OCR file hashes must exactly match the inventory")
    entries = []
    for digest in sorted(expected):
        source, record = expected[digest], actual[digest]
        if (record["status"] != "raw_ocr_unreviewed_not_deidentified"
                or len(record["pages"]) != source["pages"]
                or [page["page"] for page in record["pages"]] != list(range(1, source["pages"] + 1))):
            raise ValueError("OCR page count, order, or status differs from inventory")
        for page in record["pages"]:
            signals = page_signals(page["text"])
            entries.append({
                "source_sha256": digest,
                "source_path_local_only": source["path"],
                "page": page["page"],
                "signal_counts": signals,
                "ocr_quality": "unverified_against_scan",
                "identifier_review": "pending_manual_review",
                "exact_date_review": "pending_manual_review",
                "clinical_fact_review": "pending_manual_review",
                "episode_linkage": "unverified",
                "release_status": "hold_no_external_model_or_public_case",
            })
    totals = Counter()
    for entry in entries:
        totals.update(entry["signal_counts"])
    return {
        "status": "private_review_worklist_no_deidentification_or_clearance",
        "file_count": len(expected),
        "page_count": len(entries),
        "signal_totals": dict(sorted(totals.items())),
        "pages_with_any_signal": sum(any(entry["signal_counts"].values()) for entry in entries),
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("ocr_directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = (root / "work").resolve()
    output = args.output.resolve()
    if output == work or work not in output.parents:
        parser.error("output must be inside ignored work/")
    intake = json.loads(args.inventory.read_text(encoding="utf-8"))
    ocr_records = [json.loads(path.read_text(encoding="utf-8"))
                   for path in sorted(args.ocr_directory.glob("*.json"))]
    report = build_worklist(intake, ocr_records)
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output.parent, 0o700)
    descriptor = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.chmod(output, 0o600)
    print(json.dumps({key: report[key] for key in
                      ("status", "file_count", "page_count", "signal_totals", "pages_with_any_signal")},
                     indent=2))


if __name__ == "__main__":
    main()
