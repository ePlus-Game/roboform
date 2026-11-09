"""Offline tests of the SVG structural compatibility review; no CAPTCHA solving."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "svg_solver_review", ROOT / "scripts" / "review-svg-captcha-solver.py"
)
assert spec and spec.loader
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class OfflineSvgReviewTests(unittest.TestCase):
    def test_paths_are_counted_without_decoding_text(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path d="M10.0 20L12.0 24"/>'
            '<path d="M0 1L2 3" stroke="#222"/>'
            '</svg>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.svg"
            path.write_text(svg, encoding="utf-8")
            total, eligible, patterns = review.svg_structure(path)
        self.assertEqual((total, eligible), (2, 1))
        self.assertEqual(len(patterns), 1)
        self.assertTrue(patterns[0].startswith("ML"))

    def test_non_svg_and_oversized_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.svg"
            path.write_text("<html/>", encoding="utf-8")
            with self.assertRaises(ValueError):
                review.svg_structure(path)
            path.write_bytes(b"x" * 100_001)
            with self.assertRaises(ValueError):
                review.svg_structure(path)
            path.write_text("<svg>", encoding="utf-8")
            with self.assertRaises(ET.ParseError):
                review.svg_structure(path)

    def test_existing_fixture_is_inspected_without_solving(self):
        path = ROOT / "test" / "fixtures" / "user-provided-ocr.svg"
        total, eligible, signatures = review.svg_structure(path)
        self.assertGreaterEqual(total, 1)
        self.assertEqual(eligible, len(signatures))


if __name__ == "__main__":
    unittest.main()
