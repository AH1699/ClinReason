import unittest
from pathlib import Path

from benchmark.frozen_batch_g import load_batch_g_dataset
from benchmark.provenance import sha256_json


class FrozenBatchGTests(unittest.TestCase):
    def test_later_public_batches_do_not_change_s8_to_s18_dataset_hash(self):
        dataset = load_batch_g_dataset(Path(__file__).resolve().parents[1])
        self.assertEqual(len(dataset["families"]), 38)
        self.assertEqual(
            sha256_json(dataset),
            "4fbcfbb0a6fc7bd7501a5b77c6a6570e5c1c72c5a973579cf84d687b7eea9919",
        )
