# RoboForm registration — Chromium and Firefox

[![Chromium registration](https://img.shields.io/badge/Chromium-Register-238636?style=for-the-badge&logo=googlechrome&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml)
[![Firefox registration](https://img.shields.io/badge/Firefox-Register-238636?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/register-firefox.yml)

There are **two independent, manually triggered real-registration workflows**. Choose **one** browser for a new account. Both require a 16+ character `ROBOFORM_MASTER_PASSWORD` repository secret, use `David Nguyen` as the default full name, and record an entry **only after RoboForm explicitly confirms account creation and the email matches**. **Do not run both workflows for the same email.**

## Node.js version (CI and registration)

- **Node.js 26 LTS (Lithium)** is the latest stable/LTS line as of 2026-11-09; the latest patch then is **26.13.0**. Node.js 27 is still **Alpha** and is not used for registration.
- The single source of truth is [`.nvmrc`](.nvmrc) containing `26`. Every Node-powered GitHub Actions workflow uses `actions/setup-node@v7` with `node-version-file: .nvmrc` and `check-latest: true`, so it selects the newest available **26.x** patch without manual changes.
- The workflows use `actions/checkout@v7` and `actions/setup-python@v7` to avoid the deprecated Node.js 20 runtime in previous action versions. These actions' internal runtime is separate from the Node.js version used to execute project scripts.
- On a development machine, run `nvm use` (or install Node.js 26 LTS) and `npm test`. The `package.json` engine range excludes prerelease Node 27.

## Local interactive Firefox verification

When RoboForm shows an image-code challenge, a **GitHub-hosted Actions runner cannot accept keyboard input into the Firefox UI**. Use this opt-in mode on a computer with a visible desktop session instead.

Prerequisites: Firefox, Python 3.12+ and Node.js 26 available on your computer. From the repository root, run:

```powershell
python -m pip install "selenium>=4.30,<5"
python scripts/register-firefox.py --interactive
```

The command asks for Privacy consent, signup email and Master Password (entered without echoing it). The name defaults to `David Nguyen`; set `REGISTRATION_FULL_NAME` if needed. It downloads the signed official Firefox add-on into a temporary browser profile, fills the signup fields, then leaves a **visible Firefox window** open. In that window, click **Create Account** and complete any verification yourself. When RoboForm displays **Account created successfully**, return to the terminal and press **Enter**.

Selenium then checks that RoboForm's success screen displays the exact requested email. Only when both checks succeed does it append a record to `data/registrations.csv` **locally**. The command does **not** push the CSV to GitHub. If the screen is not verified, it records nothing. Keep the browser open until the terminal finishes; Ctrl+C cancels.

### Optional auto-resume mode (local desktop only)

```powershell
python scripts/register-firefox.py --interactive --auto-resume
```

After filling the signup fields, this mode clicks **Create Account** once if the standard submit button is enabled. If verification appears, finish it yourself in the **visible Firefox window**; if needed, click Create Account there after the challenge. Selenium checks the official result once per second and **automatically** records only a verified success screen with the exact requested email. You do not need to return to PowerShell and press Enter. The mode stops after five minutes without a verified success and records nothing.

This does **not** automatically solve, enter, or bypass any CAPTCHA. It is deliberately a local mode, not an unattended GitHub Actions registration workflow.

The original `register-firefox.yml` GitHub Actions workflow remains headless and unchanged; it still stops if manual verification is required. Never put your Master Password in command-line arguments, the repository, or screenshots.

## Which browser is currently used?

| Workflow | Browser / technology | Purpose | What success means |
| --- | --- | --- | --- |
| [`record-confirmed.yml`](.github/workflows/record-confirmed.yml) | **Chromium + Playwright**, RoboForm Chrome Web Store extension | Manual-triggered attempt to register a real account | Only RoboForm's confirmed success screen **and exact email match** allow a verified CSV record |
| [`register-firefox.yml`](.github/workflows/register-firefox.yml) | **Firefox + Selenium**, RoboForm Mozilla Add-ons extension | Independent real signup attempt, with a preselected Privacy checkbox that the operator can uncheck | Only RoboForm's confirmed success screen **and exact email match** allow a verified CSV record |
| [`ci.yml`](.github/workflows/ci.yml) | **Chromium + Playwright** (plus Node tests) | Check extension signup UI and validation without submission | Passing smoke checks **does not** mean an account was created |
| [`firefox-smoke.yml`](.github/workflows/firefox-smoke.yml) | **Firefox + Selenium**, RoboForm official Mozilla Add-ons XPI | Separate browser feasibility test; no signup, credentials, or CSV write | Firefox extension startup and onboarding status reported |

**Chromium and Firefox are separate workflows:** `record-confirmed.yml` retains the existing Chromium implementation; `register-firefox.yml` adds a Firefox-specific implementation. The `firefox-smoke.yml` check is separate and **never registers a real account**.
