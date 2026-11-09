"""Regression checks for the read-only verification-image diagnostic."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze-verification-image.py"
spec = importlib.util.spec_from_file_location("verification_image_diagnostic", SCRIPT)
assert spec and spec.loader
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


def png_header(width: int, height: int) -> bytes:
    return diagnostic.PNG_MAGIC + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)


class VerificationImageDiagnosticsTest(unittest.TestCase):
    def test_image_dimensions_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            image.write_bytes(png_header(165, 50))
            self.assertEqual(diagnostic.dimensions(image), (165, 50))
            image.write_bytes(png_header(2000, 400))
            with self.assertRaises(ValueError):
                diagnostic.dimensions(image)
            image.write_bytes(b"not a png")
            with self.assertRaises(ValueError):
                diagnostic.dimensions(image)

    def test_ocr_text_is_discarded_and_only_metrics_returned(self) -> None:
        tsv = (
            "level\tconf\ttext\n"
            "5\t70.5\tSECRET_A\n"
            "5\t80.5\tSECRET_B\n"
            "5\t-1\t\n"
        )
        count, confidence = diagnostic.confidence_metrics(tsv)
        self.assertEqual(count, 2)
        self.assertEqual(confidence, 75.5)
        self.assertEqual(diagnostic.confidence_metrics("level\tconf\ttext\n"), (0, None))

    def test_analyze_never_returns_ocr_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            image.write_bytes(png_header(165, 50))
            result = SimpleNamespace(returncode=0, stdout="level\tconf\ttext\n5\t99\tSECRET_TOKEN\n")
            with patch.object(diagnostic.subprocess, "run", return_value=result) as mock_run:
                width, height, count, score = diagnostic.analyze(image)
            self.assertEqual((width, height, count, score), (165, 50, 1, 99.0))
            self.assertNotIn("SECRET_TOKEN", repr((width, height, count, score)))
            self.assertEqual(mock_run.call_args.args[0][0], "tesseract")


if __name__ == "__main__":
    unittest.main()
