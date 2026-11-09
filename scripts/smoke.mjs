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
  await openSignupForm(page);
  console.log('Smoke PASS: official RoboForm extension opens signup form with shared registration selectors.');
  console.log('No personal data was submitted or account created during this smoke test.');
} finally {
  if (context) await context.close();
  await rm(userData, { recursive: true, force: true });
}
