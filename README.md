# RoboForm registration workflows

[![Firefox registration](https://img.shields.io/badge/Firefox-Register-238636?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/register-firefox.yml)
[![Chromium registration](https://img.shields.io/badge/Chromium-Register-238636?style=for-the-badge&logo=googlechrome&logoColor=white)](https://github.com/ePlus-Game/roboform/actions/workflows/record-confirmed.yml)
[![CI](https://github.com/ePlus-Game/roboform/actions/workflows/ci.yml/badge.svg)](https://github.com/ePlus-Game/roboform/actions/workflows/ci.yml)

Manually triggered GitHub Actions for registering RoboForm accounts through the **official browser extensions**. Choose **Firefox + Selenium** for a GitHub Issue-based, human-operated verification flow, or **Chromium + Playwright** for the separate signup flow.

**A submitted form or a passing CI run is not proof of registration.** A record is written only after RoboForm displays its expected success screen and confirms the exact requested email. Verification codes are supplied by a person, not automatically submitted from OCR predictions.

## Quick start

1. In repository **Settings → Secrets and variables → Actions**, configure a unique `ROBOFORM_MASTER_PASSWORD` secret of **at least 16 characters**. Do not commit or paste the password into an Issue.
2. Open [Register RoboForm account — Firefox](https://github.com/ePlus-Game/roboform/actions/workflows/register-firefox.yml), choose **Run workflow** on `main` and supply the inputs below.
3. Leave `email` empty to generate an unused `@hoangnnm.tech` address, or enter your own email. Keep `privacy_consent` checked **only if you agree** to the extension's Privacy terms.
4. If RoboForm asks for an image code, open the **human review GitHub Issue** linked in the run's **Job Summary**, inspect the image and respond manually. The running Firefox session waits for your answer.
5. Check the run's outcome. Only a verified registration is recorded in a CSV; an error, an OCR hint or an unconfirmed signup must not be treated as success.

> **Mailbox requirement:** Generating `xxx@hoangnnm.tech` does **not** create an inbox. Configure valid recipients or catch-all forwarding for `hoangnnm.tech` separately if RoboForm needs to send account email.

### Workflow inputs

| Input | Firefox | Chromium | Behavior |
| --- | --- | --- | --- |
| `email` | Optional | Optional | Blank → generate a unique 16-character hexadecimal address at `hoangnnm.tech` |
| `full_name` | Optional | Optional | Defaults to `David Nguyen` |
| `privacy_consent` | Required | — | Firefox Privacy consent; opting out stops before signup |
| `ddddocr_hint` | Optional | — | Defaults to `true`; adds a read-only OCR suggestion to the Firefox review Issue |

The Firefox and Chromium workflows are **independent registration implementations**. Run **one browser workflow per account**, not both for the same address.

## Firefox verification on GitHub

After RoboForm presents an image-code challenge, the Firefox workflow:

1. Captures the **isolated original PNG** while keeping the same Selenium session alive.
2. Creates a GitHub Issue showing the registration email, whether it was generated or supplied, and the screenshot.
3. Displays **unverified** suggestions from Tesseract and (when enabled) `ddddocr`. The Issue provides separate copyable comment examples.
4. Accepts a manually written comment from **the account that started the workflow**. The script forwards that human-provided value to the existing browser session and waits for RoboForm's actual confirmation.

Use the GitHub Issue comment box and **check capitalization against the image** before sending:

```text
/captcha ABC123
```

Replace `ABC123` with the characters **you read yourself**. The Issue's OCR suggestions are *not* guaranteed to be accurate:

- Tesseract reports an aggregate confidence metric, **not** proof that the entire string is right.
- `ddddocr` does not provide a comparable confidence value through the classification API and can confuse **uppercase and lowercase** letters.
- The workflow does **not** automatically correct case, enter OCR predictions, or claim success from a submitted code.

The Issue polling window is approximately **7 minutes (420 seconds)**. Respond before it expires; the browser session is not recoverable after its GitHub Actions job ends. Firefox's complete signup job has an overall 25-minute timeout.

**Image handling:** During review, the PNG is uploaded to the temporary `captcha-review-previews` branch so GitHub can render it in the Issue. The script attempts to remove the image and close the Issue afterwards; deletion does **not** guarantee removal from Git history or caches. On registration-step failure, the workflow also uploads the **original PNG file without a ZIP archive** as an artifact, retained for **7 days**.

> **Privacy:** The review Issue and temporary image are visible to anyone who can access this repository. The selected registration email is displayed in the Issue and run summary. Never post a master password or personal secrets.

## Email generation and CSV records

The email selector in `lib/registration-email.mjs` uses cryptographically random, lowercase hexadecimal local parts (16 characters). Before attempting signup, it checks **both CSV files**, including any `unverified` rows; on a generated-address collision, it retries (up to 64 attempts). A manually supplied address already marked verified is rejected.

| File | What it stores |
| --- | --- |
| [`data/hoangnnm.csv`](data/hoangnnm.csv) | Confirmed registrations using `@hoangnnm.tech`, whether generated or entered manually |
| [`data/registrations.csv`](data/registrations.csv) | Confirmed registrations using other email domains |

Both files share the same header:

```csv
email,registered_at_utc,registered_date_vn,verification_method,trial_started_at_utc,trial_ends_at_utc
```

- `verification_method` identifies how signup was confirmed (for example, `firefox_signup_ui_success`).
- `registered_date_vn` is the registration date in `Asia/Ho_Chi_Minh`.
- `trial_started_at_utc` and `trial_ends_at_utc` are **local estimates**: the workflow assumes a 30 × 24-hour trial from the confirmed signup timestamp. It does **not** query RoboForm billing or verify entitlement. Check the real trial deadline in RoboForm.
- Older rows whose actual trial data was never recorded retain **blank trial fields**; the workflow does not fabricate dates for them.

**CSV is the source of truth.** Markdown in the Job Summary is a convenient progress/result view, not another registration database. Neither CSV is updated until the official success screen confirms the exact email.

## Workflow reference

| Workflow | Trigger | What it does |
| --- | --- | --- |
| [Firefox registration](.github/workflows/register-firefox.yml) | Manual | Official Firefox extension, Selenium, human verification Issue, verified CSV receipt |
| [Chromium registration](.github/workflows/record-confirmed.yml) | Manual | Official Chromium extension, Playwright, verified CSV receipt; **no GitHub Issue CAPTCHA interaction** |
| [CI](.github/workflows/ci.yml) | Push / PR | Node and Python tests plus Chromium extension smoke checks; **no real signup** |
| [Firefox smoke](.github/workflows/firefox-smoke.yml) | PR paths / Manual | Tests extension startup without registering |
| [ddddocr smoke](.github/workflows/ddddocr-hint-smoke.yml) | PR paths / Manual | Tests local model on synthetic, labeled text; **not a real CAPTCHA accuracy test** |
| [Tesseract smoke](.github/workflows/tesseract-ocr-smoke.yml) | See workflow | Read-only OCR diagnostic tests |
| [Firefox XPI audit](.github/workflows/audit-firefox-xpi.yml) | PR paths / Manual | Read-only inspection of the official add-on |

### One registration job at a time

Both registration workflows use the same GitHub Actions concurrency group:

```yaml
concurrency:
  group: roboform-registration
  cancel-in-progress: false
```

This prevents **two registration workflow runs from executing simultaneously**. It does *not* block independent CI, smoke or audit jobs. GitHub Actions permits at most one running and one pending run in a concurrency group; a new pending run can replace the previous pending run. This is **not a durable first-in-first-out queue**.

## Source layout

| Path | Responsibility |
| --- | --- |
| `scripts/register-firefox.py`, `scripts/firefox_support.py` | Firefox automation and official add-on setup |
| `scripts/github_captcha_review.py` | GitHub Issue creation, human comment polling and preview cleanup |
| `scripts/review_content.py` | Safe, testable Issue rendering and OCR hint comparisons |
| `scripts/analyze-verification-image.py`, `scripts/ddddocr-hint.py` | Independent, read-only OCR diagnostics |
| `scripts/register.mjs` | Separate Chromium/Playwright registration |
| `scripts/select-registration-email.mjs`, `lib/registration-email.mjs` | Email selection, collision checks and workflow environment |
| `scripts/record-firefox.mjs`, `lib/records.mjs` | Verified CSV receipts and estimated trial timestamps |
| `test/` | Offline unit and regression tests |

## Local development

The project pins **Node.js 26** in [`.nvmrc`](.nvmrc) and [`package.json`](package.json). GitHub Actions sets up Python **3.12** for Firefox tooling.

```bash
nvm use
npm install --no-audit --no-fund
npm test
```

For offline Python unit tests, install the Python test dependency first:

```bash
python -m pip install 'selenium>=4.30,<5'
python -m unittest discover -s test -p 'test_*.py'
```

These commands run tests; they do **not** perform real registration. Browser startup smoke tests are provided as separate Actions.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| No registration email shown | Look for `REGISTRATION_SELECTED_EMAIL` in the workflow log and the **RoboForm registration attempt** Job Summary |
| CAPTCHA Issue missing | Open the Firefox registration job log; verify the image was captured and GitHub Issue creation permissions are available |
| OCR hints disagree | Read the original image yourself. Pay particular attention to uppercase/lowercase; neither prediction is a verified answer |
| Manual comment not accepted | Use `/captcha CODE` as a **single comment**, from the GitHub account that initiated the run, while the job is still waiting |
| No CSV change | No verified success screen and exact email match means no account receipt is written |
| Verification image unavailable | The temporary preview may have been deleted; check the failed run's non-ZIP PNG artifact within its 7-day retention |
| Generated email cannot receive messages | Configure recipient routing or catch-all for `hoangnnm.tech`; random address generation is not mailbox provisioning |
| Trial end looks incorrect | The 30-day date is an estimate, not a value validated against RoboForm subscription data |

## Operational boundaries

This repository uses the **official RoboForm browser extensions** and GitHub Actions for deliberate, manually initiated signups. It does not provide an automatic CAPTCHA-solving-and-submission path, promise a successful signup, create mailboxes, or confirm trial entitlement from RoboForm. Keep usage within the service's terms and your authorization.
