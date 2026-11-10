"""Pure, testable rendering for a human-operated Firefox verification Issue.

No GitHub API calls, browser interaction, image processing or submission.
OCR predictions are unverified hints and never supplied to the form.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

EMAIL = re.compile(
    r"[a-z0-9][a-z0-9._%+-]*@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}",
    re.ASCII,
)
HINT = re.compile(r"[A-Za-z0-9]{1,12}", re.ASCII)
CONFIDENCE = re.compile(r"N/A|\d{1,3}(?:\.\d{1,2})?", re.ASCII)

EMAIL_SOURCE = {
    "generated": "Tự tạo khi bỏ trống email",
    "provided": "Email nhập khi chạy workflow",
    "unknown": "Chưa xác định",
}


@dataclass(frozen=True)
class ReviewContent:
    title: str
    body: str
    summary: str


def normalized_registration_email(value: str | None) -> str | None:
    """Fail closed rather than displaying arbitrary, possibly unsafe text."""
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > 254
        or ".." in value
        or EMAIL.fullmatch(value) is None
    ):
        raise ValueError("Invalid registration email supplied to review renderer")
    return value


def safe_hint(value: str | None) -> str | None:
    return value if isinstance(value, str) and HINT.fullmatch(value) else None


def safe_confidence(value: str) -> str:
    return value if isinstance(value, str) and CONFIDENCE.fullmatch(value) else "N/A"


def comparison_note(first: str | None, second: str | None) -> str:
    if first is None or second is None:
        return "Chưa đủ hai gợi ý hợp lệ để đối chiếu."
    if first == second:
        return "Hai mô hình trả cùng một chuỗi nhưng vẫn cần đối chiếu ảnh."
    if len(first) != len(second):
        return (
            f"Khác số ký tự (Tesseract {len(first)}, ddddocr {len(second)}); "
            "không thể suy đoán tự động."
        )
    if first.casefold() == second.casefold():
        positions = ", ".join(
            str(index + 1)
            for index, (left, right) in enumerate(zip(first, second))
            if left != right
        )
        return (
            f"Cùng ký tự khi bỏ qua hoa/thường; khác cách viết ở vị trí {positions}. "
            "Không tự chuyển chữ hoa thành chữ thường."
        )
    return "Hai mô hình nhận dạng khác nhau; cần đọc lại ảnh và kiểm tra hoa/thường."


def command_to_copy(candidate: str | None) -> str:
    """GitHub renders fenced blocks with a native copy icon."""
    hint = safe_hint(candidate)
    if hint is None:
        return ""
    return "~~~text\n/captcha " + hint + "\n~~~"


def render_review(
    *,
    image_url: str,
    run_url: str,
    run: str,
    attempt: str,
    actor: str,
    email: str | None = None,
    email_source: str = "unknown",
    tesseract_hint: str | None = None,
    tesseract_confidence: str = "N/A",
    ddddocr_hint: str | None = None,
    ddddocr_enabled: bool = False,
) -> ReviewContent:
    email = normalized_registration_email(email)
    tesseract_hint = safe_hint(tesseract_hint)
    ddddocr_hint = safe_hint(ddddocr_hint) if ddddocr_enabled else None
    confidence = safe_confidence(tesseract_confidence)
    source = email_source if email_source in EMAIL_SOURCE else "unknown"
    display_email = email or "Chưa xác định"
    hint_fallback = (
        "OCR có phát hiện chữ nhưng kết quả bị lọc vì định dạng không hợp lệ"
        if confidence != "N/A" else "OCR không phát hiện được nhóm ký tự"
    )

    sections = [
        "## RoboForm Firefox — xác minh CAPTCHA thủ công",
        "**Email đang đăng ký:** " + display_email + "\n\n"
        "**Nguồn email:** " + EMAIL_SOURCE[source],
        "![Ảnh CAPTCHA thực tế](" + image_url + ")",
        "**OCR gợi ý (CHƯA XÁC MINH) — Tesseract:** "
        + (tesseract_hint or hint_fallback) + "\n\n"
        "**Độ tin cậy OCR (Tesseract):** " + confidence,
    ]
    if tesseract_hint is not None:
        sections.append(
            "**Copy cú pháp từ Tesseract (đối chiếu ảnh trước khi gửi):**\n\n"
            + command_to_copy(tesseract_hint)
        )

    if ddddocr_enabled:
        sections.append(
            "**ddddocr gợi ý (CHƯA XÁC MINH):** "
            + (ddddocr_hint or "Không có gợi ý hợp lệ") + "\n\n"
            "**Độ tin cậy ddddocr:** N/A (API nhận dạng không cung cấp)"
        )
        sections.append(
            "**Đối chiếu hai OCR:** "
            + comparison_note(tesseract_hint, ddddocr_hint)
            + "\n\n"
            "**Chú ý:** ddddocr có thể nhầm chữ hoa và chữ thường. "
            "Không có bước tự sửa hoa/thường."
        )
        if ddddocr_hint is not None:
            sections.append(
                "**Copy cú pháp từ ddddocr (sửa hoa/thường nếu ảnh khác):**\n\n"
                + command_to_copy(ddddocr_hint)
            )

    sections.extend([
        "**Tự đọc lại ảnh trước khi gửi.** Chỉ người kích hoạt workflow "
        f"(@{actor}) mới có thể gửi mã xác minh bằng comment. "
        "Bạn có thể sửa văn bản đã copy để khớp ảnh.",
        "**Mẫu cú pháp nhập thủ công:**\n\n~~~text\n/captcha ABC123\n~~~",
        "Thay ABC123 bằng mã do bạn đọc được. Không gửi mật khẩu hoặc thông tin nhạy cảm. "
        "Ảnh và email đang hiển thị trong Issue công khai. "
        "Ảnh sẽ được gỡ khỏi nhánh preview khi phiên kết thúc.",
        "[Xem workflow](" + run_url + ")",
    ])
    body = "\n\n".join(sections) + "\n"
    title = f"[Firefox verification] {display_email} — run {run}/{attempt}"

    summary_lines = [
        "\n### Firefox verification — manual review",
        "- Registration email: " + display_email,
        "- Email source: " + source,
        "- [View original image and OCR suggestion in GitHub Issue](__ISSUE_URL__)",
        "- Unverified Tesseract hint: "
        + (tesseract_hint or "no safe hint") + "; confidence: " + confidence,
    ]
    if ddddocr_enabled:
        summary_lines.append(
            "- Unverified ddddocr hint: "
            + (ddddocr_hint or "no safe hint") + "; confidence unavailable"
        )
    return ReviewContent(title, body, "\n".join(summary_lines) + "\n")
