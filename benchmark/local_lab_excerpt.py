"""On-device, allowlisted lab-table excerpts for private OCR verification.

Everything except exact analyte labels and short numeric/unit cells aligned to
those labels is masked in the source image. No narrative, names, identifiers,
absolute dates or source paths are emitted. Outputs remain private review drafts.
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

ANALYTES = {
    "potassium": re.compile(r"^(?:钾|血钾|K\+?|钾离子)$", re.I),
    "sodium": re.compile(r"^(?:钠|血钠|Na\+?|钠离子)$", re.I),
    "creatinine": re.compile(r"^(?:肌酐|血肌酐|CREA|CRE|Cr)$", re.I),
    "hemoglobin": re.compile(r"^(?:血红蛋白|血红蛋白浓度|血色素|HGB|Hb)$", re.I),
    "platelets": re.compile(r"^(?:血小板|血小板计数|血小板总数|PLT)$", re.I),
    "wbc": re.compile(r"^(?:白细胞|白细胞计数|白细胞总数|WBC)$", re.I),
}
NUMBER = re.compile(r"^[<>≤≥]?\s*\d{1,4}(?:\.\d{1,4})?\s*(?:[-~～—]\s*\d{1,4}(?:\.\d{1,4})?)?\s*[↑↓HL]?$", re.I)
UNIT = re.compile(r"^(?:[μµu]?mol/[lL]|mmol/[lL]|g/[dD]?[lL]|10(?:\^?9|⁹)/[lL])$", re.I)


def select_cells(boxes):
    labels = []
    for index, box in enumerate(boxes):
        label = box["text"].strip().lstrip("*＊")
        for analyte, pattern in ANALYTES.items():
            if pattern.fullmatch(label):
                labels.append((index, analyte))
    selected = set()
    rows = []
    for index, analyte in labels:
        label = boxes[index]
        cy = (label["bounds"][1] + label["bounds"][3]) / 2
        height = label["bounds"][3] - label["bounds"][1]
        cells = []
        for cell_index, box in enumerate(boxes):
            text = box["text"].strip()
            y = (box["bounds"][1] + box["bounds"][3]) / 2
            if (box["bounds"][0] > label["bounds"][2]
                    and abs(y-cy) < height * 0.55 and (NUMBER.fullmatch(text) or UNIT.fullmatch(text))):
                cells.append(cell_index)
        # Keep coordinates and raw numeric/unit cells; do not guess which is a
        # patient result versus reference interval from OCR reading order.
        if cells:
            selected.add(index)
            selected.update(cells)
            rows.append({"analyte": analyte,
                         "cells_left_to_right": [{"text": boxes[i]["text"], "bounds": boxes[i]["bounds"]}
                                                 for i in sorted(cells, key=lambda i: boxes[i]["bounds"][0])],
                         "label_bounds": label["bounds"], "value_assignment": "pending_visual_verification"})
    return sorted(selected), rows


def recognize_boxes(png):
    import Foundation
    import Vision
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    request.setRecognitionLanguages_(["zh-Hans", "en-US"])
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(Foundation.NSURL.fileURLWithPath_(str(png)), {})
    ok, _ = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError("Local OCR failed")
    boxes = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        rect = observation.boundingBox()
        boxes.append({"text": str(candidates[0].string()), "bounds": [float(rect.origin.x), float(1-rect.origin.y-rect.size.height),
                      float(rect.origin.x+rect.size.width), float(1-rect.origin.y)]})
    return boxes


def private_json(path, value):
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hash-prefix", required=True)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.output.resolve().is_relative_to((root/"work").resolve()) or args.output.exists():
        parser.error("Use a fresh private work/ directory")
    # Optional local-image dependency, not required by the standard-library
    # benchmark or select_cells unit tests. OCR additionally needs macOS Vision.
    from PIL import Image

    records = [json.loads(path.read_text(encoding="utf-8")) for path in (root/"work/xi_an_ocr_private").glob("*.json")]
    matches = [row for row in records if row["sha256"].startswith(args.hash_prefix)]
    if len(matches) != 1 or args.page < 1 or args.page > len(matches[0]["pages"]):
        parser.error("Source hash/page must resolve uniquely")
    record = matches[0]
    source = Path(record["source_path"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("Source PDF changed")
    args.output.mkdir(parents=True, mode=0o700)
    os.chmod(args.output, 0o700)
    with tempfile.TemporaryDirectory(prefix="clinreason_lab_") as tmp:
        png = Path(tmp)/"page.png"
        subprocess.run(["pdftoppm", "-f", str(args.page), "-l", str(args.page), "-r", "180", "-singlefile", "-png", str(source), str(png.with_suffix(""))], check=True, capture_output=True)
        boxes = recognize_boxes(png)
        selected, rows = select_cells(boxes)
        with Image.open(png) as original:
            masked = Image.new("RGB", original.size, "white")
            width, height = original.size
            for index in selected:
                x0,y0,x1,y1 = boxes[index]["bounds"]
                bounds = (int(x0*width), int(y0*height), int(x1*width)+1, int(y1*height)+1)
                masked.paste(original.crop(bounds), bounds[:2])
            masked.save(args.output/"masked_source.png")
            os.chmod(args.output/"masked_source.png", 0o600)
    private_json(args.output/"candidate_rows.json", {"source_sha256": record["sha256"], "page": args.page,
                 "status": "allowlisted_excerpt_pending_visual_and_clinical_review", "rows": rows,
                 "limits": "No full-record de-identification or encounter linkage claim; masked boxes may contain OCR/column errors. Not for public case release."})
    print(json.dumps({"status": "private_masked_excerpt_created", "analyte_rows": len(rows),
                      "source_hash_prefix": record["sha256"][:16], "page": args.page,
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
