import { readFile, writeFile } from 'node:fs/promises';

export const CSV_HEADER = 'email,registered_at_utc,registered_date_vn,verification_method';

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
  if (lines.shift() !== CSV_HEADER) throw new Error('Unexpected CSV header; refusing to overwrite it.');
  return lines.map(line => {
    const fields = line.split(',');
    if (fields.length !== 4) throw new Error('Invalid CSV data row.');
    return { email: normalizeEmail(fields[0]), utc: fields[1], vn: fields[2], status: fields[3] };
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
  const next = { email: normalized, utc: date.toISOString(), vn: vietnamDate(date), status: method };
  const index = records.findIndex(x => x.email === normalized);
  if (index >= 0) records[index] = next;
  else records.push(next);
  const contents = [CSV_HEADER, ...records.map(x => [x.email, x.utc, x.vn, x.status].join(',')), ''].join('\n');
  await writeFile(path, contents, { encoding: 'utf8' });
  return next;
}
