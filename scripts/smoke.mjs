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
  page.on('pageerror', error => console.log('SMOKE_PAGE_ERROR:', error.message.slice(0, 400)));
  await page.goto(`chrome-extension://${EXTENSION_ID}/start-page.html`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  await page.waitForTimeout(8000);
  console.log('SMOKE_URL:', page.url());
  console.log('SMOKE_TITLE:', await page.title());
  console.log('SMOKE_BODY:', (await page.locator('body').innerText()).slice(0, 800));
  console.log('SMOKE_BUTTONS:', await page.locator('input[type="button"]').evaluateAll(nodes => nodes.map(n => n.value)));
  console.log('SMOKE_SETUP_HTML:', (await page.locator('#setup-page').innerHTML().catch(() => '')).slice(0, 700));
  await page.locator('.choose-setup-way input[type="button"][value="Sign Up"]')
    .waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('.choose-setup-way input[type="button"][value="Sign Up"]').click();
  await page.locator('.create-new-account').waitFor({ state: 'visible', timeout: 30_000 });
  console.log('Smoke PASS: official RoboForm extension opens Sign Up form in headless Playwright Chromium.');
  console.log('No personal data was submitted or account created during this smoke test.');
} finally {
  if (context) await context.close();
  await rm(userData, { recursive: true, force: true });
}
