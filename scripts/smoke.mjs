import { chromium } from 'playwright';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { installExtension, EXTENSION_ID } from './install-extension.mjs';
import { openSignupForm, getSignupSubmissionGate } from './signup-ui.mjs';

const extensionDir = await installExtension();
const userData = await mkdtemp(join(tmpdir(), 'roboform-smoke-'));
let context;
try {
  context = await chromium.launchPersistentContext(userData, {
    channel: 'chromium', headless: true, locale: 'en-US',
    args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`]
  });
  const page = await context.newPage();
  page.on('pageerror', error => console.log('SMOKE_PAGE_ERROR:', error.message.slice(0, 400)));
  await page.goto(`chrome-extension://${EXTENSION_ID}/start-page.html`, {
    waitUntil: 'domcontentloaded', timeout: 60_000
  });
  const { textFields, passFields } = await openSignupForm(page);
  // Smoke uses synthetic data only, never a real secret or registration.
  await textFields.nth(0).fill('roboform-smoke@example.com');
  await passFields.nth(0).fill('ExampleSmokeOnly#2026Strong');
  await passFields.nth(1).fill('ExampleSmokeOnly#2026Strong');
  await textFields.nth(1).fill('Smoke Tester');
  await textFields.nth(1).blur();
  await page.waitForTimeout(1500);
  const { enabled, verificationRequired } = await getSignupSubmissionGate(page);
  if (verificationRequired && !enabled) {
    console.log('SMOKE_PASS: RoboForm signup UI loaded; Create Account verification pending.');
  } else if (enabled) {
    console.log('SMOKE_PASS: RoboForm signup UI loaded; Create Account is enabled with synthetic data. No submission was attempted.');
  } else {
    throw new Error('Create Account is disabled without a recognized verification widget. Check local validation and RoboForm UI changes.');
  }
  console.log('No personal data was submitted or account created during this smoke test.');
} finally {
  if (context) await context.close();
  await rm(userData, { recursive: true, force: true });
}
