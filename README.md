# RoboForm account registration research

Private project for reviewing RoboForm signup and logging email addresses entered through GitHub Actions.

## Extension findings

The supplied RoboForm Password Manager archive was v10.0.2.0 (Chrome extension ID `pnlccmojcmeohlpggmfnbbiapkmbliob`). Its signup UI accepts an email address, Master Password, confirmation, and name, and can display `Account created successfully` after the signup succeeds.

Official RoboForm guidance requires completing a security check/CAPTCHA when creating an account. This repository's current GitHub Action does **not** automate the signup itself.

## Available GitHub Action

Go to **Actions → Log RoboForm registration email → Run workflow** and enter only the `email` input.

The workflow records that email along with the current UTC timestamp and date in `Asia/Ho_Chi_Minh` to `data/registrations.csv`, then commits the tracking log to `main`.

**No confirmation input is required.** The previous `I CONFIRM` manual attestation has been removed.

### Tracking semantics

- All newly added entries have `verification_method=unverified`. They are **not proof of successful RoboForm registration**.
- For backward compatibility, the CSV still uses the existing column names `registered_at_utc` and `registered_date_vn`. In new `unverified` rows, these fields mean **the time/date the email was logged**, *not* the confirmed creation date of a RoboForm account.
- Duplicate email addresses and invalid input are rejected.
- No password or token is stored in the tracking file.
- The workflow has no schedule and does not attempt any CAPTCHA bypass.

## Development

Run `node --test test/record.test.mjs` for local tests. CI runs on pull requests and main.

If the goal is unattended **account creation**, this project still needs a supported RoboForm provisioning flow or a legitimate interactive security verification process; removing an attestation field does not complete signup.
