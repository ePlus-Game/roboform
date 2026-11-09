import { randomBytes } from 'node:crypto';
import { loadRecords, normalizeEmail } from './records.mjs';

export const GENERATED_EMAIL_DOMAIN = 'hoangnnm.tech';
export const MAIN_RECORDS_CSV = 'data/registrations.csv';
export const HOANGNNM_RECORDS_CSV = 'data/hoangnnm.csv';
export const ALL_REGISTRATION_FILES = Object.freeze([MAIN_RECORDS_CSV, HOANGNNM_RECORDS_CSV]);

export function registrationFileForEmail(address) {
  const email = normalizeEmail(address);
  return email.endsWith('@' + GENERATED_EMAIL_DOMAIN) ? HOANGNNM_RECORDS_CSV : MAIN_RECORDS_CSV;
}

export async function loadAllRegistrations(paths = ALL_REGISTRATION_FILES) {
  const entries = await Promise.all(paths.map(path => loadRecords(path)));
  return entries.flat();
}

/**
 * Choose a user-supplied address, or generate a unique local part on our domain.
 * Check BOTH CSVs, including unverified entries, for generated addresses.
 * Never register against the remote service just to see whether a name is taken.
 *
 * The GitHub Actions concurrency group serializes both registration workflows;
 * this helper is intentionally side-effect free until signup is confirmed.
 */
export async function selectRegistrationEmail(input, options = {}) {
  const paths = options.paths ?? ALL_REGISTRATION_FILES;
  const candidate = options.candidate ?? (() => randomBytes(8).toString('hex'));
  const maxAttempts = options.maxAttempts ?? 64;
  const records = await loadAllRegistrations(paths);
  const occupied = new Set(records.map(record => record.email));

  if (String(input ?? '').trim()) {
    const email = normalizeEmail(input);
    if (records.some(row => row.email === email && row.status !== 'unverified')) {
      throw new Error('Email already has a verified record in a registration CSV.');
    }
    return { email, generated: false };
  }

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const localPart = candidate();
    if (typeof localPart !== 'string' || !/^[a-z0-9]{8,16}$/.test(localPart)) {
      throw new Error('Generated email local-part has invalid format.');
    }
    const email = localPart + '@' + GENERATED_EMAIL_DOMAIN;
    if (!occupied.has(email)) return { email, generated: true };
  }
  throw new Error('Unable to generate an unused email after bounded attempts.');
}
