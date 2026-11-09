# RoboForm registration — Chromium and Firefox

[![Chromium registration](https://img.shields.io/badge/Chromium-Register-238636?style=for-the-badge&logo=googlechrome&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml)
[![Firefox registration](https://img.shields.io/badge/Firefox-Register-238636?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/register-firefox.yml)

There are **two independent, manually triggered real-registration workflows**. Choose **one** browser for a new account. Both require a 16+ character `ROBOFORM_MASTER_PASSWORD` repository secret, use `David Nguyen` as the default full name, and record an entry **only after RoboForm explicitly confirms account creation and the email matches**. **Do not run both workflows for the same email.**

## Optional email generation and domain-specific records

Both manually-dispatched registration workflows accept an **optional email**. Leave
the Email field empty to generate a unique random address such as
`a1b2c3d4e5f60708@hoangnnm.tech` (16 lowercase hexadecimal characters).
The generator checks **both** `data/registrations.csv` and `data/hoangnnm.csv`,
including unverified entries, and retries on any collision. Both workflows
use the same concurrency group to serialize registration attempts.

- Confirmed `@hoangnnm.tech` accounts (generated **or entered manually**) are
  stored in `data/hoangnnm.csv`.
- Confirmed accounts at other domains stay in `data/registrations.csv`.
- Neither CSV is updated unless RoboForm confirms the exact selected email.
- The generated address appears in the GitHub Actions log and Job Summary.
- **Important:** Generating an address does not provision a mailbox. The
  `hoangnnm.tech` domain must support the address or catch-all forwarding
  if registration requires receiving confirmation emails.

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
| [`firefox-smoke.yml`](.github/workflows/firefox-smoke.yml) | **Firefox + Selenium**, RoboForm official Mozilla Add-ons XPI | Separate browser feasibility test; no signup, credentials, or CSV write | Firefox extension startup and onboarding status reported |

**Chromium and Firefox are separate workflows:** `record-confirmed.yml` retains the existing Chromium implementation; `register-firefox.yml` adds a Firefox-specific implementation. The `firefox-smoke.yml` check is separate and **never registers a real account**.
