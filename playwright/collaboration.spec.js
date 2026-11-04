const { test, expect } = require('@playwright/test');
const { fillSignIn, signOut } = require('./helpers');

const clientEmail = process.env.TRUSTFLOW_CLIENT_EMAIL;
const clientPassword = process.env.TRUSTFLOW_CLIENT_PASSWORD;
const freelancerEmail = process.env.TRUSTFLOW_FREELANCER_EMAIL;
const freelancerPassword = process.env.TRUSTFLOW_FREELANCER_PASSWORD;

test('client creates project, freelancer accepts, client adds milestone, freelancer submits evidence', async ({ browser }) => {
  test.skip(
    !clientEmail || !clientPassword || !freelancerEmail || !freelancerPassword,
    'Set TRUSTFLOW_CLIENT_EMAIL/PASSWORD and TRUSTFLOW_FREELANCER_EMAIL/PASSWORD.',
  );

  const clientContext = await browser.newContext();
  const freelancerContext = await browser.newContext();
  const clientPage = await clientContext.newPage();
  const freelancerPage = await freelancerContext.newPage();
  const uniqueId = String(Date.now());
  const projectName = 'Playwright collaboration ' + uniqueId;
  const milestoneName = 'Playwright milestone ' + uniqueId;
  const evidenceText = 'Playwright evidence ' + uniqueId;

  try {
    await fillSignIn(clientPage, clientEmail, clientPassword);
    await clientPage.getByRole('button', { name: /sign in/i }).click();
    await expect(clientPage.getByRole('heading', { level: 1 })).toContainText('Good work starts with');
    await clientPage.getByLabel('Project name').fill(projectName);
    await clientPage.getByLabel('Freelancer account email').fill(freelancerEmail);
    await clientPage.getByLabel('Project description').fill('Browser test collaboration.');
    await clientPage.getByRole('button', { name: 'Create project' }).click();
    await expect(clientPage.getByText('Project created and invitation sent to the registered freelancer.')).toBeVisible();

    await fillSignIn(freelancerPage, freelancerEmail, freelancerPassword);
    await freelancerPage.getByRole('button', { name: /sign in/i }).click();
    await expect(freelancerPage.getByRole('heading', { level: 1 })).toContainText('Keep your next milestone');
    const invitation = freelancerPage.getByRole('button', { name: 'Accept invitation to ' + projectName });
    await expect(invitation).toBeVisible();
    await invitation.click();
    await expect(freelancerPage.getByText('Project invitation accepted.')).toBeVisible();

    await signOut(clientPage);
    await fillSignIn(clientPage, clientEmail, clientPassword);
    await clientPage.getByRole('button', { name: /sign in/i }).click();
    await clientPage.getByRole('button', { name: 'Open ' + projectName }).click();
    await expect(clientPage.getByRole('heading', { name: projectName })).toBeVisible();
    await clientPage.getByLabel('Milestone name').fill(milestoneName);
    await clientPage.getByLabel('Acceptance criteria').fill('The agreed deliverable is complete.\nFiles are included.');
    await clientPage.getByLabel('Agreed amount').fill('100.00');
    await clientPage.getByRole('button', { name: 'Add milestone' }).click();
    await expect(clientPage.getByText('Milestone added to the project.')).toBeVisible();
    await expect(clientPage.getByRole('button', { name: new RegExp(milestoneName) })).toBeVisible();

    await signOut(freelancerPage);
    await fillSignIn(freelancerPage, freelancerEmail, freelancerPassword);
    await freelancerPage.getByRole('button', { name: /sign in/i }).click();
    await freelancerPage.getByRole('button', { name: 'Open ' + projectName }).click();
    await freelancerPage.getByRole('button', { name: new RegExp(milestoneName) }).click();
    await expect(freelancerPage.getByRole('heading', { name: milestoneName })).toBeVisible();

    await freelancerPage.locator('textarea[name="description"]').fill(evidenceText);
    await freelancerPage.locator('textarea[name="links"]').fill('https://example.com/test-evidence');
    await freelancerPage.locator('input[name="file"]').setInputFiles({
      name: 'playwright-evidence.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Sample evidence attachment for Playwright.'),
    });
    await freelancerPage.getByRole('button', { name: /submit evidence revision/i }).click();
    await expect(freelancerPage.getByText('Evidence revision submitted. A client can now request an assessment.')).toBeVisible();
    await expect(freelancerPage.getByText(evidenceText)).toBeVisible();
    await expect(freelancerPage.getByText('https://example.com/test-evidence')).toBeVisible();
    await expect(freelancerPage.getByText('playwright-evidence.txt')).toBeVisible();
  } finally {
    await clientContext.close();
    await freelancerContext.close();
  }
});

