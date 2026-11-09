import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { normalizeEmail, vietnamDate, loadRecords, alreadyVerified, recordVerified, CSV_HEADER, LEGACY_CSV_HEADER, TRIAL_DURATION_DAYS, estimatedTrialWindow } from '../lib/records.mjs';
import { crxZipPayload } from '../scripts/install-extension.mjs';

test('validates email and prevents CSV injection', () => {
  assert.equal(normalizeEmail(' Test+1@Example.com '), 'test+1@example.com');
  for (const bad of ['=SUM(1)@example.com', 'a@example.com\nb@example.com', 'a..b@example.com', 'missing-at'])
    assert.throws(() => normalizeEmail(bad));
});

test('records confirmed signup and upgrades old unverified email', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'rf-record-'));
  const file = join(dir, 'registrations.csv');
  await writeFile(file, `${LEGACY_CSV_HEADER}\nhello@example.com,2026-11-08T00:00:00.000Z,2026-11-08,unverified\n`);
  assert.equal(alreadyVerified(await loadRecords(file), 'hello@example.com'), false);
  await recordVerified(file, 'HELLO@example.com', new Date('2026-11-08T18:45:00.000Z'));
  assert.equal(alreadyVerified(await loadRecords(file), 'hello@example.com'), true);
  assert.equal(vietnamDate(new Date('2026-11-08T18:45:00.000Z')), '2026-11-09');
  const csv = await readFile(file, 'utf8');
  assert.match(csv, /hello@example.com,2026-11-08T18:45:00.000Z,2026-11-09,signup_ui_success/);
  assert.equal(csv.split('hello@example.com').length, 2);
  assert.match(csv, new RegExp('^' + CSV_HEADER + '\\n'));
  const rows = await loadRecords(file);
  assert.equal(rows[0].trialStartUtc, '2026-11-08T18:45:00.000Z');
  assert.equal(rows[0].trialEndUtc, '2026-12-08T18:45:00.000Z');
  assert.equal(TRIAL_DURATION_DAYS, 30);
  await assert.rejects(recordVerified(file, 'hello@example.com'));
});

test('rejects invalid CRX packages without loading any code', () => {
  assert.throws(() => crxZipPayload(Buffer.from('garbage')));
});


test('records verified Firefox signup with distinct source, never accepts arbitrary method', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'rf-firefox-record-'));
  const file = join(dir, 'registrations.csv');
  await recordVerified(file, 'firefox@example.com', new Date('2026-11-09T04:00:00.000Z'), 'firefox_signup_ui_success');
  assert.equal((await loadRecords(file))[0].status, 'firefox_signup_ui_success');
  await assert.rejects(recordVerified(file, 'other@example.com', new Date(), 'unverified'));
  assert.equal((await loadRecords(file)).length, 1);
});

test('trial is 30 actual days in UTC across DST and year boundaries', () => {
  const date = new Date('2026-12-20T22:15:00.000Z');
  const trial = estimatedTrialWindow(date);
  assert.equal(trial.trialStartUtc, '2026-12-20T22:15:00.000Z');
  assert.equal(trial.trialEndUtc, '2027-01-19T22:15:00.000Z');
  assert.equal(
    Date.parse(trial.trialEndUtc) - Date.parse(trial.trialStartUtc),
    30 * 24 * 60 * 60 * 1000,
  );
  assert.throws(() => estimatedTrialWindow(new Date('broken')), /Invalid trial/);
});

test('legacy rows without confirmed trial dates remain blank after upgrade', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'rf-legacy-trial-'));
  const file = join(dir, 'legacy.csv');
  await writeFile(file, LEGACY_CSV_HEADER + '\n' +
    'previous@example.com,2026-11-01T00:00:00.000Z,2026-11-01,firefox_signup_ui_success\n');
  await recordVerified(file, 'new@example.com', new Date('2026-11-10T00:00:00.000Z'));
  const rows = await loadRecords(file);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].trialStartUtc, '');
  assert.equal(rows[0].trialEndUtc, '');
  assert.equal(rows[1].trialStartUtc, '2026-11-10T00:00:00.000Z');
  assert.equal(rows[1].trialEndUtc, '2026-12-10T00:00:00.000Z');
});
