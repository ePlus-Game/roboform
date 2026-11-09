import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const script = resolve('scripts/record-confirmed.mjs');

function run(cwd, email, confirmation) {
  return spawnSync(process.execPath, [script], {
    cwd,
    env: { ...process.env, REGISTRATION_EMAIL: email, USER_CONFIRMATION: confirmation },
    encoding: 'utf8'
  });
}

test('records only explicit user confirmation and avoids duplicates', () => {
  const cwd = mkdtempSync(join(tmpdir(), 'rf-log-'));
  const pending = run(cwd, 'first@example.com', 'NO');
  assert.notEqual(pending.status, 0);
  const success = run(cwd, ' FIRST@example.com ', 'I CONFIRM');
  assert.equal(success.status, 0, success.stderr);
  const csv = readFileSync(join(cwd, 'data/registrations.csv'), 'utf8');
  assert.match(csv, /^email,registered_at_utc,registered_date_vn,verification_method\n/);
  assert.match(csv, /first@example.com,[^,]+,\d{4}-\d{2}-\d{2},user_confirmed\n/);
  assert.notEqual(run(cwd, 'first@example.com', 'I CONFIRM').status, 0);
  assert.notEqual(run(cwd, '=cmd@example.com', 'I CONFIRM').status, 0);
});
