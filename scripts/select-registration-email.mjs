// Shared by Firefox and Chromium GitHub Actions workflows.
// This selects an address; it does NOT create or verify a RoboForm account.
import { appendFile } from 'node:fs/promises';
import { selectRegistrationEmail } from '../lib/registration-email.mjs';

async function main() {
  if (!process.env.GITHUB_ENV) {
    throw new Error('GITHUB_ENV is required to pass email to later steps.');
  }
  const selected = await selectRegistrationEmail(process.env.REGISTRATION_EMAIL);
  const source = selected.generated ? 'generated' : 'provided';
  await appendFile(
    process.env.GITHUB_ENV,
    'REGISTRATION_EMAIL=' + selected.email + '\n' +
    'REGISTRATION_EMAIL_SOURCE=' + source + '\n',
    'utf8'
  );

  // Always identify the address even when the operator supplied it explicitly.
  console.log('REGISTRATION_EMAIL_SOURCE: ' + source);
  console.log('REGISTRATION_SELECTED_EMAIL: ' + selected.email);
  if (process.env.GITHUB_STEP_SUMMARY) {
    await appendFile(
      process.env.GITHUB_STEP_SUMMARY,
      '\n### RoboForm registration attempt\n' +
        '- Address: ' + selected.email + '\n' +
        '- Email source: ' + source + '\n' +
        (selected.generated ? '- Checked for duplicates in both CSV files.\n' : '') +
        '- An account record is only saved after the official success screen.\n',
      'utf8',
    );
  }
}

main().catch(() => {
  console.error('REGISTRATION_EMAIL_SELECTION_FAILED: invalid input or registration CSV.');
  process.exitCode = 1;
});
