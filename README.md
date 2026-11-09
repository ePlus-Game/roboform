# RoboForm account registration — GitHub Actions + Playwright

[![Register via GitHub Actions](https://img.shields.io/badge/Playwright-Register_RoboForm-238636?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml)

[**Open the signup workflow**](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml) — then select **Run workflow**.

## Setup (once)

1. Go to **Settings → Secrets and variables → Actions → New repository secret**.
2. Create a secret named **`ROBOFORM_MASTER_PASSWORD`** containing a strong, unique Master Password (16+ characters) for **this** account. Never type the password into the Actions email input or commit it to Git. Make sure you personally retain it securely; RoboForm cannot simply reset encrypted vault contents without the recovery setup.
3. After this PR is merged, open the green button above, enter your **email** and optionally **full_name**, then run. No `I CONFIRM` field.

**Use a distinct Master Password for each account.** If you register another email, change the secret first. The workflow handles one account per manually triggered run; no schedules or automatic retries.

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

`npm test` runs CSV, dedupe and input tests. CI's **smoke-extension** job downloads the extension and opens the Sign Up form with Playwright **without submitting a real account**. The real registration job requires an operator-supplied email and a GitHub Actions secret, so CI smoke success alone cannot prove RoboForm account creation.

The signup selectors were derived from user-provided RoboForm extension **v10.0.2.0**; live versions might have changed. For safety, no browser screenshots or traces containing credentials are uploaded. The repository and its logs should remain private.

References: [RoboForm signup help](https://help.roboform.com/hc/en-us/articles/115005962708-RoboForm-Windows-Installation-and-setup) · [RoboForm OTP documentation](https://help.roboform.com/hc/en-us/articles/115005043767-How-to-enable-One-Time-Password-OTP-via-email-or-SMS) · [Playwright extensions](https://playwright.dev/docs/chrome-extensions).
