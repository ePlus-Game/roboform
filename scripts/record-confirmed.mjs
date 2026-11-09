import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

// This workflow logs an email for tracking; it does not create or verify
// a RoboForm account. Never mark these records as successful registrations.
const email = String(process.env.REGISTRATION_EMAIL || '').trim().toLowerCase();
if (!/^[a-z0-9][a-z0-9._%+\-]*@[a-z0-9.\-]+\.[a-z]{2,63}$/.test(email) ||
    email.length > 254 || email.includes('..')) {
  throw new Error('Email is invalid.');
}
const path = 'data/registrations.csv';
const header = 'email,registered_at_utc,registered_date_vn,verification_method';
let old = '';
try {
  old = await readFile(path, 'utf8');
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
const lines = old.trim().split(/\r?\n/).filter(Boolean);
if (lines.length && lines[0] !== header) throw new Error('Unexpected CSV schema.');
if (lines.slice(1).some(line => line.split(',')[0] === email)) {
  throw new Error('This email is already in the tracking log.');
}
const now = new Date();
const parts = new Intl.DateTimeFormat('en-US', {
  timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit'
}).formatToParts(now);
const datePart = type => parts.find(part => part.type === type).value;
const date = [datePart('year'), datePart('month'), datePart('day')].join('-');
const newLine = [email, now.toISOString(), date, 'unverified'].join(',');
await mkdir(dirname(path), { recursive: true });
await writeFile(path, (lines.length ? lines.join('\n') : header) + '\n' + newLine + '\n');
console.log('Logged email without account verification: ' + email + ' on ' + date);
