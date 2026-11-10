"""Rendering regression tests: no network, browser, or actual CAPTCHA input."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_content import (
    command_to_copy,
    comparison_note,
    normalized_registration_email,
    render_review,
    safe_hint,
)


def content(**overrides):
    args = {
        "image_url": "https://raw.githubusercontent.com/example/roboform/previews/example.png",
        "run_url": "https://github.com/example/roboform/actions/runs/12345",
        "run": "12345",
        "attempt": "2",
        "actor": "review-owner",
        "email": "generated123@hoangnnm.tech",
        "email_source": "generated",
        "tesseract_hint": "bMWyHd3",
        "tesseract_confidence": "48.0",
        "ddddocr_hint": "bmhb3",
        "ddddocr_enabled": True,
    }
    args.update(overrides)
    return render_review(**args)


class ReviewRenderingTests(unittest.TestCase):
    def test_email_and_source_visible_in_issue_title_body_and_summary(self):
        result = content()
        self.assertIn("generated123@hoangnnm.tech", result.title)
        self.assertIn("generated123@hoangnnm.tech", result.body)
        self.assertIn("generated123@hoangnnm.tech", result.summary)
        self.assertIn("Tự tạo khi bỏ trống email", result.body)
        self.assertIn("- Email source: generated", result.summary)
        self.assertIn("__ISSUE_URL__", result.summary)
        self.assertIn("run 12345/2", result.title)

    def test_every_available_prediction_has_a_separate_copyable_command(self):
        result = content()
        self.assertIn("~~~text\n/captcha bMWyHd3\n~~~", result.body)
        self.assertIn("~~~text\n/captcha bmhb3\n~~~", result.body)
        self.assertIn("~~~text\n/captcha ABC123\n~~~", result.body)
        self.assertIn("CHƯA XÁC MINH", result.body)
        self.assertIn("chữ hoa", result.body)
        self.assertIn("N/A (API nhận dạng không cung cấp)", result.body)

    def test_no_auto_case_fix_even_when_only_casing_differs(self):
        result = content(tesseract_hint="AbC7", ddddocr_hint="abc7")
        self.assertIn("vị trí 1, 3", result.body)
        self.assertIn("Không tự chuyển chữ hoa thành chữ thường", result.body)
        self.assertIn("/captcha AbC7", result.body)
        self.assertIn("/captcha abc7", result.body)
        self.assertEqual(comparison_note("ABC", "ABC")[:12], "Hai mô hình ")
        self.assertIn("Khác số ký tự", comparison_note("ABC", "AB"))

    def test_no_dangerous_unbounded_predictions_or_unchecked_email(self):
        self.assertIsNone(safe_hint("<script>"))
        self.assertEqual(command_to_copy("aB12"), "~~~text\n/captcha aB12\n~~~")
        self.assertEqual(command_to_copy("example@gmail.com"), "")
        result = content(tesseract_hint="<script>", ddddocr_hint="a" * 13)
        self.assertNotIn("<script>", result.body)
        self.assertNotIn("a" * 13, result.body)
        self.assertNotIn("Copy cú pháp từ ddddocr", result.body)
        for invalid in ("foo\nissue-title", "<script>@example.com", "a..b@example.com"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalized_registration_email(invalid)
                with self.assertRaises(ValueError):
                    content(email=invalid)

    def test_tesseract_only_and_unavailable_hints(self):
        result = content(
            email="manual@example.com", email_source="provided",
            tesseract_hint=None, tesseract_confidence="N/A",
            ddddocr_enabled=False
        )
        self.assertIn("Email nhập khi chạy workflow", result.body)
        self.assertIn("OCR không phát hiện được nhóm ký tự", result.body)
        self.assertNotIn("ddddocr gợi ý", result.body)
        self.assertNotIn("Copy cú pháp từ Tesseract", result.body)

    def test_filtered_hint_text_is_distinct_from_no_text(self):
        result = content(tesseract_hint=None, tesseract_confidence="15.6")
        self.assertIn("kết quả bị lọc", result.body)
        self.assertIn("Độ tin cậy OCR", result.body)

    def test_no_email_source_fallback_is_safe(self):
        result = content(email=None, email_source="unexpected", ddddocr_hint=None)
        self.assertIn("Chưa xác định", result.body)
        self.assertIn("unknown", result.summary)
        self.assertNotIn("unexpected", result.body)


if __name__ == "__main__":
    unittest.main()
