#!/usr/bin/env python3
"""Build a self-contained, offline human legibility study from the checked-in SVG.

The page has no network requests, no hidden answer, and no RoboForm interaction.
Human participants transcribe what they see and download their own JSON report.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "test" / "fixtures" / "user-provided-ocr.svg"
SVG_NS = "{http://www.w3.org/2000/svg}"

HTML = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>Đánh giá khả năng đọc ký tự SVG — bài kiểm thử độc lập</title>
<style>
:root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;background:#f5f7fb;color:#182334;line-height:1.5}
main{max-width:740px;margin:40px auto;padding:0 20px}
article{background:#fff;border:1px solid #d7deea;border-radius:16px;padding:28px;box-shadow:0 10px 26px #18233410}
h1{font-size:1.65rem;line-height:1.2;margin-top:0}
p{margin:12px 0;color:#46556a}
label{display:block;font-weight:650;margin:20px 0 7px}
input,select,textarea{width:100%;padding:12px;border-radius:8px;border:1px solid #96a6b9;font:inherit;color:#182334;background:white}
textarea{resize:vertical;min-height:76px}
button{padding:12px 17px;border:0;border-radius:8px;font:inherit;font-weight:650;cursor:pointer;background:#1765c1;color:white;margin:12px 12px 0 0}
button.secondary{background:#e8edf5;color:#233449}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #ffaf3c;outline-offset:2px}
.figure{margin:20px 0;padding:22px;background:#edf1f8;border:1px dashed #92a3bc;border-radius:10px;overflow:auto}
.figure img{display:block;object-fit:contain;image-rendering:auto}
.note{font-size:.9rem;color:#53627c}
#status{font-weight:650;min-height:28px}
[hidden]{display:none!important}
@media(max-width:540px){main{margin:18px auto}article{padding:18px}}
@media(prefers-color-scheme:dark){body{background:#111b2a;color:#e5edf8}article{background:#1e293a;border-color:#415168}p,.note{color:#b8c8db}.figure{background:#29384b;border-color:#687c95}}
</style>
</head>
<body>
<main>
<article>
<h1>Kiểm thử khả năng đọc hình SVG</h1>
<p>Đây là bài kiểm thử với <strong>ảnh SVG gốc</strong>, kích thước 165 × 50 px. Không có mã đúng hay lời giải được cung cấp trên trang.</p>
<p>Hãy nhờ người tham gia đọc ký tự theo mắt thường và nhập lại chính xác những gì họ thấy. Mỗi người nên thực hiện độc lập, không trao đổi đáp án.</p>
<p class="note">Trang chạy hoàn toàn ngoại tuyến. Không truyền kết quả lên máy chủ. Khi hoàn tất, trình duyệt tải về một tệp JSON để gửi cho người phụ trách kiểm thử.</p>
<button type="button" id="begin">Bắt đầu lượt thử</button>
<section id="trial" hidden>
<div class="figure">
<img id="svg-sample" src="data:image/svg+xml;base64,__SVG_BASE64__" width="165" height="50" alt="Ảnh mẫu gồm các ký tự biến dạng">
</div>
<button class="secondary" id="zoom" type="button">Phóng to 2× (tuỳ chọn)</button>
<form id="response-form">
<label for="answer">Các ký tự bạn nhìn thấy</label>
<input id="answer" name="answer" type="text" maxlength="20" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="answer-note">
<p id="answer-note" class="note">Giữ nguyên chữ hoa/thường nếu có. Để trống nếu không thể đọc.</p>
<label for="readable">Bạn có đọc được hình không?</label>
<select id="readable" required>
<option value="">Chọn một câu trả lời</option>
<option value="yes">Có</option>
<option value="unsure">Không chắc chắn</option>
<option value="no">Không</option>
</select>
<label for="confidence">Mức độ tự tin (1 = rất thấp, 5 = rất cao)</label>
<select id="confidence" required>
<option value="">Chọn mức độ</option>
<option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option>
</select>
<label for="feedback">Góp ý (không bắt buộc)</label>
<textarea id="feedback" maxlength="500" placeholder="Ví dụ: chữ thứ 2 quá giống chữ l..."></textarea>
<button type="submit">Hoàn tất và tải JSON</button>
</form>
</section>
<p id="status" role="status" aria-live="polite"></p>
<p class="note">Ảnh tham chiếu SHA-256: <code>__SVG_SHA256__</code>. Đây là phép đo khả năng đọc của con người, không phải kiểm thử giải mã tự động.</p>
</article>
</main>
<script>
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let began = null;
  let zoomed = false;
  $("begin").addEventListener("click", () => {
    $("begin").hidden = true;
    $("trial").hidden = false;
    began = performance.now();
    $("answer").focus();
  });
  $("zoom").addEventListener("click", () => {
    zoomed = !zoomed;
    $("svg-sample").width = zoomed ? 330 : 165;
    $("svg-sample").height = zoomed ? 100 : 50;
    $("zoom").textContent = zoomed ? "Trở về kích thước gốc" : "Phóng to 2× (tuỳ chọn)";
  });
  $("response-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const text = $("answer").value.trim();
    const readable = $("readable").value;
    if (readable === "yes" && !text) {
      $("status").textContent = "Vui lòng nhập ký tự bạn nhìn thấy hoặc chọn không đọc được.";
      $("answer").focus();
      return;
    }
    const report = {
      kind: "human-svg-readability-v1",
      fixture: "test/fixtures/user-provided-ocr.svg",
      fixture_sha256: "__SVG_SHA256__",
      transcribed: text,
      readable: readable,
      confidence: Number($("confidence").value),
      elapsed_ms: Math.round(performance.now() - began),
      zoomed: zoomed,
      feedback: $("feedback").value.trim(),
      submitted_at: new Date().toISOString()
    };
    const blob = new Blob([JSON.stringify(report, null, 2) + "\n"], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "svg-readability-response-" + new Date().toISOString().replace(/[:.]/g,"-") + ".json";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $("response-form").hidden = true;
    $("zoom").hidden = true;
    $("status").textContent = "Đã tạo báo cáo JSON. Hãy gửi tệp đó cho người phụ trách kiểm thử.";
  });
})();
</script>
</body>
</html>
"""


def build(output: Path) -> None:
    svg = FIXTURE.read_bytes()
    if not (0 < len(svg) <= 100_000):
        raise ValueError("SVG fixture is empty or too large")
    root = ET.fromstring(svg)
    if root.tag != SVG_NS + "svg":
        raise ValueError("Expected a standalone SVG root")
    allowed = {SVG_NS + name for name in ("svg", "g", "path", "style")}
    for elem in root.iter():
        if elem.tag not in allowed:
            raise ValueError(f"Disallowed SVG element: {elem.tag}")
        for key in elem.attrib:
            if key.startswith("on") or key.endswith("}href"):
                raise ValueError("Dynamic SVG attribute is not supported")
    if sum(e.tag == SVG_NS + "path" for e in root.iter()) != 5:
        raise ValueError("Unexpected image fixture: should contain five path glyphs")
    sha256 = hashlib.sha256(svg).hexdigest()
    page = HTML.replace("__SVG_BASE64__", base64.b64encode(svg).decode("ascii"))
    page = page.replace("__SVG_SHA256__", sha256)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    if page.count("data:image/svg+xml;base64,") != 1 or "__SVG_" in page:
        raise ValueError("Offline HTML embedding failed")
    print(f"HUMAN_READABILITY_HTML_READY: {output}")
    print(f"HUMAN_READABILITY_FIXTURE_SHA256: {sha256}")
    print("HUMAN_READABILITY_MODE: offline sample survey")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist/human-readability-review.html"))
    options = parser.parse_args()
    build(options.output)
