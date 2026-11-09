import { chromium } from 'playwright';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { installExtension, EXTENSION_ID } from './install-extension.mjs';
import { openSignupForm } from './signup-ui.mjs';

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
  // Exercise the *same* selectors used by real registration.
  // No email, password or account submission in this smoke test.
  const { textFields, passFields } = await openSignupForm(page);
  // Use synthetic values to exercise local form validation, but NEVER submit.
  // This does not read any repository secret or make a registration attempt.
  await textFields.nth(0).fill('roboform-smoke@example.com');
  await passFields.nth(0).fill('ExampleSmokeOnly#2026Strong');
  await passFields.nth(1).fill('ExampleSmokeOnly#2026Strong');
  await textFields.nth(1).fill('Smoke Tester');
  await textFields.nth(1).blur();
  await page.waitForTimeout(2000);
  const state = await page.evaluate(() => ({
    controls: [...document.querySelectorAll('input, select, textarea')].filter(e => e.getClientRects().length).map(e => ({
      type: e.type, required: e.required, disabled: e.disabled,
      valid: e.validity?.valid, ariaInvalid: e.getAttribute('aria-invalid'),
      checked: (e.type === 'checkbox' || e.type === 'radio') ? e.checked : undefined,
      // Never read or log form values, even synthetic ones.
    })),
    submitEnabled: [...document.querySelectorAll('button')].some(e =>
      e.textContent?.trim() === 'Create Account' && !e.disabled),
    errors: [...document.querySelectorAll('.error-text:not(.hidden), .error-balloon:not(.hidden)')]
      .filter(e => e.getClientRects().length).map(e => e.textContent?.trim()).filter(Boolean).slice(0, 4)
  }));
  console.log('SMOKE_FORM_VALIDATION:', JSON.stringify(state));
  if (!state.submitEnabled) throw new Error('Create Account stays disabled after filling synthetic valid-looking data; check local validation / required agreements before real signup.');
  console.log('Smoke PASS: signup form can enable Create Account with synthetic data.');
  console.log('No personal data was submitted or account created during this smoke test.');
} finally {
  if (context) await context.close();
  await rm(userData, { recursive: true, force: true });
}
