import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const script = resolve('scripts/record-confirmed.mjs');

function run(cwd, email) {
  return spawnSync(process.execPath, [script], {
    cwd,
    env: { ...process.env, REGISTRATION_EMAIL: email },
    encoding: 'utf8'
  });
}

test('logs an email without confirmation, marks it unverified, and avoids duplicates', () => {
  const cwd = mkdtempSync(join(tmpdir(), 'rf-log-'));
  const result = run(cwd, ' FIRST@example.com ');
  assert.equal(result.status, 0, result.stderr);
  const csv = readFileSync(join(cwd, 'data/registrations.csv'), 'utf8');
  assert.match(csv, /^email,registered_at_utc,registered_date_vn,verification_method\n/);
  assert.match(csv, /first@example.com,[^,]+,\d{4}-\d{2}-\d{2},unverified\n/);
  assert.notEqual(run(cwd, 'first@example.com').status, 0);
  assert.notEqual(run(cwd, '=cmd@example.com').status, 0);
  assert.notEqual(run(cwd, '').status, 0);
});
