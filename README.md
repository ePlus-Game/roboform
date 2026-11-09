# RoboForm account registration — GitHub Actions + Playwright

[![Register via GitHub Actions](https://img.shields.io/badge/Playwright-Register_RoboForm-238636?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml)

[**Open the signup workflow**](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml) — then select **Run workflow**.

## Which browser is currently used?

| Workflow | Browser / technology | Purpose | What success means |
| --- | --- | --- | --- |
| [`record-confirmed.yml`](.github/workflows/record-confirmed.yml) | **Chromium + Playwright**, RoboForm Chrome Web Store extension | Manual-triggered attempt to register a real account | Only RoboForm's confirmed success screen **and exact email match** allow a verified CSV record |
| [`ci.yml`](.github/workflows/ci.yml) | **Chromium + Playwright** (plus Node tests) | Check extension signup UI and validation without submission | Passing smoke checks **does not** mean an account was created |
| [`firefox-smoke.yml`](.github/workflows/firefox-smoke.yml) | **Firefox + Selenium**, RoboForm official Mozilla Add-ons XPI | Separate browser feasibility test; no signup, credentials, or CSV write | Firefox extension starts; human onboarding may still be required |

**Default registration remains Chromium.** Merging the Firefox experiment did **not** switch `npm run register` or `record-confirmed.yml` to Firefox.

### Firefox experiment (merged PR #9)

On November 9, 2026, [Firefox CI run #42569477955](https://github.com/ePlus-Game/roboform/actions/runs/42569477955) successfully installed Firefox **159.0.1**, downloaded/installed RoboForm Firefox extension **9.9.9.1**, and opened its internal start page. The first screen was **Privacy**, asking the user to consent to data processing. The CI test identified this requirement but **did not accept it on the user's behalf**, access the signup form, or submit an account.

To re-run this **safe, non-registration** experiment, open [Firefox RoboForm smoke (no registration)](https://github.com/ePlus-Game/roboform/actions/workflows/firefox-smoke.yml) → **Run workflow** on `main`. Its `FIREFOX_PRIVACY_CONSENT_REQUIRED` message identifies the onboarding gate; a green workflow run is **not proof of registration**.

To continue past Privacy in Firefox, use an interactive Firefox window with the [official RoboForm add-on](https://addons.mozilla.org/en-US/firefox/addon/roboform/), read the agreement and consent personally if you choose, then complete any required security verification. Hosted, unattended Actions cannot assume privacy consent or solve human-only challenges.



## Current limitation: RoboForm human verification

The actual GitHub Actions registration job may **not** be able to create an account unattended. In the live registration run on 2026-11-09, all four form inputs passed basic HTML validity checks, but the **Create Account** button remained disabled. A no-submission smoke test confirmed the presence of RoboForm's **Cloudflare Turnstile** human-verification widget. This is a deliberate interactive security requirement; this workflow does **not** attempt to bypass it.

When Turnstile blocks submission, the registration job fails immediately with an explicit error and **does not** write `data/registrations.csv`. A passing smoke test validates the extension UI and challenge detection, **not** successful account creation.

**To create an account when human verification is required:** use RoboForm's [official signup flow](https://www.roboform.com/) in your browser and complete its security verification yourself. Do not enter your Master Password in GitHub issue comments, logs, PRs or workflow inputs. If you already registered manually, do not rerun the automation just to make a CSV entry: a verified receipt must reflect a successful registration, not an assumption.

## Setup (once)

1. Go to **Settings → Secrets and variables → Actions → New repository secret**.
2. Create a secret named **`ROBOFORM_MASTER_PASSWORD`** containing a strong, unique Master Password (16+ characters) for **this** account. Never type the password into the Actions email input or commit it to Git. Make sure you personally retain it securely; RoboForm cannot simply reset encrypted vault contents without the recovery setup.
3. Open the registration workflow link above, enter an **email** and optionally edit **full_name** (defaults to `David Nguyen`), then choose **Run workflow**. No `I CONFIRM` field. If RoboForm requires human verification, this unattended attempt will stop without recording a signup.

**Use a distinct Master Password for each account.** If you register another email, change the secret first. The workflow handles one account per manually triggered run; no schedules or automatic retries.

### Troubleshooting: master password validation

The workflow now checks the configured secret **before** installing dependencies or Playwright, without printing the secret value.

- **Missing or blank**: check that the repository secret is named exactly `ROBOFORM_MASTER_PASSWORD` in **Settings → Secrets and variables → Actions → Repository secrets**. This workflow uses a repository secret (not an environment secret).
- **Shorter than 16 characters**: click the pencil icon next to the existing repository secret and replace its **value** with a unique 16+ character master password. GitHub shows the secret name, not its saved value or length.
- After updating a secret, trigger a **new Run workflow** from `main`; inspect the **Validate RoboForm master password** step. The password value is never logged.

If the preflight passes, later signup errors concern browser registration or RoboForm verification, not this secret-length check.

## What actually happens

- GitHub Actions runs **Node.js 26 LTS** and Playwright's Chromium, not a fake CSV logger.
- The runner downloads the RoboForm browser extension from **Chrome Web Store**, verifies its manifest key hashes to extension ID `pnlccmojcmeohlpggmfnbbiapkmbliob`, then launches it in a disposable browser profile. We don't redistribute RoboForm binaries or upload account credentials as artifacts.
- Playwright opens `start-page.html`, clicks **Sign Up**, fills email + Master Password + password confirmation + full name, then clicks **Create Account**.
- Only when the extension displays **Account created successfully** **and** its confirmation email exactly matches the requested email does it write to `data/registrations.csv`.
- The file stores `email,registered_at_utc,registered_date_vn,verification_method`. New verified rows use `signup_ui_success`. Earlier `unverified` rows are upgraded **only after confirmed success**, not blocked as duplicates. No password is saved.
- Errors, mismatches, CAPTCHA, OTP/new-device verification, or missing success screen cause the workflow to **fail without a success record**. Check its logs and the job summary to diagnose the point of failure.

## Why an OTP may not arrive

Previously this repository's action only appended an **unverified email** and **never submitted an account registration**. That successful GitHub run did not mean RoboForm sent an email.

RoboForm's documentation states email OTP is usually a **device authorization method for sign-in**; it is not a guarantee that signup itself generates OTP. RoboForm also documents **human security verification (CAPTCHA)** during account creation.

A hosted headless CI runner **cannot reliably complete an interactive challenge**. This project does not solve or bypass CAPTCHA. Even a Playwright signup may stop before the server accepts the account. A human may need to complete the official RoboForm signup UI instead. Do not assume that a missing OTP is a deliverability problem until the signup itself has been confirmed.

## Verification & limitations

`npm test` runs CSV, dedupe and input tests. CI's Chromium **smoke-extension** job downloads the extension and opens the Sign Up form with Playwright **without submitting a real account**; it can also detect that Turnstile prevents submission. The **firefox-extension** job separately tests Mozilla's extension and Firefox onboarding, also without registration. The real Chromium registration job requires an operator-supplied email and a GitHub Actions secret. **Neither smoke test can prove that RoboForm created an account.**

The signup selectors were derived from user-provided RoboForm extension **v10.0.2.0**; live versions might have changed. For safety, no browser screenshots or traces containing credentials are uploaded. The repository and its logs should remain private.

References: [RoboForm signup help](https://help.roboform.com/hc/en-us/articles/115005962708-RoboForm-Windows-Installation-and-setup) · [RoboForm OTP documentation](https://help.roboform.com/hc/en-us/articles/115005043767-How-to-enable-One-Time-Password-OTP-via-email-or-SMS) · [Playwright extensions](https://playwright.dev/docs/chrome-extensions) · [Selenium Firefox](https://www.selenium.dev/documentation/webdriver/browsers/firefox/) · [RoboForm on Mozilla Add-ons](https://addons.mozilla.org/en-US/firefox/addon/roboform/).
