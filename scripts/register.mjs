import { chromium } from 'playwright';
import { mkdtemp, appendFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { installExtension, EXTENSION_ID } from './install-extension.mjs';
import { openSignupForm, getSignupSubmissionGate } from './signup-ui.mjs';
import { normalizeEmail, alreadyVerified, recordVerified } from '../lib/records.mjs';
import { registrationFileForEmail, loadAllRegistrations } from '../lib/registration-email.mjs';

const csvFile = registrationFileForEmail(process.env.REGISTRATION_EMAIL);
const email = normalizeEmail(process.env.REGISTRATION_EMAIL);
const fullName = (process.env.REGISTRATION_FULL_NAME || 'RoboForm User').trim();
const secret = process.env.ROBOFORM_MASTER_PASSWORD || '';

async function summary(lines) {
  if (process.env.GITHUB_STEP_SUMMARY) await appendFile(process.env.GITHUB_STEP_SUMMARY, lines + '\n');
}

async function run() {
  if (fullName.length < 2 || fullName.length > 80 || /[*?"<>|\\/]/.test(fullName))
    throw new Error('Invalid full name.');
  if (!secret.trim()) throw new Error('ROBOFORM_MASTER_PASSWORD is missing or blank. Check repository Actions secrets.');
  if (secret.length < 16) throw new Error('ROBOFORM_MASTER_PASSWORD was supplied but is shorter than 16 characters. Update the repository secret.');
  const rows = await loadAllRegistrations();
  if (alreadyVerified(rows, email)) throw new Error('Email already has a verified registration record; no retry attempted.');

  const extensionDir = await installExtension();
  const profile = await mkdtemp(join(tmpdir(), 'rf-pw-profile-'));
  let context;
  try {
    context = await chromium.launchPersistentContext(profile, {
      channel: 'chromium', headless: true, locale: 'en-US',
      args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`]
    });
    const page = await context.newPage();
    await page.goto(`chrome-extension://${EXTENSION_ID}/start-page.html`, {
      waitUntil: 'domcontentloaded', timeout: 60_000
    });
    const { textFields, passFields } = await openSignupForm(page);
    await textFields.nth(0).fill(email);
    await passFields.nth(0).fill(secret);
    await passFields.nth(1).fill(secret);
    await textFields.nth(1).fill(fullName);
    await textFields.nth(1).blur();
    await page.waitForTimeout(1500);
    const gate = await getSignupSubmissionGate(page);
    if (!gate.enabled) {
      if (gate.verificationRequired) {
        throw new Error('Account creation is pending verification; no registration was confirmed or recorded.');
      }
      throw new Error('Create Account remains disabled after filling the fields. Check UI-side password policy and required validation; no signup was confirmed or recorded.');
    }
    await gate.submit.click({ timeout: 15_000 });
    console.log('Create Account clicked; waiting for RoboForm confirmation (not assuming success).');

    const confirmation = page.locator('.account-confirmation .credentials-section .email');
    try { await confirmation.waitFor({ state: 'visible', timeout: 90_000 }); }
    catch {
      const challenge = page.frames().some(frame => /captcha|turnstile|challenge/i.test(frame.url())) ||
        await page.locator('iframe[src*="captcha"], iframe[src*="turnstile"], .cf-turnstile, .g-recaptcha').count() > 0;
      const errors = await page.locator('.error-text:not(.hidden), .error-balloon:not(.hidden)')
        .allTextContents().catch(() => []);
      const concise = errors.map(t => t.trim()).filter(Boolean).join('; ').slice(0, 500)
        .replaceAll(secret, '[REDACTED]');
      if (challenge) throw new Error('Account confirmation is pending a verification step.');
      throw new Error('No verified success screen. Possible security check / OTP / signup error.' +
        (concise ? ` UI says: ${concise}` : ''));
    }
    const returnedEmail = normalizeEmail(await confirmation.innerText());
    if (returnedEmail !== email) throw new Error('Confirmed signup email does not match requested address.');
    const title = await page.locator('.account-confirmation .done-message .text').innerText();
    if (!/Account created successfully/i.test(title))
      throw new Error('RoboForm did not display the expected success message.');
    const receipt = await recordVerified(csvFile, email);
    console.log(`SIGNUP_CONFIRMED: ${receipt.email} at ${receipt.utc} (${receipt.vn} Vietnam).`);
    console.log(`TRIAL_ESTIMATED: 30 days from ${receipt.trialStartUtc} to ${receipt.trialEndUtc} UTC (not provider-confirmed).`);
    await summary(`### RoboForm signup confirmed\n\nEmail: ${receipt.email}\n\nUTC: ${receipt.utc}\n\nVietnam date: ${receipt.vn}\n\nEstimated 30-day trial end (UTC): ${receipt.trialEndUtc}\n\nConfirm actual trial entitlement and expiration in RoboForm.`);
  } finally {
    if (context) await context.close();
    await rm(profile, { recursive: true, force: true });
  }
}

run().catch(async error => {
  const message = error.message.replaceAll(secret || '!!not-configured!!', '[REDACTED]');
  console.error('REGISTRATION_NOT_CONFIRMED: ' + message);
  await summary(`### RoboForm signup was not confirmed\n\n${message.replaceAll('|', '\\|')}`);
  process.exitCode = 1;
});
