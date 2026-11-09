import { readFile, writeFile } from 'node:fs/promises';

export const LEGACY_CSV_HEADER = 'email,registered_at_utc,registered_date_vn,verification_method';
export const CSV_HEADER = LEGACY_CSV_HEADER + ',trial_started_at_utc,trial_ends_at_utc';
export const TRIAL_DURATION_DAYS = 30;
const TRIAL_DURATION_MS = TRIAL_DURATION_DAYS * 24 * 60 * 60 * 1000;

export function estimatedTrialWindow(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) throw new Error('Invalid trial start date.');
  return { trialStartUtc: date.toISOString(), trialEndUtc: new Date(date.getTime() + TRIAL_DURATION_MS).toISOString() };
}

export function normalizeEmail(value) {
  const email = String(value ?? '').trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9._%+\-]*@[a-z0-9](?:[a-z0-9.\-]*[a-z0-9])?\.[a-z]{2,63}$/.test(email)
      || email.length > 254 || email.includes('..')) throw new Error('Invalid email address.');
  return email;
}

export function vietnamDate(date) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(date);
  const get = type => parts.find(x => x.type === type)?.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

export async function loadRecords(path) {
  let raw;
  try { raw = await readFile(path, 'utf8'); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  const lines = raw.trim().split(/\r?\n/).filter(Boolean);
  if (!lines.length) return [];
  const header = lines.shift();
  if (header !== CSV_HEADER && header !== LEGACY_CSV_HEADER)
    throw new Error('Unexpected CSV header; refusing to overwrite it.');
  const columns = header === CSV_HEADER ? 6 : 4;
  return lines.map(line => {
    const fields = line.split(',');
    if (fields.length !== columns) throw new Error('Invalid CSV data row.');
    return {
      email: normalizeEmail(fields[0]), utc: fields[1], vn: fields[2], status: fields[3],
      trialStartUtc: fields[4] ?? '', trialEndUtc: fields[5] ?? ''
    };
  });
}

export function alreadyVerified(rows, email) {
  const normalized = normalizeEmail(email);
  return rows.some(row => row.email === normalized && row.status !== 'unverified');
}

export async function recordVerified(path, email, date = new Date(), method = 'signup_ui_success') {
  if (!['signup_ui_success', 'firefox_signup_ui_success'].includes(method))
    throw new Error('Invalid verification method.');
  const normalized = normalizeEmail(email);
  const records = await loadRecords(path);
  if (alreadyVerified(records, normalized)) throw new Error('Email already verified in CSV.');
  const { trialStartUtc, trialEndUtc } = estimatedTrialWindow(date);
  const next = { email: normalized, utc: date.toISOString(), vn: vietnamDate(date), status: method,
    trialStartUtc, trialEndUtc };
  const index = records.findIndex(x => x.email === normalized);
  if (index >= 0) records[index] = next;
  else records.push(next);
  // Preserve old rows without inventing a trial period; any legacy 4-column
  // file is upgraded to 6 columns only when a new signup is confirmed.
  const contents = [
    CSV_HEADER,
    ...records.map(x => [
      x.email, x.utc, x.vn, x.status, x.trialStartUtc ?? '', x.trialEndUtc ?? ''
    ].join(',')),
    ''
  ].join('\n');
  await writeFile(path, contents, { encoding: 'utf8' });
  return next;
}
