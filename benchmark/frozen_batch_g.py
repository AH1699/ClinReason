"""Dataset revision used by S8–S18 exact-packet development diagnostics.

Later public batches must not silently change historical dataset hashes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_json
from .multiturn import merge_multiturn_datasets


BATCH_G_PATHS = (
    "data/multiturn/pilot_cases.json",
    "data/multiturn/batch_c_cases.json",
    "data/multiturn/batch_d_cases.json",
    "data/multiturn/batch_e_cases.json",
    "data/multiturn/batch_f_cases.json",
    "data/multiturn/batch_g_cases.json",
)


def load_batch_g_dataset(root: Path) -> dict[str, Any]:
    return merge_multiturn_datasets([load_json(root / path) for path in BATCH_G_PATHS])
