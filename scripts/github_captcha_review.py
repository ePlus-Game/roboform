"""Human-reviewed Firefox verification in GitHub Issues.

An isolated PNG and unverified OCR suggestion are shown publicly during the
review. Only a human-authored comment from the workflow actor is accepted.
No OCR prediction is ever submitted automatically.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import time
from urllib import error, request

PNG_MAGIC = bytes((137, 80, 78, 71, 13, 10, 26, 10))
PREVIEW_BRANCH = "captcha-review-previews"


class ReviewUnavailable(Exception):
    pass


class GithubCaptchaReview:
    def __init__(self):
        self.repo = os.getenv("GITHUB_REPOSITORY", "")
        self.actor = os.getenv("GITHUB_ACTOR", "")
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.run = os.getenv("GITHUB_RUN_ID", "")
        self.attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
        self.commit = os.getenv("GITHUB_SHA", "")
        if not (re.fullmatch(r"[\w.-]+/[\w.-]+", self.repo)
                and re.fullmatch(r"[\w-]+", self.actor)
                and re.fullmatch(r"\d+", self.run)
                and re.fullmatch(r"\d+", self.attempt)
                and re.fullmatch(r"[a-fA-F0-9]{40}", self.commit)
                and self.token):
            raise ReviewUnavailable("Missing or invalid GitHub Actions context.")
        self.path = f"captcha/{self.run}-{self.attempt}.png"
        self.issue = None
        self.image_sha = None

    def api(self, method, suffix, payload=None, missing_ok=False):
        url = f"https://api.github.com/repos/{self.repo}/{suffix}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = request.Request(url, method=method, data=data, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "roboform-human-verification",
        })
        try:
            with request.urlopen(req, timeout=20) as res:
                body = res.read(800000)
                return json.loads(body) if body else {}
        except error.HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            raise ReviewUnavailable(f"GitHub API {method} failed (HTTP {exc.code}).") from None
        except (error.URLError, OSError, ValueError, TimeoutError):
            raise ReviewUnavailable("GitHub API was unavailable.") from None

    def publish(self, image: Path, suggestion: str | None, confidence: str, *,
                ddddocr_hint: str | None = None, ddddocr_enabled: bool = False,
                registration_email: str | None = None,
                email_source: str = "unknown") -> int:
        """Publish the image and open a human review Issue.

        This class owns GitHub I/O. Text rendering and OCR formatting live in
        review_content.py; no prediction is submitted to RoboForm.
        """
        from review_content import render_review

        raw = image.read_bytes()
        if not raw.startswith(PNG_MAGIC) or not 100 <= len(raw) <= 512000:
            raise ReviewUnavailable("Not a valid bounded PNG verification image.")

        try:
            content = render_review(
                image_url=(
                    f"https://raw.githubusercontent.com/{self.repo}/"
                    f"{PREVIEW_BRANCH}/{self.path}"
                ),
                run_url=f"https://github.com/{self.repo}/actions/runs/{self.run}",
                run=self.run,
                attempt=self.attempt,
                actor=self.actor,
                email=registration_email,
                email_source=email_source,
                tesseract_hint=suggestion,
                tesseract_confidence=confidence,
                ddddocr_hint=ddddocr_hint,
                ddddocr_enabled=ddddocr_enabled,
            )
        except ValueError:
            raise ReviewUnavailable("Invalid human review metadata.") from None

        existing = self.api("GET", f"git/ref/heads/{PREVIEW_BRANCH}", missing_ok=True)
        if not existing:
            try:
                self.api("POST", "git/refs", {
                    "ref": f"refs/heads/{PREVIEW_BRANCH}", "sha": self.commit
                })
            except ReviewUnavailable:
                if not self.api("GET", f"git/ref/heads/{PREVIEW_BRANCH}", missing_ok=True):
                    raise

        result = self.api("PUT", f"contents/{self.path}", {
            "message": f"Temporary verification screenshot for run {self.run}",
            "branch": PREVIEW_BRANCH,
            "content": base64.b64encode(raw).decode(),
        })
        self.image_sha = (result.get("content") or {}).get("sha")
        if not self.image_sha:
            raise ReviewUnavailable("Image preview upload failed.")

        issue = self.api("POST", "issues", {
            "title": content.title,
            "body": content.body,
        })
        self.issue = issue.get("number")
        if not isinstance(self.issue, int):
            raise ReviewUnavailable("GitHub Issue creation failed.")

        issue_url = issue.get("html_url", "")
        print("FIREFOX_CAPTCHA_REVIEW_ISSUE:", issue_url)
        if path := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(path).open("a", encoding="utf-8") as out:
                out.write(content.summary.replace("__ISSUE_URL__", issue_url))
        return self.issue

    def wait_for_answer(self, seconds=420):
        if self.issue is None:
            raise ReviewUnavailable("Review Issue has not been created.")
        until = time.monotonic() + min(540, max(30, seconds))
        print("FIREFOX_CAPTCHA_REVIEW_WAITING: waiting for a human comment.")
        while time.monotonic() < until:
            comments = self.api("GET", f"issues/{self.issue}/comments?per_page=100")
            if not isinstance(comments, list):
                raise ReviewUnavailable("Unexpected GitHub comments response.")
            for item in comments:
                user = (item.get("user") or {}).get("login", "")
                if user.casefold() != self.actor.casefold():
                    continue
                match = re.fullmatch(r"/captcha\s+([A-Za-z0-9]{1,12})",
                                    (item.get("body") or "").strip())
                if match:
                    print("FIREFOX_CAPTCHA_REVIEW_ANSWER_RECEIVED: authorized human input.")
                    return match.group(1)
            time.sleep(5)
        raise ReviewUnavailable("Manual response timed out.")

    def finish(self, status: str):
        if self.issue is not None:
            try:
                self.api("POST", f"issues/{self.issue}/comments", {
                    "body": f"Review ended: {status}. Temporary image is being removed."
                })
                self.api("PATCH", f"issues/{self.issue}", {"state": "closed"})
            except ReviewUnavailable:
                print("FIREFOX_CAPTCHA_REVIEW_CLEANUP: unable to close Issue.")
        if self.image_sha:
            try:
                self.api("DELETE", f"contents/{self.path}", {
                    "message": f"Remove temporary image for run {self.run}",
                    "branch": PREVIEW_BRANCH,
                    "sha": self.image_sha,
                })
            except ReviewUnavailable:
                print("FIREFOX_CAPTCHA_REVIEW_CLEANUP: image removal failed.")
