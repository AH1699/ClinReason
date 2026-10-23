"""Local-only inventory and duplicate-screen for scanned clinical PDFs.

The output is private intake metadata, not OCR, de-identification, or case approval.
Requires local Poppler commands and Pillow; makes no model or network calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image


def command(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def page_count(pdf: Path) -> int:
    for line in command("pdfinfo", str(pdf)).splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError("PDF page count unavailable")


def first_page_dhash(pdf: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="clinreason_scan_") as tmp:
        prefix = Path(tmp) / "first"
        subprocess.run(
            ["pdftoppm", "-f", "1", "-l", "1", "-scale-to", "256",
             "-singlefile", "-gray", "-png", str(pdf), str(prefix)],
            check=True, capture_output=True,
        )
        with Image.open(prefix.with_suffix(".png")) as image:
            pixels = list(image.convert("L").resize((9, 8)).getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return f"{bits:016x}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    private_work = (root / "work").resolve()
    if output != private_work and private_work not in output.parents:
        parser.error("output must be under ignored work/")
    source = args.source.resolve()
    if not source.is_dir():
        parser.error("source directory does not exist")
    files = []
    for pdf in sorted(source.glob("*.pdf")):
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        text = command("pdftotext", str(pdf), "-")
        files.append({
            "path": str(pdf), "sha256": digest, "pages": page_count(pdf),
            "text_layer_chars": len(text.strip()), "first_page_dhash": first_page_dhash(pdf),
            "status": "raw_unreviewed_not_deidentified",
        })
    exact = defaultdict(list)
    for record in files:
        exact[record["sha256"]].append(record["sha256"][:12])
    near = []
    for index, left in enumerate(files):
        for right in files[index + 1:]:
            distance = bin(int(left["first_page_dhash"], 16) ^ int(right["first_page_dhash"], 16)).count("1")
            if distance <= 4:
                near.append({"a": left["sha256"][:12], "b": right["sha256"][:12],
                             "first_page_dhash_distance": distance})
    report = {"status": "HOLD: not OCRed, de-identified, episode-linked, or case-approved",
              "files": files, "possible_first_page_matches": near}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(output, 0o600)
    print(json.dumps({"files": len(files), "pages": sum(f["pages"] for f in files),
                      "files_with_text_layer": sum(f["text_layer_chars"] > 0 for f in files),
                      "exact_duplicate_groups": sum(len(group) > 1 for group in exact.values()),
                      "possible_first_page_matches": len(near),
                      "status": report["status"]}, indent=2))


if __name__ == "__main__":
    main()
