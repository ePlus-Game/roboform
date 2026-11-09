import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { normalizeEmail, vietnamDate, loadRecords, alreadyVerified, recordVerified, CSV_HEADER } from '../lib/records.mjs';
import { crxZipPayload } from '../scripts/install-extension.mjs';

test('validates email and prevents CSV injection', () => {
  assert.equal(normalizeEmail(' Test+1@Example.com '), 'test+1@example.com');
  for (const bad of ['=SUM(1)@example.com', 'a@example.com\nb@example.com', 'a..b@example.com', 'missing-at'])
    assert.throws(() => normalizeEmail(bad));
});

test('records confirmed signup and upgrades old unverified email', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'rf-record-'));
  const file = join(dir, 'registrations.csv');
  await writeFile(file, `${CSV_HEADER}\nhello@example.com,2026-11-08T00:00:00.000Z,2026-11-08,unverified\n`);
  assert.equal(alreadyVerified(await loadRecords(file), 'hello@example.com'), false);
  await recordVerified(file, 'HELLO@example.com', new Date('2026-11-08T18:45:00.000Z'));
  assert.equal(alreadyVerified(await loadRecords(file), 'hello@example.com'), true);
  assert.equal(vietnamDate(new Date('2026-11-08T18:45:00.000Z')), '2026-11-09');
  const csv = await readFile(file, 'utf8');
  assert.match(csv, /hello@example.com,2026-11-08T18:45:00.000Z,2026-11-09,signup_ui_success/);
  assert.equal(csv.split('hello@example.com').length, 2);
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
