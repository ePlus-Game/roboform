# RoboForm registration — Chromium and Firefox

[![Chromium registration](https://img.shields.io/badge/Chromium-Register-238636?style=for-the-badge&logo=googlechrome&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml)
[![Firefox registration](https://img.shields.io/badge/Firefox-Register-238636?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/register-firefox.yml)

There are **two independent, manually triggered real-registration workflows**. Choose **one** browser for a new account. Both require a 16+ character `ROBOFORM_MASTER_PASSWORD` repository secret, use `David Nguyen` as the default full name, and record an entry **only after RoboForm explicitly confirms account creation and the email matches**. Neither workflow bypasses human verification. **Do not run both workflows for the same email.**

## Node.js version (CI and registration)

- **Node.js 26 LTS (Lithium)** is the latest stable/LTS line as of 2026-11-09; the latest patch then is **26.13.0**. Node.js 27 is still **Alpha** and is not used for registration.
- The single source of truth is [`.nvmrc`](.nvmrc) containing `26`. Every Node-powered GitHub Actions workflow uses `actions/setup-node@v7` with `node-version-file: .nvmrc` and `check-latest: true`, so it selects the newest available **26.x** patch without manual changes.
- The workflows use `actions/checkout@v7` and `actions/setup-python@v7` to avoid the deprecated Node.js 20 runtime in previous action versions. These actions' internal runtime is separate from the Node.js version used to execute project scripts.
- On a development machine, run `nvm use` (or install Node.js 26 LTS) and `npm test`. The `package.json` engine range excludes prerelease Node 27.

## Which browser is currently used?

| Workflow | Browser / technology | Purpose | What success means |
| --- | --- | --- | --- |
| [`record-confirmed.yml`](.github/workflows/record-confirmed.yml) | **Chromium + Playwright**, RoboForm Chrome Web Store extension | Manual-triggered attempt to register a real account | Only RoboForm's confirmed success screen **and exact email match** allow a verified CSV record |
| [`register-firefox.yml`](.github/workflows/register-firefox.yml) | **Firefox + Selenium**, RoboForm Mozilla Add-ons extension | Independent real signup attempt, with a preselected Privacy checkbox that the operator can uncheck | Only RoboForm's confirmed success screen **and exact email match** allow a verified CSV record |
| [`ci.yml`](.github/workflows/ci.yml) | **Chromium + Playwright** (plus Node tests) | Check extension signup UI and validation without submission | Passing smoke checks **does not** mean an account was created |
| [`firefox-smoke.yml`](.github/workflows/firefox-smoke.yml) | **Firefox + Selenium**, RoboForm official Mozilla Add-ons XPI | Separate browser feasibility test; no signup, credentials, or CSV write | Firefox extension starts; human onboarding may still be required |

**Chromium and Firefox are separate workflows:** `record-confirmed.yml` retains the existing Chromium implementation; `register-firefox.yml` adds a Firefox-specific implementation. The `firefox-smoke.yml` check is separate and **never registers a real account**.

### Firefox experiment (merged PR #9)

On November 9, 2026, [Firefox CI run #42569477955](https://github.com/ePlus-Game/roboform/actions/runs/42569477955) successfully installed Firefox **159.0.1**, downloaded/installed RoboForm Firefox extension **9.9.9.1**, and opened its internal start page. The first screen was **Privacy**, asking the user to consent to data processing. The CI test identified this requirement but **did not accept it on the user's behalf**, access the signup form, or submit an account.

To re-run this **safe, non-registration** experiment, open [Firefox RoboForm smoke (no registration)](https://github.com/ePlus-Game/roboform/actions/workflows/firefox-smoke.yml) → **Run workflow** on `main`. Its `FIREFOX_PRIVACY_CONSENT_REQUIRED` message identifies the onboarding gate; a green workflow run is **not proof of registration**.

**The Firefox registration workflow is different:** the manual dispatch includes a required **privacy_consent** checkbox. The checkbox is **checked by default**. Review the agreement and **uncheck it if you do not agree**. Selenium clicks RoboForm's displayed **Accept** control only when the input remains checked, then attempts to fill the real Sign Up form. The browser may still require human CAPTCHA or Turnstile verification, in which case the action stops with failure and writes no record. The Firefox registration path is **experimental** and has not been proven to create an account unattended.

To continue past Privacy in Firefox, use an interactive Firefox window with the [official RoboForm add-on](https://addons.mozilla.org/en-US/firefox/addon/roboform/), read the agreement and consent personally if you choose, then complete any required security verification. Hosted, unattended Actions cannot assume privacy consent or solve human-only challenges.



## Current limitation: RoboForm human verification

The actual GitHub Actions registration job may **not** be able to create an account unattended. In the live registration run on 2026-11-09, all four form inputs passed basic HTML validity checks, but the **Create Account** button remained disabled. A no-submission smoke test confirmed the presence of RoboForm's **Cloudflare Turnstile** human-verification widget. This is a deliberate interactive security requirement; this workflow does **not** attempt to bypass it.

When Turnstile blocks submission, the registration job fails immediately with an explicit error and **does not** write `data/registrations.csv`. A passing smoke test validates the extension UI and challenge detection, **not** successful account creation.

**To create an account when human verification is required:** use RoboForm's [official signup flow](https://www.roboform.com/) in your browser and complete its security verification yourself. Do not enter your Master Password in GitHub issue comments, logs, PRs or workflow inputs. If you already registered manually, do not rerun the automation just to make a CSV entry: a verified receipt must reflect a successful registration, not an assumption.

## Setup (once)

1. Go to **Settings → Secrets and variables → Actions → New repository secret**.
2. Create a secret named **`ROBOFORM_MASTER_PASSWORD`** containing a strong, unique Master Password (16+ characters) for **this** account. Never type the password into the Actions email input or commit it to Git. Make sure you personally retain it securely; RoboForm cannot simply reset encrypted vault contents without the recovery setup.
3. Choose [**Register — Chromium**](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml) or [**Register — Firefox**](https://github.com/ePlus-Game/roboform/actions/workflows/register-firefox.yml). Select **Run workflow** on `main`, enter **email** and optionally edit **full_name** (defaults to `David Nguyen`).
4. **Firefox only:** read [RoboForm's Privacy Policy](https://www.roboform.com/privacy-policy) and the Firefox add-on's Privacy screen. **privacy_consent** starts checked for convenience; uncheck it if you do not agree. When unchecked, the Firefox workflow fails before launching the browser. If RoboForm requests further human verification, the run stops without recording a signup.

**Use a distinct Master Password for each account.** If you register another email, change the secret first. The workflow handles one account per manually triggered run; no schedules or automatic retries.

### Troubleshooting: master password validation

The workflow now checks the configured secret **before** installing dependencies or Playwright, without printing the secret value.

- **Missing or blank**: check that the repository secret is named exactly `ROBOFORM_MASTER_PASSWORD` in **Settings → Secrets and variables → Actions → Repository secrets**. This workflow uses a repository secret (not an environment secret).
- **Shorter than 16 characters**: click the pencil icon next to the existing repository secret and replace its **value** with a unique 16+ character master password. GitHub shows the secret name, not its saved value or length.
- After updating a secret, trigger a **new Run workflow** from `main`; inspect the **Validate RoboForm master password** step. The password value is never logged.

If the preflight passes, later signup errors concern browser registration or RoboForm verification, not this secret-length check.

## Chromium registration flow

- GitHub Actions runs **Node.js 26 LTS** and Playwright's Chromium, not a fake CSV logger.
- The runner downloads the RoboForm browser extension from **Chrome Web Store**, verifies its manifest key hashes to extension ID `pnlccmojcmeohlpggmfnbbiapkmbliob`, then launches it in a disposable browser profile. We don't redistribute RoboForm binaries or upload account credentials as artifacts.
- Playwright opens `start-page.html`, clicks **Sign Up**, fills email + Master Password + password confirmation + full name, then clicks **Create Account**.
- Only when the extension displays **Account created successfully** **and** its confirmation email exactly matches the requested email does it write to `data/registrations.csv`.
- The file stores `email,registered_at_utc,registered_date_vn,verification_method`. New verified rows use `signup_ui_success`. Earlier `unverified` rows are upgraded **only after confirmed success**, not blocked as duplicates. No password is saved.
- Errors, mismatches, CAPTCHA, OTP/new-device verification, or missing success screen cause the workflow to **fail without a success record**. Check its logs and the job summary to diagnose the point of failure.

## Firefox registration flow (experimental)

- Trigger [`register-firefox.yml`](.github/workflows/register-firefox.yml) manually with the account email, full name and the **preselected privacy_consent checkbox**, which can be unchecked.
- The runner starts Firefox and Selenium, downloads the official Mozilla-signed RoboForm Firefox extension, then opens its internal start page.
- When the submitted privacy_consent input is true, Selenium clicks the extension's own **Accept** button on the Privacy onboarding screen; it does not skip this screen.
- If the Sign Up form is available, it fills the email, Master Password, password confirmation and full name and tries to submit using the visible **Create Account** button.
- **No CAPTCHA/Turnstile solving or bypass:** if human verification blocks the button or submission, the job fails. Do not treat a green install/smoke test as proof of successful signup.
- After RoboForm displays its expected success message **and** confirms the exact requested email, the workflow writes a `firefox_signup_ui_success` entry to `data/registrations.csv`. The Chromium flow retains `signup_ui_success` for backwards compatibility.
- The two registration workflows share the same concurrency group and CSV deduplication. Use a unique Master Password for each new account. Do not replay HAR authentication requests, upload sensitive HAR files or use stale sessions.

## Why an OTP may not arrive

Previously this repository's action only appended an **unverified email** and **never submitted an account registration**. That successful GitHub run did not mean RoboForm sent an email.

RoboForm's documentation states email OTP is usually a **device authorization method for sign-in**; it is not a guarantee that signup itself generates OTP. RoboForm also documents **human security verification (CAPTCHA)** during account creation.

A hosted headless CI runner **cannot reliably complete an interactive challenge**. This project does not solve or bypass CAPTCHA. Even a Playwright signup may stop before the server accepts the account. A human may need to complete the official RoboForm signup UI instead. Do not assume that a missing OTP is a deliverability problem until the signup itself has been confirmed.

## Verification & limitations

`npm test` runs CSV, dedupe and input tests. CI's Chromium **smoke-extension** job downloads the extension and opens the Sign Up form with Playwright **without submitting a real account**; it can also detect that Turnstile prevents submission. The **firefox-extension** job separately tests Mozilla's extension and Firefox onboarding, also without registration. **Both real-registration jobs** require an operator-supplied email and a GitHub Actions secret, and Firefox requires its Privacy checkbox to remain checked. **Neither smoke test can prove that RoboForm created an account.**

The signup selectors were derived from user-provided RoboForm extension **v10.0.2.0**; live versions might have changed. For safety, no browser screenshots or traces containing credentials are uploaded. The repository and its logs should remain private.

References: [RoboForm signup help](https://help.roboform.com/hc/en-us/articles/115005962708-RoboForm-Windows-Installation-and-setup) · [RoboForm OTP documentation](https://help.roboform.com/hc/en-us/articles/115005043767-How-to-enable-One-Time-Password-OTP-via-email-or-SMS) · [Playwright extensions](https://playwright.dev/docs/chrome-extensions) · [Selenium Firefox](https://www.selenium.dev/documentation/webdriver/browsers/firefox/) · [RoboForm on Mozilla Add-ons](https://addons.mozilla.org/en-US/firefox/addon/roboform/).

## Firefox signup workflow: same-run OCR and human readability report

The manually started [`register-firefox.yml`](.github/workflows/register-firefox.yml) now performs the previously independent OCR/Selenium checks and publishes the **offline human-readability page in the same `signup-firefox` job**, before submitting an actual RoboForm signup. No separate workflow dispatch, local runner or service account is required.

Order: validate consent and password → install Firefox, Selenium, CairoSVG, Pillow and Tesseract → run source tests → run read-only OCR on the committed SVG fixture → test the local Selenium form → generate and smoke-test the human readability page → upload **`svg-human-readability-<run_id>`** artifact → execute existing RoboForm signup → write CSV only after the existing UI success check.

The artifact is created **before the signup attempt**, so it remains available for users to review even when RoboForm requires human verification and the signup is not confirmed. Its HTML embeds only the static test fixture; it does **not** capture the live registration CAPTCHA, receive participants' answers during the workflow run, or pass OCR output to the actual registration form. Browser testing of the offline review page is nonblocking for signup. For an actual human legibility measurement, download the artifact, give it to human testers, and collect their locally saved JSON responses afterwards.

This is one manually triggered **registration workflow** containing several sequential test steps, not a new continuously running registration workflow. The independent OCR workflow remains for PR testing without real signups.

## Human readability test for the original user-supplied SVG

To check whether **people** can read the actual 165 × 50 image (not whether OCR can), run the existing **Tesseract OCR + Selenium form — single flow** workflow via `workflow_dispatch`. The job includes all existing OCR checks and additionally generates `dist/human-readability-review.html`, smoke-tests it in Firefox, and uploads an artifact named **`svg-human-readability`**.

Download that artifact from the GitHub Actions run's **Artifacts** section, extract it, and open `human-readability-review.html` in a browser. Ask several testers to click **Bắt đầu**, read the exact original SVG, type the characters they perceive, rate readability and confidence, and download their individual JSON reports. The page works offline: there are no form submissions to a server and no credentials or RoboForm browser sessions. Share the HTML file with testers; collect their JSON responses separately.

The page contains **no correct-answer label** so participants cannot see it by inspecting the HTML. To calculate objective character/error rates, the image designer needs to supply the actual intended text separately after responses are collected. Without that ground truth, the survey supports self-reported readability, transcription consistency and elapsed time only; CI success does **not** demonstrate that human participants can correctly read it.

## Single GitHub Actions OCR + Selenium demo

The same [Tesseract workflow](.github/workflows/tesseract-ocr-smoke.yml) runs **one `test-ocr` job**, with these steps in sequence: install Firefox, Tesseract, CairoSVG, Pillow and Selenium; run the baseline text recognition; inspect the user-provided SVG offline; then run an end-to-end Selenium Firefox test against a **local HTML form**.

The demo script [`scripts/test-ocr-form-demo.py`](scripts/test-ocr-form-demo.py) embeds its own plain-text SVG sample, reads it from the local browser page, converts it to PNG, recognizes `HELLO2026` with Tesseract, submits the result to the local form and requires `OCR_FORM_E2E_PASS`. It does **not** interact with RoboForm signup or solve live CAPTCHA challenges.

## Standalone Tesseract OCR smoke test

The optional [Tesseract OCR smoke workflow](.github/workflows/tesseract-ocr-smoke.yml) runs entirely in GitHub Actions and performs **two separate offline OCR checks**:

1. A generated plain-text SVG with known text `HELLO 2026`; the test fails if Tesseract misreads this baseline.
2. The exact **user-provided `Untitled.svg`** stored as [`test/fixtures/user-provided-ocr.svg`](test/fixtures/user-provided-ocr.svg), with five path glyphs and no embedded text labels. CairoSVG renders it, Pillow composites it onto white and enlarges it 6×, and Tesseract's raw result is printed as `OCR_USER_IMAGE_OUTPUT`. There is no known ground-truth label, so this second observation does not fail based on text mismatch.

No login, network submission, RoboForm browser automation, HAR file, password or registration takes place. This standalone OCR experiment does **not** automate RoboForm human verification. The signup workflows retain their existing protection and require manual completion of security challenges.
