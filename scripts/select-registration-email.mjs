// Shared by Firefox and Chromium GitHub Actions workflows.
// This selects an address; it does NOT create or verify a RoboForm account.
import { appendFile } from 'node:fs/promises';
import { selectRegistrationEmail } from '../lib/registration-email.mjs';

async function main() {
  if (!process.env.GITHUB_ENV) {
    throw new Error('GITHUB_ENV is required to pass email to later steps.');
  }
  const selected = await selectRegistrationEmail(process.env.REGISTRATION_EMAIL);
  await appendFile(process.env.GITHUB_ENV, 'REGISTRATION_EMAIL=' + selected.email + '\n', 'utf8');

  console.log('REGISTRATION_EMAIL_SOURCE: ' + (selected.generated ? 'generated' : 'provided'));
  if (selected.generated) {
    console.log('REGISTRATION_GENERATED_EMAIL: ' + selected.email);
    if (process.env.GITHUB_STEP_SUMMARY) {
      await appendFile(
        process.env.GITHUB_STEP_SUMMARY,
        '\n### Generated signup email\n- Address: ' + selected.email + '\n' +
          '- Uniqueness checked against both registration CSV files.\n' +
          '- A record is only saved after the official success screen.\n',
        'utf8',
      );
    }
  }
}

main().catch(() => {
  console.error('REGISTRATION_EMAIL_SELECTION_FAILED: invalid input or registration CSV.');
  process.exitCode = 1;
});
