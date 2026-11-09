# RoboForm account registration research

Private project for reviewing RoboForm signup and recording **user-confirmed** registrations.

## What the extension actually does

The supplied RoboForm Password Manager extension archive was v10.0.2.0 (Chrome ID `pnlccmojcmeohlpggmfnbbiapkmbliob`). Its `start-page.html` and bundled `1.js` implement Create Account using an email address, master password, password confirmation, and first/last name. It can show `Account created successfully` with the registered email.

Official RoboForm documentation also notes CAPTCHA/security checks during signup. A GitHub-hosted headless runner cannot reliably finish those interactive steps, and an unconfirmed form submission must **never** be reported as a successful account registration.

## Available GitHub Action

**Actions → Record confirmed RoboForm signup → Run workflow**

1. Register a new personal account through the official RoboForm extension, including any human verification.
2. Only **after** the extension explicitly displays the account creation success screen, enter the email into the workflow.
3. Type `I CONFIRM` to certify that you saw the confirmation. This is a **manual attestation**, not independent verification by GitHub.
4. The workflow saves a UTC timestamp and the current registration-recording date in `Asia/Ho_Chi_Minh` to `data/registrations.csv`, then commits the record to `main`.
5. Duplicate emails and unconfirmed entries are rejected. This workflow has no schedule and never attempts CAPTCHA bypass.

**Important:** This workflow does not fill or submit the signup form and does not automatically create accounts. The logged timestamp is when you recorded the confirmed registration, not an independently proven server-side account creation time. No passwords or tokens are stored in the repository.

## Development

Run `node --test test/record.test.mjs` for local checks. GitHub Actions CI runs the same test suite on pull requests and main.

For future fully unattended registration, RoboForm would have to provide a supported registration/provisioning API or flow that does not require interactive human verification. For RoboForm Business, its officially documented admin onboarding / identity provider provisioning may be a better integration route.
