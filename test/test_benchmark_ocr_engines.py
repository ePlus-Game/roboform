"""Unit tests for deterministic, synthetic OCR benchmark (no OCR models required)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "benchmark-ocr-engines.py"
spec = importlib.util.spec_from_file_location("ocr_benchmark", PATH)
assert spec and spec.loader
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class SyntheticOCRBenchmarkTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(benchmark.normalize("Hello 2026!\n"), "HELLO2026")
        self.assertEqual(benchmark.normalize(None), "")

    def test_edit_distance(self):
        self.assertEqual(benchmark.edit_distance("ABC", "ABC"), 0)
        self.assertEqual(benchmark.edit_distance("ABC", "AXC"), 1)
        self.assertEqual(benchmark.edit_distance("ABC", "AB"), 1)
        self.assertEqual(benchmark.edit_distance("ABC", ""), 3)

    def test_aggregate_exact_rate_and_character_error(self):
        rows = [
            {"expected": "ABC", "observed": "ABC", "correct": True,
             "edit_distance": 0, "duration_ms": 10},
            {"expected": "ABC", "observed": "AXC", "correct": False,
             "edit_distance": 1, "duration_ms": 30},
        ]
        stats = benchmark.aggregate(rows)
        self.assertEqual(stats["samples"], 2)
        self.assertEqual(stats["exact_matches"], 1)
        self.assertEqual(stats["exact_match_rate"], 0.5)
        self.assertEqual(stats["character_error_rate"], round(1 / 6, 4))
        self.assertEqual(stats["mean_inference_ms"], 20.0)

    def test_generated_samples_are_deterministic_labeled_text(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("Pillow not installed in lightweight unit-test environment")
        if not Path(benchmark.FONT_SANS).is_file() or not Path(benchmark.FONT_SERIF).is_file():
            self.skipTest("DejaVu fonts not installed")
        with tempfile.TemporaryDirectory() as tmp:
            examples = benchmark.samples(Path(tmp))
            self.assertEqual(len(examples), len(benchmark.LABELS) * len(benchmark.STYLES))
            self.assertEqual({item["style"] for item in examples}, set(benchmark.STYLES))
            for example in examples:
                self.assertTrue(Path(example["file"]).read_bytes().startswith(b"\x89PNG"))
                self.assertIn(example["label"], benchmark.LABELS)


if __name__ == "__main__":
    unittest.main()
