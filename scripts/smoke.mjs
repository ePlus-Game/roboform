import { chromium } from 'playwright';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { installExtension, EXTENSION_ID } from './install-extension.mjs';

const extensionDir = await installExtension();
const userData = await mkdtemp(join(tmpdir(), 'roboform-smoke-'));
let context;
try {
  context = await chromium.launchPersistentContext(userData, {
    channel: 'chromium', headless: true, locale: 'en-US',
    args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`]
  });
  const page = await context.newPage();
  await page.goto(`chrome-extension://${EXTENSION_ID}/start-page.html`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  await page.locator('.choose-setup-way input[type="button"][value="Sign Up"]')
    .waitFor({ state: 'visible', timeout: 60_000 });
  await page.locator('.choose-setup-way input[type="button"][value="Sign Up"]').click();
  await page.locator('.create-new-account').waitFor({ state: 'visible', timeout: 30_000 });
  console.log('Smoke PASS: official RoboForm extension opens Sign Up form in headless Playwright Chromium.');
  console.log('No personal data was submitted or account created during this smoke test.');
} finally {
  if (context) await context.close();
  await rm(userData, { recursive: true, force: true });
}
