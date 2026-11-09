import { chromium } from 'playwright';
import { mkdtemp, appendFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { installExtension, EXTENSION_ID } from './install-extension.mjs';
import { normalizeEmail, loadRecords, alreadyVerified, recordVerified } from '../lib/records.mjs';

const csvFile = 'data/registrations.csv';
const email = normalizeEmail(process.env.REGISTRATION_EMAIL);
const fullName = (process.env.REGISTRATION_FULL_NAME || 'RoboForm User').trim();
const secret = process.env.ROBOFORM_MASTER_PASSWORD || '';

async function summary(lines) {
  if (process.env.GITHUB_STEP_SUMMARY) await appendFile(process.env.GITHUB_STEP_SUMMARY, lines + '\n');
}

async function run() {
  if (fullName.length < 2 || fullName.length > 80 || /[*?"<>|\\/]/.test(fullName))
    throw new Error('Invalid full name.');
  if (secret.length < 16) throw new Error('Add a unique 16+ character ROBOFORM_MASTER_PASSWORD Actions secret.');
  const rows = await loadRecords(csvFile);
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
    await page.locator('.choose-setup-way input[type="button"][value="Sign Up"]')
      .waitFor({ state: 'visible', timeout: 60_000 });
    await page.locator('.choose-setup-way input[type="button"][value="Sign Up"]').click();
    const form = page.locator('.create-new-account');
    await form.waitFor({ state: 'visible', timeout: 45_000 });
    const textFields = form.locator('input[type="text"]');
    const passFields = form.locator('input[type="password"]');
    if ((await textFields.count()) !== 2 || (await passFields.count()) !== 2)
      throw new Error('RoboForm signup form changed; inspect extension selectors.');
    await textFields.nth(0).fill(email);
    await passFields.nth(0).fill(secret);
    await passFields.nth(1).fill(secret);
    await textFields.nth(1).fill(fullName);
    await form.locator('input[type="button"][value="Create Account"]').click();
    console.log('Create Account clicked; waiting for RoboForm confirmation (not assuming success).');

    const confirmation = page.locator('.account-confirmation .credentials-section .email');
    try { await confirmation.waitFor({ state: 'visible', timeout: 90_000 }); }
    catch {
      const challenge = page.frames().some(frame => /captcha|turnstile|challenge/i.test(frame.url())) ||
        await page.locator('iframe[src*="captcha"], iframe[src*="turnstile"], .cf-turnstile, .g-recaptcha').count() > 0;
      const errors = await form.locator('.error-text:not(.hidden), .error-balloon:not(.hidden)')
        .allTextContents().catch(() => []);
      const concise = errors.map(t => t.trim()).filter(Boolean).join('; ').slice(0, 500)
        .replaceAll(secret, '[REDACTED]');
      if (challenge) throw new Error('CAPTCHA/security challenge requires a human. No bypass was attempted.');
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
    await summary(`### RoboForm signup confirmed\n\nEmail: ${receipt.email}\n\nUTC: ${receipt.utc}\n\nVietnam date: ${receipt.vn}`);
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
