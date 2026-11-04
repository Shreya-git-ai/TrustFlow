# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: workspace.spec.js >> client can visit the main workspace sections
- Location: workspace.spec.js:7:1

# Error details

```
Error: locator.click: Error: strict mode violation: getByRole('button', { name: 'Payments' }) resolved to 2 elements:
    1) <button title="Payments" class="nav-link " aria-label="Payments">…</button> aka getByRole('button', { name: 'Payments', description: 'Payments' })
    2) <button type="button" class="pulse-metric-row pulse-payment-link">…</button> aka getByRole('button', { name: 'Payments in progress' })

Call log:
  - waiting for getByRole('button', { name: 'Payments' })

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - complementary [ref=e4]:
    - generic [ref=e5]:
      - link "TrustFlow home" [ref=e6] [cursor=pointer]:
        - /url: /
        - generic [ref=e7]: T
        - generic [ref=e8]: trustflow.
      - generic [ref=e9]: WORK, WITH A CLEAR PAPER TRAIL
    - generic [ref=e10]:
      - generic [ref=e11]: P
      - generic [ref=e12]:
        - generic [ref=e13]: YOUR WORKSPACE
        - strong [ref=e14]: Client studio
        - emphasis [ref=e15]: Personal workspace
      - generic [ref=e17]: ⌄
    - paragraph [ref=e18]: WORKSPACE
    - button "Overview" [ref=e19] [cursor=pointer]:
      - generic [aria-hidden] [ref=e20]: ▦
    - paragraph [ref=e22]:
      - text: WORKFLOW
      - generic [ref=e23]: LIVE
    - button "Payments" [ref=e24] [cursor=pointer]:
      - generic [aria-hidden] [ref=e25]: ↗
    - button "Insights" [ref=e27] [cursor=pointer]:
      - generic [aria-hidden] [ref=e28]: ▥
    - button "Resources" [ref=e30] [cursor=pointer]:
      - generic [aria-hidden] [ref=e31]: ⌘
    - generic [ref=e33]:
      - generic [ref=e34]:
        - generic [ref=e35]:
          - generic [ref=e36]: ✓
          - text: PAYMENT PARTNER
        - img "PayPal" [ref=e37]
        - strong [ref=e38]: Payments with a paper trail.
        - paragraph [ref=e39]: Clear agreements. Visible evidence. Human approval.
      - generic [ref=e40]:
        - generic [ref=e41]: P
        - generic [ref=e42]:
          - strong [ref=e43]: playwrightestclient@example.com
          - generic [ref=e44]: Client account
  - main [ref=e45]:
    - generic [ref=e46]:
      - generic [ref=e47]:
        - generic [ref=e48]:
          - generic [aria-hidden] [ref=e49]: ⌂
          - generic [ref=e50]:
            - generic [ref=e51]: YOUR WORKSPACE
            - strong [ref=e52]: Overview
        - generic [ref=e53]:
          - generic [aria-hidden] [ref=e54]: ⌕
          - textbox "Search projects" [ref=e55]:
            - /placeholder: Search projects…
          - generic [ref=e56]: ⌘ K
      - generic [ref=e57]:
        - generic "Powered by PayPal" [ref=e58]:
          - generic [ref=e59]: POWERED BY
          - img "PayPal" [ref=e60]
        - button "Open notifications" [ref=e63] [cursor=pointer]
        - button "Open account menu" [ref=e67] [cursor=pointer]:
          - generic [ref=e68]: P
          - generic [ref=e69]:
            - strong [ref=e70]: playwrightestclient@example.com
            - generic [ref=e71]: Client account
          - generic [aria-hidden] [ref=e72]: ⌄
    - generic [ref=e73]:
      - generic [ref=e74]:
        - generic [ref=e75]:
          - generic [ref=e76]: CLIENT WORKSPACE
          - heading [level=1] [ref=e77]:
            - text: Good work starts with
            - emphasis [ref=e78]: clarity.
          - paragraph [ref=e79]: Manage projects, review evidence, and keep payment decisions transparent.
          - generic [ref=e80]:
            - generic [ref=e81]: ◷ Monday, Nov 2
            - generic [ref=e82]: Email confirmed
        - button "＋ New project →" [ref=e84] [cursor=pointer]:
          - text: ＋ New project
          - generic [ref=e85]: →
      - generic [ref=e86]:
        - generic [ref=e87]:
          - generic [ref=e88]: ▦
          - generic [ref=e89]:
            - generic [ref=e90]: TOTAL PROJECTS
            - strong [ref=e91]: "0"
        - generic [ref=e92]:
          - generic [ref=e93]: ◇
          - generic [ref=e94]:
            - generic [ref=e95]: MILESTONES
            - strong [ref=e96]: "0"
        - generic [ref=e97]:
          - generic [ref=e98]: ◎
          - generic [ref=e99]:
            - generic [ref=e100]: SUBMISSIONS TO REVIEW
            - strong [ref=e101]: "0"
        - generic [ref=e102]:
          - generic [ref=e103]: ✓
          - generic [ref=e104]:
            - generic [ref=e105]: DECISIONS DUE
            - strong [ref=e106]: "0"
        - generic [ref=e107]:
          - generic [ref=e108]: $
          - generic [ref=e109]:
            - generic [ref=e110]: ACTIVE PAYMENTS
            - strong [ref=e111]: "0"
      - generic [ref=e112]:
        - generic [ref=e113]:
          - generic [ref=e115]:
            - text: YOUR COLLABORATIONS
            - heading "Projects 0" [level=2] [ref=e116]:
              - text: Projects
              - generic [ref=e117]: "0"
            - paragraph [ref=e118]: Keep agreements, revisions, and decisions together.
          - generic [ref=e119]:
            - tablist "Filter projects" [ref=e120]:
              - tab "All projects 0" [selected] [ref=e121] [cursor=pointer]:
                - text: All projects
                - generic [ref=e122]: "0"
              - tab "Active 0" [ref=e123] [cursor=pointer]:
                - text: Active
                - generic [ref=e124]: "0"
              - tab "Invitations 0" [ref=e125] [cursor=pointer]:
                - text: Invitations
                - generic [ref=e126]: "0"
            - generic [ref=e127]: 0 shown
          - generic [ref=e128]:
            - generic [ref=e129]:
              - generic [ref=e130]: ◇
              - generic [ref=e131]: ＋
            - heading "Your next collaboration starts here." [level=3] [ref=e132]
            - paragraph [ref=e133]: Create a project, set expectations, and invite a freelancer using their registered email.
            - button "Create your first project →" [ref=e134] [cursor=pointer]:
              - text: Create your first project
              - generic [ref=e135]: →
          - generic [ref=e136]:
            - generic [ref=e137]: Your project records stay together in one place.
            - generic [ref=e139]: ⌑ Privacy-first workspace
        - generic [ref=e140]:
          - generic [ref=e141]:
            - generic [ref=e142]:
              - generic [ref=e143]:
                - text: START A COLLABORATION
                - heading "New project" [level=2] [ref=e144]
              - generic [ref=e145]: ＋
            - generic [ref=e146]:
              - generic [ref=e147]:
                - text: Project name
                - textbox "Project name" [ref=e148]:
                  - /placeholder: Website redesign
              - generic [ref=e149]:
                - text: Freelancer account email
                - textbox "Freelancer account email" [ref=e150]:
                  - /placeholder: name@example.com
              - generic [ref=e151]:
                - text: Project description
                - textbox "Project description" [ref=e152]:
                  - /placeholder: What are you building together?
              - generic [ref=e153]:
                - text: Currency
                - textbox "Currency" [ref=e154]: USD
              - button "Create project →" [disabled] [ref=e155]:
                - text: Create project
                - generic [ref=e156]: →
              - generic [ref=e157]: The freelancer must already have a TrustFlow account to receive the invitation.
          - generic [ref=e158]:
            - generic [ref=e159]:
              - generic [ref=e160]:
                - text: AT A GLANCE
                - heading "Workspace pulse" [level=2] [ref=e161]
              - generic [aria-hidden] [ref=e162]: ◌
            - generic [ref=e163]:
              - strong [ref=e164]: "0"
              - generic [ref=e165]: projects in your workspace
            - img "0 active projects, 0 pending invitations" [ref=e166]
            - generic [ref=e167]:
              - button [ref=e168] [cursor=pointer]:
                - text: Active
                - strong [ref=e170]: "0"
              - button [ref=e171] [cursor=pointer]:
                - text: Invitations
                - strong [ref=e173]: "0"
            - generic [ref=e175]:
              - generic [ref=e176]: Milestones across projects
              - strong [ref=e177]: "0"
            - generic [ref=e178]:
              - generic [ref=e179]: Awaiting your decision
              - strong [ref=e180]: "0"
            - button "Payments in progress 0" [ref=e181] [cursor=pointer]:
              - generic [ref=e182]: Payments in progress
              - strong [ref=e183]: 0↗
            - paragraph [ref=e184]: Counts update from your current project records.
      - generic [ref=e185]:
        - generic [ref=e186]:
          - generic [ref=e187]:
            - generic [ref=e188]:
              - text: WORKSPACE UPDATES
              - heading "Recent activity" [level=2] [ref=e189]
              - paragraph [ref=e190]: Updates recorded across your projects.
            - button "View insights →" [ref=e191] [cursor=pointer]
          - generic [ref=e192]:
            - strong [ref=e193]: No activity yet
            - paragraph [ref=e194]: Project creation, submissions, decisions, and payment updates will appear here.
        - generic [ref=e195]:
          - generic [ref=e196]:
            - generic [ref=e197]:
              - text: ACCOUNT SNAPSHOT
              - heading "Your workspace details" [level=2] [ref=e198]
              - paragraph [ref=e199]: Current account and verification status.
            - button "Open account settings" [ref=e200] [cursor=pointer]: ↗
          - generic [ref=e201]:
            - generic [ref=e202]: P
            - generic [ref=e203]:
              - strong [ref=e204]: playwrightestclient@example.com
              - generic [ref=e205]: playwrightestclient@example.com
            - generic [ref=e206]: Verified
          - generic [ref=e208]:
            - generic [ref=e209]:
              - generic [ref=e210]: ACCOUNT ROLE
              - strong [ref=e211]: Client
            - generic [ref=e212]:
              - generic [ref=e213]: WORKSPACE
              - strong [ref=e214]: Client studio
            - generic [ref=e215]:
              - generic [ref=e216]: PROJECTS
              - strong [ref=e217]: 0 total
            - generic [ref=e218]:
              - generic [ref=e219]: SECURITY
              - strong [ref=e220]: Email confirmed
          - button "Manage account settings →" [ref=e221] [cursor=pointer]:
            - text: Manage account settings
            - generic [ref=e222]: →
```

# Test source

```ts
  1  | const { test, expect } = require('@playwright/test');
  2  | const { fillSignIn } = require('./helpers');
  3  | 
  4  | const email = process.env.TRUSTFLOW_CLIENT_EMAIL;
  5  | const password = process.env.TRUSTFLOW_CLIENT_PASSWORD;
  6  | 
  7  | test('client can visit the main workspace sections', async ({ page }) => {
  8  |   test.skip(!email || !password, 'Set TRUSTFLOW_CLIENT_EMAIL and TRUSTFLOW_CLIENT_PASSWORD.');
  9  |   await fillSignIn(page, email, password);
  10 |   await page.getByRole('button', { name: /sign in/i }).click();
  11 |   await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');
  12 | 
> 13 |   await page.getByRole('button', { name: 'Payments' }).click();
     |                                                        ^ Error: locator.click: Error: strict mode violation: getByRole('button', { name: 'Payments' }) resolved to 2 elements:
  14 |   await expect(page.getByRole('heading', { name: 'Payments', exact: true })).toBeVisible();
  15 |   await expect(page.getByRole('heading', { name: 'Milestone payments' })).toBeVisible();
  16 |   await page.getByRole('button', { name: 'Insights' }).click();
  17 |   await expect(page.getByRole('heading', { name: 'Insights', exact: true })).toBeVisible();
  18 |   await page.getByRole('button', { name: 'Resources' }).click();
  19 |   await expect(page.getByRole('heading', { name: 'Resources', exact: true })).toBeVisible();
  20 |   await page.getByRole('button', { name: 'Overview' }).click();
  21 |   await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');
  22 | });
  23 | 
  24 | test('account settings and notification preferences are available', async ({ page }) => {
  25 |   test.skip(!email || !password, 'Set TRUSTFLOW_CLIENT_EMAIL and TRUSTFLOW_CLIENT_PASSWORD.');
  26 |   await fillSignIn(page, email, password);
  27 |   await page.getByRole('button', { name: /sign in/i }).click();
  28 |   await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');
  29 | 
  30 |   await page.getByRole('button', { name: 'Open account settings' }).click();
  31 |   await expect(page.getByRole('heading', { name: 'Account settings' })).toBeVisible();
  32 |   await expect(page.getByText('Project updates', { exact: true })).toBeVisible();
  33 |   await expect(page.getByText('Payment alerts', { exact: true })).toBeVisible();
  34 |   await expect(page.locator('input[type="checkbox"]')).toHaveCount(2);
  35 | });
  36 | 
  37 | test('notification centre opens and supports its empty or mark-read state', async ({ page }) => {
  38 |   test.skip(!email || !password, 'Set TRUSTFLOW_CLIENT_EMAIL and TRUSTFLOW_CLIENT_PASSWORD.');
  39 |   await fillSignIn(page, email, password);
  40 |   await page.getByRole('button', { name: /sign in/i }).click();
  41 |   await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');
  42 | 
  43 |   await page.getByRole('button', { name: /open notifications/i }).click();
  44 |   const dialog = page.getByRole('dialog', { name: 'Notification centre' });
  45 |   await expect(dialog).toBeVisible();
  46 |   const markRead = dialog.getByRole('button', { name: 'Mark all read' });
  47 |   if (await markRead.isEnabled()) {
  48 |     await markRead.click();
  49 |     await expect(dialog.getByRole('button', { name: 'All caught up' })).toBeDisabled();
  50 |   } else {
  51 |     await expect(dialog.getByText('You’re all caught up.')).toBeVisible();
  52 |   }
  53 | });
  54 | 
  55 | 
```