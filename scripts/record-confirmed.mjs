import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

const email = String(process.env.REGISTRATION_EMAIL || '').trim().toLowerCase();
const confirmation = process.env.USER_CONFIRMATION || '';
if (!/^[a-z0-9][a-z0-9._%+\-]*@[a-z0-9.\-]+\.[a-z]{2,63}$/.test(email) ||
    email.length > 254 || email.includes('..')) {
  throw new Error('Email is invalid.');
}
if (confirmation !== 'I CONFIRM') {
  throw new Error('You must personally confirm that RoboForm displayed a successful account creation screen.');
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
  throw new Error('This email is already in the registration log.');
}
const now = new Date();
const parts = new Intl.DateTimeFormat('en-US', {
  timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit'
}).formatToParts(now);
const datePart = type => parts.find(part => part.type === type).value;
const date = [datePart('year'), datePart('month'), datePart('day')].join('-');
const newLine = [email, now.toISOString(), date, 'user_confirmed'].join(',');
await mkdir(dirname(path), { recursive: true });
await writeFile(path, (lines.length ? lines.join('\n') : header) + '\n' + newLine + '\n');
console.log('Recorded user-confirmed signup: ' + email + ' on ' + date);
