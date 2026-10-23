"""On-device OCR for private clinical intake; no model or network calls.

Run only in a local environment that allows macOS Vision. Raw text remains below
ignored work/ with restrictive file permissions. OCR is not de-identification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import Foundation
import Vision


SIGNALS = {
    "id_field": re.compile(r"姓名|身份证|住院号|病案号|病历号|患者编号"),
    "contact_field": re.compile(r"电话|手机|住址|地址|联系人"),
    "date_like": re.compile(r"(?:19|20)\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}"),
    "long_digit_sequence": re.compile(r"(?<!\d)\d{11,18}(?!\d)"),
}


def page_count(pdf: Path) -> int:
    info = subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True).stdout
    for line in info.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError("PDF page count unavailable")


def recognize(png: Path) -> str:
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    request.setRecognitionLanguages_(["zh-Hans", "en-US"])
    url = Foundation.NSURL.fileURLWithPath_(str(png))
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"On-device Vision OCR unavailable: {error!r}")
    lines = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if candidates:
            lines.append(str(candidates[0].string()))
    return "\n".join(lines)


def private_write(path: Path, content: str) -> None:
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--limit-files", type=int, default=3)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    private_work = (root / "work").resolve()
    if output == private_work or private_work not in output.parents:
        parser.error("output must be a dedicated directory under ignored work/")
    source = args.source.resolve()
    if not source.is_dir() or args.limit_files < 1 or not 72 <= args.dpi <= 200:
        parser.error("source directory, positive file limit, and 72–200 dpi are required")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    summary = []
    for pdf in sorted(source.glob("*.pdf"))[: args.limit_files]:
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        pages = []
        with tempfile.TemporaryDirectory(prefix="clinreason_ocr_") as tmp:
            for page in range(1, page_count(pdf) + 1):
                prefix = Path(tmp) / "page"
                subprocess.run(
                    ["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(args.dpi),
                     "-singlefile", "-png", str(pdf), str(prefix)],
                    check=True, capture_output=True,
                )
                pages.append({"page": page, "text": recognize(prefix.with_suffix(".png"))})
        raw_text = "\n".join(page["text"] for page in pages)
        record = {"source_path": str(pdf), "sha256": digest, "pages": pages,
                  "status": "raw_ocr_unreviewed_not_deidentified"}
        private_write(output / f"{digest[:16]}.json",
                      json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        summary.append({"sha256_prefix": digest[:16], "pages": len(pages),
                        "recognized_chars": len(raw_text),
                        "privacy_signal_counts": {key: len(pattern.findall(raw_text))
                                                  for key, pattern in SIGNALS.items()}})
    print(json.dumps({"files_processed": len(summary),
                      "pages_processed": sum(item["pages"] for item in summary),
                      "recognized_chars": sum(item["recognized_chars"] for item in summary),
                      "privacy_signal_counts": {key: sum(item["privacy_signal_counts"][key]
                                                         for item in summary) for key in SIGNALS},
                      "status": "HOLD: OCR is unverified and not de-identified"}, indent=2))


if __name__ == "__main__":
    main()
