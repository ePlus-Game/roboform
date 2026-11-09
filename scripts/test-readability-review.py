"""Smoke test the offline human-readability page; never attempt a real signup."""
from __future__ import annotations

import base64
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "dist" / "human-readability-review.html"
FIXTURE = ROOT / "test" / "fixtures" / "user-provided-ocr.svg"


def main() -> None:
    assert PAGE.is_file(), "HTML review artifact was not generated"
    options = webdriver.FirefoxOptions()
    options.add_argument("-headless")
    driver = webdriver.Firefox(options=options)
    try:
        driver.get(PAGE.resolve().as_uri())
        assert driver.title.startswith("Đánh giá khả năng đọc ký tự SVG")
        assert not driver.find_element(By.ID, "trial").is_displayed()
        driver.find_element(By.ID, "begin").click()
        assert driver.find_element(By.ID, "trial").is_displayed()
        image = driver.find_element(By.ID, "svg-sample")
        source = image.get_attribute("src")
        assert source.startswith("data:image/svg+xml;base64,")
        assert base64.b64decode(source.split(",", 1)[1], validate=True) == FIXTURE.read_bytes()
        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.ID, "svg-sample").get_property("naturalWidth") == 165
        )
        driver.find_element(By.ID, "answer").send_keys("manual-reader-test")
        Select(driver.find_element(By.ID, "readable")).select_by_value("yes")
        Select(driver.find_element(By.ID, "confidence")).select_by_value("4")
        driver.find_element(By.ID, "zoom").click()
        assert image.get_property("width") == 330
        driver.find_element(By.CSS_SELECTOR, "#response-form button[type=submit]").click()
        WebDriverWait(driver, 10).until(
            lambda d: "Đã tạo báo cáo JSON" in d.find_element(By.ID, "status").text
        )
        print("HUMAN_READABILITY_SMOKE_PASS")
        print("HUMAN_READABILITY_FIXTURE_VERIFIED: exact checked-in SVG shown in Firefox")
        print("HUMAN_READABILITY_NOTE: browser UI tested; humans must supply real responses")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
