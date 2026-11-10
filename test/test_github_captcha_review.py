"""Offline tests for the GitHub Issue CAPTCHA review panel (no API calls)."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("github_captcha_review", ROOT / "scripts" / "github_captcha_review.py")
review_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review_mod)


class GithubReviewTests(unittest.TestCase):
    def setup_reviewer(self):
        context = {
            "GITHUB_REPOSITORY": "example/roboform",
            "GITHUB_ACTOR": "review-owner",
            "GITHUB_TOKEN": "test-only",
            "GITHUB_RUN_ID": "123456",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_SHA": "a" * 40,
        }
        with patch.dict(os.environ, context):
            return review_mod.GithubCaptchaReview()

    def test_issue_shows_image_ocr_suggestion_and_warning(self):
        reviewer = self.setup_reviewer()
        captured = []
        def fake_api(method, suffix, payload=None, missing_ok=False):
            captured.append((method, suffix, payload))
            if suffix.startswith("git/ref/heads/"):
                return None
            if method == "PUT":
                return {"content": {"sha": "b" * 40}}
            if method == "POST" and suffix == "issues":
                return {"number": 42, "html_url": "https://github.com/example/roboform/issues/42"}
            return {}
        reviewer.api = fake_api
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "isolated.png"
            image.write_bytes(review_mod.PNG_MAGIC + b"test-png-data" * 12)
            with patch("builtins.print"):
                self.assertEqual(reviewer.publish(image, "GYKL7", "36.8"), 42)
        issue = next(item[2] for item in captured if item[1] == "issues")
        body = issue["body"]
        self.assertIn("![Ảnh CAPTCHA thực tế](https://raw.githubusercontent.com/", body)
        self.assertIn("GYKL7", body)
        self.assertIn("36.8", body)
        self.assertIn("CHƯA XÁC MINH", body)
        self.assertIn("/captcha ABC123", body)
        self.assertNotIn("test-only", body)
        self.assertEqual(reviewer.image_sha, "b" * 40)

    def test_issue_distinguishes_filtered_ocr_from_no_detected_groups(self):
        reviewer = self.setup_reviewer()
        bodies = []
        def fake_api(method, suffix, payload=None, missing_ok=False):
            if method == "PUT":
                return {"content": {"sha": "b" * 40}}
            if method == "POST" and suffix == "issues":
                bodies.append(payload["body"])
                return {"number": 42, "html_url": "https://github.com/example/roboform/issues/42"}
            return None
        reviewer.api = fake_api
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "isolated.png"
            image.write_bytes(review_mod.PNG_MAGIC + b"test-png-data" * 12)
            with patch("builtins.print"):
                reviewer.publish(image, None, "15.6")
                reviewer.publish(image, None, "N/A")
        self.assertIn("kết quả bị lọc", bodies[0])
        self.assertIn("không phát hiện được", bodies[1])
        self.assertIn("CHƯA XÁC MINH", bodies[0])

    def test_issue_shows_both_ocr_hints_with_clear_warning(self):
        reviewer = self.setup_reviewer()
        bodies = []

        def fake_api(method, suffix, payload=None, missing_ok=False):
            if method == "PUT":
                return {"content": {"sha": "b" * 40}}
            if method == "POST" and suffix == "issues":
                bodies.append(payload["body"])
                return {"number": 42, "html_url": "https://github.com/example/roboform/issues/42"}
            return None

        reviewer.api = fake_api
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "isolated.png"
            image.write_bytes(review_mod.PNG_MAGIC + b"test-png-data" * 12)
            with patch("builtins.print"):
                reviewer.publish(
                    image, "G7TDR", "73.5",
                    ddddocr_hint="CLOUD7", ddddocr_enabled=True
                )
                reviewer.publish(
                    image, None, "N/A",
                    ddddocr_hint="<script>", ddddocr_enabled=True
                )
        self.assertIn("CLOUD7", bodies[0])
        self.assertIn("G7TDR", bodies[0])
        self.assertIn("Tesseract", bodies[0])
        self.assertIn("CHƯA XÁC MINH", bodies[0])
        self.assertIn("N/A (API nhận dạng không cung cấp)", bodies[0])
        self.assertIn("Không có gợi ý hợp lệ", bodies[1])
        self.assertNotIn("<script>", bodies[1])
        self.assertIn("/captcha ABC123", bodies[0])

    def test_issue_inherits_current_registration_email_and_source(self):
        reviewer = self.setup_reviewer()
        bodies = []
        titles = []

        def fake_api(method, suffix, payload=None, missing_ok=False):
            if method == "PUT":
                return {"content": {"sha": "b" * 40}}
            if method == "POST" and suffix == "issues":
                bodies.append(payload["body"])
                titles.append(payload["title"])
                return {"number": 42, "html_url": "https://github.com/example/roboform/issues/42"}
            return None

        reviewer.api = fake_api
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "isolated.png"
            image.write_bytes(review_mod.PNG_MAGIC + b"test-png-data" * 12)
            context = {
                "REGISTRATION_EMAIL": "selected@hoangnnm.tech",
                "REGISTRATION_EMAIL_SOURCE": "generated",
            }
            with patch.dict(os.environ, context), patch("builtins.print"):
                reviewer.publish(image, "AbC7", "80.0",
                                 ddddocr_hint="abc7", ddddocr_enabled=True)

        self.assertIn("selected@hoangnnm.tech", titles[0])
        self.assertIn("selected@hoangnnm.tech", bodies[0])
        self.assertIn("Tự tạo khi bỏ trống email", bodies[0])
        self.assertIn("/captcha AbC7", bodies[0])
        self.assertIn("/captcha abc7", bodies[0])
        self.assertIn("hoa/thường", bodies[0])

    def test_invalid_registration_email_rejected_before_api_upload(self):
        reviewer = self.setup_reviewer()
        calls = []
        reviewer.api = lambda *args, **kwargs: calls.append(args)
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "isolated.png"
            image.write_bytes(review_mod.PNG_MAGIC + b"test-png-data" * 12)
            with self.assertRaises(review_mod.ReviewUnavailable):
                reviewer.publish(image, "AB123", "80", registration_email="bad\nemail")
        self.assertEqual(calls, [])

    def test_only_workflow_actor_can_supply_code(self):
        reviewer = self.setup_reviewer()
        reviewer.issue = 42
        reviewer.api = lambda *a, **k: [
            {"user": {"login": "stranger"}, "body": "/captcha STRANGERCODE"},
            {"user": {"login": "review-owner"}, "body": "/captcha ABC123"},
        ]
        with patch("builtins.print"):
            self.assertEqual(reviewer.wait_for_answer(30), "ABC123")

    def test_cleanup_deletes_temporary_image_and_closes_issue(self):
        reviewer = self.setup_reviewer()
        reviewer.issue = 42
        reviewer.image_sha = "b" * 40
        calls = []
        reviewer.api = lambda method, suffix, payload=None: calls.append((method, suffix, payload))
        reviewer.finish("complete")
        self.assertTrue(any(m == "PATCH" and u == "issues/42" for m, u, _ in calls))
        self.assertTrue(any(m == "DELETE" and u.startswith("contents/captcha/") for m, u, _ in calls))

    def test_invalid_context_never_sends_api_request(self):
        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": "bad repository",
            "GITHUB_TOKEN": "fake",
        }, clear=True):
            with self.assertRaises(review_mod.ReviewUnavailable):
                review_mod.GithubCaptchaReview()


if __name__ == "__main__":
    unittest.main()
