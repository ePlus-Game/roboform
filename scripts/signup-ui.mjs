// Shared Playwright navigation for smoke tests and real signup.
// Keep this flow identical so CI catches broken registration selectors
// without submitting an account or handling credentials.
export async function openSignupForm(page) {
  // RoboForm v10.0.2.0 uses text-bearing Sign Up/Create Account
  // controls; the old .choose-setup-way input[value="Sign Up"]
  // selector never became visible in GitHub Actions.
  const signup = page.getByText('Sign Up', { exact: true }).last();
  try {
    await signup.click({ timeout: 60_000 });
    await page.getByText('Create Account', { exact: true }).last()
      .waitFor({ state: 'visible', timeout: 45_000 });
  } catch {
    // Do not log full DOM, URLs with query strings, or typed credentials.
    const count = await page.getByText('Sign Up', { exact: true }).count().catch(() => 0);
    throw new Error(`RoboForm signup screen unavailable (Sign Up text matches: ${count}). Check current extension UI and CI smoke test.`);
  }
  const textFields = page.locator('input[type="text"]:visible');
  const passFields = page.locator('input[type="password"]:visible');
  if ((await textFields.count()) !== 2 || (await passFields.count()) !== 2) {
    throw new Error('RoboForm signup form changed: expected 2 visible text fields and 2 visible password fields.');
  }
  return { textFields, passFields };
}
