"""Unit tests for optional local ddddocr hint; no real model or browser needed."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ddddocr-hint.py"
spec = importlib.util.spec_from_file_location("ddddocr_hint_module", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_png(width=165, height=50):
    return (
        module.PNG_MAGIC
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00"
        + b"x" * 120
    )


class DdddocrHintTests(unittest.TestCase):
    def test_only_short_alphanumeric_text_is_accepted(self):
        for text in ("AB12", "XYz09", "a"):
            self.assertEqual(module.accepted_hint(text), text)
        for text in ("", "A B", "<script>", "A" * 13, "BAD_TOKEN", "é", 123, None):
            self.assertIsNone(module.accepted_hint(text))

    def test_validates_local_png_dimensions_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "image.png"
            file.write_bytes(fake_png())
            self.assertEqual(module.validate_image(file), fake_png())
            file.write_bytes(fake_png(width=1000))
            with self.assertRaises(ValueError):
                module.validate_image(file)
            file.write_bytes(b"not a png" * 40)
            with self.assertRaises(ValueError):
                module.validate_image(file)

    def test_uses_local_model_and_never_submits(self):
        calls = []

        class FakeOCR:
            def __init__(self, **kwargs):
                self.assert_kwargs = kwargs
                calls.append(("init", kwargs))

            def classification(self, data):
                calls.append(("classification", data))
                return "CLOUD7"

        fake = types.SimpleNamespace(DdddOcr=FakeOCR)
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "image.png"
            image.write_bytes(fake_png())
            with patch.dict(sys.modules, {"ddddocr": fake}):
                self.assertEqual(module.recognize(image), "CLOUD7")
        self.assertEqual([call[0] for call in calls], ["init", "classification"])
        self.assertEqual(calls[0][1], {"show_ad": False})

    def test_invalid_model_output_is_not_exposed(self):
        class FakeOCR:
            def __init__(self, **kwargs):
                pass

            def classification(self, _data):
                return "<html>not safe</html>"

        fake = types.SimpleNamespace(DdddOcr=FakeOCR)
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "image.png"
            image.write_bytes(fake_png())
            with patch.dict(sys.modules, {"ddddocr": fake}):
                self.assertIsNone(module.recognize(image))


if __name__ == "__main__":
    unittest.main()
