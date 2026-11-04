# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: collaboration.spec.js >> client creates project, freelancer accepts, client adds milestone, freelancer submits evidence
- Location: collaboration.spec.js:9:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('button', { name: 'Accept invitation to Playwright collaboration 1793639834704' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('button', { name: 'Accept invitation to Playwright collaboration 1793639834704' }) with timeout 5000ms
  - waiting for getByRole('button', { name: 'Accept invitation to Playwright collaboration 1793639834704' })

```

```yaml
- complementary:
  - link "TrustFlow home":
    - /url: /
    - text: T trustflow.
  - text: WORK, WITH A CLEAR PAPER TRAIL P YOUR WORKSPACE
  - strong: Freelancer desk
  - emphasis: Personal workspace
  - text: ⌄
  - paragraph: WORKSPACE
  - button "Overview"
  - paragraph: WORKFLOW LIVE
  - button "Payments"
  - button "Insights"
  - button "Resources"
  - text: ✓ PAYMENT PARTNER
  - img "PayPal"
  - strong: Payments with a paper trail.
  - paragraph: Clear agreements. Visible evidence. Human approval.
  - text: P
  - strong: playwrightfl@example.com
  - text: Freelancer account
- main:
  - text: YOUR WORKSPACE
  - strong: Overview
  - textbox "Search projects":
    - /placeholder: Search projects…
  - text: ⌘ K POWERED BY
  - img "PayPal"
  - button "Open notifications, 1 unread": "1"
  - button "Open account menu":
    - text: P
    - strong: playwrightfl@example.com
    - text: Freelancer account
  - text: FREELANCER WORKSPACE
  - heading "Keep your next milestone moving." [level=1]:
    - text: Keep your next milestone
    - emphasis: moving.
  - paragraph: Track your projects, submit evidence, and stay on top of payment milestones.
  - text: ◷ Monday, Nov 2 Email confirmed ▦ TOTAL PROJECTS
  - strong: "1"
  - text: ◇ MILESTONES
  - strong: "0"
  - text: ◎ REVISION REQUESTS
  - strong: "0"
  - text: ✓ DECISIONS DUE
  - strong: "0"
  - text: $ ACTIVE PAYMENTS
  - strong: "0"
  - text: YOUR COLLABORATIONS
  - heading "Projects 1" [level=2]
  - paragraph: Keep agreements, revisions, and decisions together.
  - tablist "Filter projects":
    - tab "All projects 1" [selected]
    - tab "Active 0"
    - tab "Invitations 1"
  - text: 1 shown
  - searchbox "Search projects, people, or actions"
  - status: of 1 projects
  - button "Export CSV"
  - text: No Rows To Show. 1 to 1 of 1. Page 1 of 1
  - grid:
    - rowgroup:
      - row "Project Client Needs attention Milestones Payments Status":
        - columnheader "Project"
        - columnheader "Client"
        - columnheader "Needs attention"
        - columnheader "Milestones"
        - columnheader "Payments"
        - columnheader "Status"
      - row "Open Filter Menu Open Filter Menu Open Filter Menu Open Filter Menu Open Filter Menu Open Filter Menu":
        - gridcell "Open Filter Menu":
          - textbox "Project Filter Input"
          - button "Open Filter Menu"
        - gridcell "Open Filter Menu":
          - textbox "Client Filter Input"
          - button "Open Filter Menu"
        - gridcell "Open Filter Menu":
          - textbox "Needs attention Filter Input"
          - button "Open Filter Menu"
        - gridcell "Open Filter Menu":
          - spinbutton "Milestones Filter Input"
          - button "Open Filter Menu"
        - gridcell "Open Filter Menu":
          - textbox "Payments Filter Input"
          - button "Open Filter Menu"
        - gridcell "Open Filter Menu":
          - textbox "Status Filter Input"
          - button "Open Filter Menu"
      - row "Playwright collaboration 1793639834704 Browser test collaboration. playwrightestclient@example.com Invitation to accept 0 None active Invitation pending":
        - gridcell "Playwright collaboration 1793639834704 Browser test collaboration.":
          - strong: Playwright collaboration 1793639834704
          - text: Browser test collaboration.
        - gridcell "playwrightestclient@example.com"
        - gridcell "Invitation to accept"
        - gridcell "0"
        - gridcell "None active"
        - gridcell "Invitation pending"
  - text: "Page Size:"
  - combobox "Page Size": "8"
  - text: 1 to 1 of 1
  - button "First Page" [disabled]
  - button "Previous Page" [disabled]
  - text: Page
  - spinbutton "Page number, 1 of 1": "1"
  - text: of 1
  - button "Next Page" [disabled]
  - button "Last Page" [disabled]
  - text: Your project records stay together in one place. ⌑ Privacy-first workspace AT A GLANCE
  - heading "Workspace pulse" [level=2]
  - strong: "1"
  - text: projects in your workspace
  - img "0 active projects, 1 pending invitations"
  - button "Active 0":
    - text: Active
    - strong: "0"
  - button "Invitations 1":
    - text: Invitations
    - strong: "1"
  - text: Milestones across projects
  - strong: "0"
  - text: Revision requests
  - strong: "0"
  - button "Payments in progress 0":
    - text: Payments in progress
    - strong: "0"
  - paragraph: Counts update from your current project records.
  - text: WORKSPACE UPDATES
  - heading "Recent activity" [level=2]
  - paragraph: Updates recorded across your projects.
  - button "View insights →"
  - button "↗ Project created Playwright collaboration 1793639834704 11/2/2026, 10:47:18 PM · client":
    - text: ↗
    - strong: Project created
    - text: Playwright collaboration 1793639834704 11/2/2026, 10:47:18 PM · client
  - text: ACCOUNT SNAPSHOT
  - heading "Your workspace details" [level=2]
  - paragraph: Current account and verification status.
  - button "Open account settings": ↗
  - text: P
  - strong: playwrightfl@example.com
  - text: playwrightfl@example.com Verified ACCOUNT ROLE
  - strong: Freelancer
  - text: WORKSPACE
  - strong: Freelancer desk
  - text: PROJECTS
  - strong: 1 total
  - text: SECURITY
  - strong: Email confirmed
  - button "Manage account settings →"
```

# Test source

```ts
  1  | const { test, expect } = require('@playwright/test');
  2  | const { fillSignIn, signOut } = require('./helpers');
  3  | 
  4  | const clientEmail = process.env.TRUSTFLOW_CLIENT_EMAIL;
  5  | const clientPassword = process.env.TRUSTFLOW_CLIENT_PASSWORD;
  6  | const freelancerEmail = process.env.TRUSTFLOW_FREELANCER_EMAIL;
  7  | const freelancerPassword = process.env.TRUSTFLOW_FREELANCER_PASSWORD;
  8  | 
  9  | test('client creates project, freelancer accepts, client adds milestone, freelancer submits evidence', async ({ browser }) => {
  10 |   test.skip(
  11 |     !clientEmail || !clientPassword || !freelancerEmail || !freelancerPassword,
  12 |     'Set TRUSTFLOW_CLIENT_EMAIL/PASSWORD and TRUSTFLOW_FREELANCER_EMAIL/PASSWORD.',
  13 |   );
  14 | 
  15 |   const clientContext = await browser.newContext();
  16 |   const freelancerContext = await browser.newContext();
  17 |   const clientPage = await clientContext.newPage();
  18 |   const freelancerPage = await freelancerContext.newPage();
  19 |   const uniqueId = String(Date.now());
  20 |   const projectName = 'Playwright collaboration ' + uniqueId;
  21 |   const milestoneName = 'Playwright milestone ' + uniqueId;
  22 |   const evidenceText = 'Playwright evidence ' + uniqueId;
  23 | 
  24 |   try {
  25 |     await fillSignIn(clientPage, clientEmail, clientPassword);
  26 |     await clientPage.getByRole('button', { name: /sign in/i }).click();
  27 |     await expect(clientPage.getByRole('heading', { level: 1 })).toContainText('Good work starts with');
  28 |     await clientPage.getByLabel('Project name').fill(projectName);
  29 |     await clientPage.getByLabel('Freelancer account email').fill(freelancerEmail);
  30 |     await clientPage.getByLabel('Project description').fill('Browser test collaboration.');
  31 |     await clientPage.getByRole('button', { name: 'Create project' }).click();
  32 |     await expect(clientPage.getByText('Project created and invitation sent to the registered freelancer.')).toBeVisible();
  33 | 
  34 |     await fillSignIn(freelancerPage, freelancerEmail, freelancerPassword);
  35 |     await freelancerPage.getByRole('button', { name: /sign in/i }).click();
  36 |     await expect(freelancerPage.getByRole('heading', { level: 1 })).toContainText('Keep your next milestone');
  37 |     const invitation = freelancerPage.getByRole('button', { name: 'Accept invitation to ' + projectName });
> 38 |     await expect(invitation).toBeVisible();
     |                              ^ Error: expect(locator).toBeVisible() failed
  39 |     await invitation.click();
  40 |     await expect(freelancerPage.getByText('Project invitation accepted.')).toBeVisible();
  41 | 
  42 |     await signOut(clientPage);
  43 |     await fillSignIn(clientPage, clientEmail, clientPassword);
  44 |     await clientPage.getByRole('button', { name: /sign in/i }).click();
  45 |     await clientPage.getByRole('button', { name: 'Open ' + projectName }).click();
  46 |     await expect(clientPage.getByRole('heading', { name: projectName })).toBeVisible();
  47 |     await clientPage.getByLabel('Milestone name').fill(milestoneName);
  48 |     await clientPage.getByLabel('Acceptance criteria').fill('The agreed deliverable is complete.\nFiles are included.');
  49 |     await clientPage.getByLabel('Agreed amount').fill('100.00');
  50 |     await clientPage.getByRole('button', { name: 'Add milestone' }).click();
  51 |     await expect(clientPage.getByText('Milestone added to the project.')).toBeVisible();
  52 |     await expect(clientPage.getByRole('button', { name: new RegExp(milestoneName) })).toBeVisible();
  53 | 
  54 |     await signOut(freelancerPage);
  55 |     await fillSignIn(freelancerPage, freelancerEmail, freelancerPassword);
  56 |     await freelancerPage.getByRole('button', { name: /sign in/i }).click();
  57 |     await freelancerPage.getByRole('button', { name: 'Open ' + projectName }).click();
  58 |     await freelancerPage.getByRole('button', { name: new RegExp(milestoneName) }).click();
  59 |     await expect(freelancerPage.getByRole('heading', { name: milestoneName })).toBeVisible();
  60 | 
  61 |     await freelancerPage.locator('textarea[name="description"]').fill(evidenceText);
  62 |     await freelancerPage.locator('textarea[name="links"]').fill('https://example.com/test-evidence');
  63 |     await freelancerPage.locator('input[name="file"]').setInputFiles({
  64 |       name: 'playwright-evidence.txt',
  65 |       mimeType: 'text/plain',
  66 |       buffer: Buffer.from('Sample evidence attachment for Playwright.'),
  67 |     });
  68 |     await freelancerPage.getByRole('button', { name: /submit evidence revision/i }).click();
  69 |     await expect(freelancerPage.getByText('Evidence revision submitted. A client can now request an assessment.')).toBeVisible();
  70 |     await expect(freelancerPage.getByText(evidenceText)).toBeVisible();
  71 |     await expect(freelancerPage.getByText('https://example.com/test-evidence')).toBeVisible();
  72 |     await expect(freelancerPage.getByText('playwright-evidence.txt')).toBeVisible();
  73 |   } finally {
  74 |     await clientContext.close();
  75 |     await freelancerContext.close();
  76 |   }
  77 | });
  78 | 
  79 | 
```