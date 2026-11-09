// Invoked only after Firefox Selenium confirms RoboForm's success screen
// and the displayed email exactly matches the workflow input.
import { normalizeEmail, recordVerified } from '../lib/records.mjs';

const expected = normalizeEmail(process.env.REGISTRATION_EMAIL);
const confirmed = normalizeEmail(process.env.CONFIRMED_EMAIL);
if (expected !== confirmed) throw new Error('Confirmed account email does not match requested email.');
const receipt = await recordVerified('data/registrations.csv', confirmed, new Date(), 'firefox_signup_ui_success');
console.log(`SIGNUP_CONFIRMED_FIREFOX: ${receipt.email} at ${receipt.utc} (${receipt.vn} Vietnam).`);
