// Invoked only after Firefox Selenium confirms RoboForm's success screen
// and the displayed email exactly matches the workflow input.
import { normalizeEmail, recordVerified, alreadyVerified } from '../lib/records.mjs';
import { registrationFileForEmail, loadAllRegistrations } from '../lib/registration-email.mjs';

const expected = normalizeEmail(process.env.REGISTRATION_EMAIL);
const confirmed = normalizeEmail(process.env.CONFIRMED_EMAIL);
if (expected !== confirmed) throw new Error('Confirmed account email does not match requested email.');
if (alreadyVerified(await loadAllRegistrations(), confirmed)) throw new Error('Email already verified in a registration CSV.');
const receipt = await recordVerified(registrationFileForEmail(confirmed), confirmed, new Date(), 'firefox_signup_ui_success');
console.log(`SIGNUP_CONFIRMED_FIREFOX: ${receipt.email} at ${receipt.utc} (${receipt.vn} Vietnam).`);
