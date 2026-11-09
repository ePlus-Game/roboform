import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import {
  selectRegistrationEmail, registrationFileForEmail, loadAllRegistrations,
  GENERATED_EMAIL_DOMAIN
} from '../lib/registration-email.mjs';
import { LEGACY_CSV_HEADER, alreadyVerified } from '../lib/records.mjs';

const helper = resolve('scripts/select-registration-email.mjs');
const recorder = resolve('scripts/record-firefox.mjs');
const headers = LEGACY_CSV_HEADER + '\n';

async function workspace() {
  const dir = await mkdtemp(join(tmpdir(), 'rf-auto-email-'));
  await mkdir(join(dir, 'data'));
  const main = join(dir, 'data', 'registrations.csv');
  const domain = join(dir, 'data', 'hoangnnm.csv');
  await writeFile(main, headers, 'utf8');
  await writeFile(domain, headers, 'utf8');
  return { dir, main, domain };
}

test('generated hoangnnm.tech address skips collisions from both CSVs', async () => {
  const { main, domain } = await workspace();
  await writeFile(main, headers +
    '1111111111111111@hoangnnm.tech,2026-11-01T00:00:00Z,2026-11-01,unverified\n');
  await writeFile(domain, headers +
    '2222222222222222@hoangnnm.tech,2026-11-02T00:00:00Z,2026-11-02,firefox_signup_ui_success\n');
  const values = ['1111111111111111', '2222222222222222', '3333333333333333'];
  const selected = await selectRegistrationEmail('', {
    paths: [main, domain], candidate: () => values.shift()
  });
  assert.deepEqual(selected, { email: '3333333333333333@hoangnnm.tech', generated: true });
});

test('empty email produces bounded random unique local part', async () => {
  const { main, domain } = await workspace();
  const { email, generated } = await selectRegistrationEmail('  ', { paths: [main, domain] });
  assert.equal(generated, true);
  assert.match(email, new RegExp('^[a-f0-9]{16}@' + GENERATED_EMAIL_DOMAIN.replace('.', '\\.') + '$'));
});

test('rejects exhausted collisions and malformed local-part generator', async () => {
  const { main, domain } = await workspace();
  await writeFile(domain, headers +
    'aaaaaaaaaaaaaaaa@hoangnnm.tech,2026-11-03T00:00:00Z,2026-11-03,unverified\n');
  await assert.rejects(
    selectRegistrationEmail('', { paths: [main, domain], maxAttempts: 2, candidate: () => 'aaaaaaaaaaaaaaaa' }),
    /Unable to generate/
  );
  await assert.rejects(
    selectRegistrationEmail('', { paths: [main, domain], candidate: () => 'abc\nBAD' }),
    /invalid format/
  );
});

test('provided email remains unchanged and verified duplicates are blocked in any CSV', async () => {
  const { main, domain } = await workspace();
  await writeFile(domain, headers +
    'taken@hoangnnm.tech,2026-11-04T00:00:00Z,2026-11-04,firefox_signup_ui_success\n');
  await assert.rejects(
    selectRegistrationEmail('TAKEN@HOANGNNM.TECH', { paths: [main, domain] }),
    /already has a verified/
  );
  assert.deepEqual(
    await selectRegistrationEmail(' Test.User@Example.com ', { paths: [main, domain] }),
    { email: 'test.user@example.com', generated: false }
  );
  assert.equal(registrationFileForEmail('manual@hoangnnm.tech'), 'data/hoangnnm.csv');
  assert.equal(registrationFileForEmail('manual@example.com'), 'data/registrations.csv');
  assert.equal(alreadyVerified([
    { email: 'a@example.com', status: 'unverified' },
    { email: 'a@example.com', status: 'firefox_signup_ui_success' }
  ], 'a@example.com'), true);
});

test('generated email is exported to GITHUB_ENV for later workflow steps', async () => {
  const { dir } = await workspace();
  const envFile = join(dir, 'gha_env');
  const summary = join(dir, 'summary.md');
  const run = spawnSync(process.execPath, [helper], {
    cwd: dir,
    env: {
      ...process.env,
      REGISTRATION_EMAIL: '',
      GITHUB_ENV: envFile,
      GITHUB_STEP_SUMMARY: summary
    },
    encoding: 'utf8'
  });
  assert.equal(run.status, 0, run.stderr);
  const output = await readFile(envFile, 'utf8');
  assert.match(output, /^REGISTRATION_EMAIL=[a-f0-9]{16}@hoangnnm\.tech\n$/);
  assert.match(await readFile(summary, 'utf8'), /Generated signup email/);
});

test('confirmed Firefox registration routes hoangnnm.tech to dedicated CSV only', async () => {
  const { dir, main, domain } = await workspace();
  const env = { ...process.env, REGISTRATION_EMAIL: 'abc12345@hoangnnm.tech',
                CONFIRMED_EMAIL: 'abc12345@hoangnnm.tech' };
  const run = spawnSync(process.execPath, [recorder], {
    cwd: dir, env, encoding: 'utf8'
  });
  assert.equal(run.status, 0, run.stderr);
  assert.equal((await loadAllRegistrations([domain])).length, 1);
  const records = await loadAllRegistrations([domain]);
  assert.equal(records[0].trialStartUtc, records[0].utc);
  assert.equal(Date.parse(records[0].trialEndUtc) - Date.parse(records[0].trialStartUtc), 30 * 86400000);
  assert.match(await readFile(domain, 'utf8'), /abc12345@hoangnnm\.tech/);
  assert.equal(await readFile(main, 'utf8'), headers);
});

test('recording a manually provided external email still uses original CSV', async () => {
  const { dir, main, domain } = await workspace();
  const run = spawnSync(process.execPath, [recorder], {
    cwd: dir,
    env: { ...process.env, REGISTRATION_EMAIL: 'manual@example.com',
      CONFIRMED_EMAIL: 'manual@example.com' },
    encoding: 'utf8'
  });
  assert.equal(run.status, 0, run.stderr);
  assert.match(await readFile(main, 'utf8'), /manual@example\.com/);
  assert.equal(await readFile(domain, 'utf8'), headers);
});
