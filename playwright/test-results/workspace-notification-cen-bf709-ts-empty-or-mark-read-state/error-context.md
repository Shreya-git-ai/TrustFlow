# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: workspace.spec.js >> notification centre opens and supports its empty or mark-read state
- Location: workspace.spec.js:37:1

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.isEnabled: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('dialog', { name: 'Notification centre' }).getByRole('button', { name: 'Mark all read' })

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
            - strong [ref=e91]: "1"
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
            - heading "Projects 1" [level=2] [ref=e116]:
              - text: Projects
              - generic [ref=e117]: "1"
            - paragraph [ref=e118]: Keep agreements, revisions, and decisions together.
          - generic [ref=e119]:
            - tablist "Filter projects" [ref=e120]:
              - tab "All projects 1" [selected] [ref=e121] [cursor=pointer]:
                - text: All projects
                - generic [ref=e122]: "1"
              - tab "Active 0" [ref=e123] [cursor=pointer]:
                - text: Active
                - generic [ref=e124]: "0"
              - tab "Invitations 1" [ref=e125] [cursor=pointer]:
                - text: Invitations
                - generic [ref=e126]: "1"
            - generic [ref=e127]: 1 shown
          - generic [ref=e128]:
            - generic [ref=e129]:
              - generic [ref=e130]:
                - generic [aria-hidden] [ref=e131]: ⌕
                - searchbox "Search projects, people, or actions" [ref=e132]
              - generic [ref=e133]:
                - status [ref=e134]: of 1 projects
                - button "Export CSV" [ref=e135] [cursor=pointer]:
                  - generic [aria-hidden] [ref=e136]: ↓
                  - text: Export CSV
            - generic "Projects" [ref=e137]:
              - generic [ref=e140]:
                - generic [ref=e141]: No Rows To Show. 1 to 1 of 1. Page 1 of 1
                - grid [ref=e142]:
                  - rowgroup [ref=e143]:
                    - row [ref=e144]:
                      - columnheader "Project" [ref=e145]
                      - columnheader "Freelancer" [ref=e148]
                      - columnheader "Needs attention" [ref=e151]:
                        - generic [ref=e154] [cursor=pointer]
                      - columnheader "Milestones" [ref=e156]
                      - columnheader "Payments" [ref=e159]
                      - columnheader "Status" [ref=e162]
                    - row [ref=e165]:
                      - gridcell [ref=e166]:
                        - textbox "Project Filter Input" [ref=e167]
                        - button "Open Filter Menu" [ref=e169] [cursor=pointer]
                      - gridcell [ref=e170]:
                        - textbox "Freelancer Filter Input" [ref=e171]
                        - button "Open Filter Menu" [ref=e173] [cursor=pointer]
                      - gridcell [ref=e174]:
                        - textbox "Needs attention Filter Input" [ref=e175]
                        - button "Open Filter Menu" [ref=e177] [cursor=pointer]
                      - gridcell [ref=e178]:
                        - spinbutton "Milestones Filter Input" [ref=e179]
                        - button "Open Filter Menu" [ref=e181] [cursor=pointer]
                      - gridcell [ref=e182]:
                        - textbox "Payments Filter Input" [ref=e183]
                        - button "Open Filter Menu" [ref=e185] [cursor=pointer]
                      - gridcell [ref=e186]:
                        - textbox "Status Filter Input" [ref=e187]
                        - button "Open Filter Menu" [ref=e189] [cursor=pointer]
                    - row [ref=e190]:
                      - gridcell "Playwright collaboration 1793639834704 Browser test collaboration." [ref=e191]:
                        - generic [ref=e192]:
                          - strong [ref=e193]: Playwright collaboration 1793639834704
                          - generic [ref=e194]: Browser test collaboration.
                      - gridcell "playwrightfl@example.com" [ref=e195]
                      - gridcell "Invitation pending" [ref=e196]
                      - gridcell "0" [ref=e198]
                      - gridcell "None active" [ref=e199]
                      - gridcell "Invitation pending" [ref=e200]
                - generic [ref=e203]:
                  - generic [ref=e204]:
                    - generic [ref=e205]: "Page Size:"
                    - combobox "Page Size" [ref=e206]:
                      - generic [ref=e207]: "8"
                      - generic [aria-hidden] [ref=e208] [cursor=pointer]
                  - generic [ref=e209]: 1 to 1 of 1
                  - button "First Page" [disabled] [ref=e211]
                  - button "Previous Page" [disabled] [ref=e212]
                  - generic [ref=e213]:
                    - text: Page
                    - spinbutton "Page number, 1 of 1" [ref=e214]: "1"
                    - text: of 1
                  - button "Next Page" [disabled] [ref=e215]
                  - button "Last Page" [disabled] [ref=e216]
          - generic [ref=e217]:
            - generic [ref=e218]: Your project records stay together in one place.
            - generic [ref=e220]: ⌑ Privacy-first workspace
        - generic [ref=e221]:
          - generic [ref=e222]:
            - generic [ref=e223]:
              - generic [ref=e224]:
                - text: START A COLLABORATION
                - heading "New project" [level=2] [ref=e225]
              - generic [ref=e226]: ＋
            - generic [ref=e227]:
              - generic [ref=e228]:
                - text: Project name
                - textbox "Project name" [ref=e229]:
                  - /placeholder: Website redesign
              - generic [ref=e230]:
                - text: Freelancer account email
                - textbox "Freelancer account email" [ref=e231]:
                  - /placeholder: name@example.com
              - generic [ref=e232]:
                - text: Project description
                - textbox "Project description" [ref=e233]:
                  - /placeholder: What are you building together?
              - generic [ref=e234]:
                - text: Currency
                - textbox "Currency" [ref=e235]: USD
              - button "Create project →" [ref=e236] [cursor=pointer]:
                - text: Create project
                - generic [ref=e237]: →
              - generic [ref=e238]: The freelancer must already have a TrustFlow account to receive the invitation.
          - generic [ref=e239]:
            - generic [ref=e240]:
              - generic [ref=e241]:
                - text: AT A GLANCE
                - heading "Workspace pulse" [level=2] [ref=e242]
              - generic [aria-hidden] [ref=e243]: ◌
            - generic [ref=e244]:
              - strong [ref=e245]: "1"
              - generic [ref=e246]: projects in your workspace
            - img "0 active projects, 1 pending invitations" [ref=e247]
            - generic [ref=e249]:
              - button [ref=e250] [cursor=pointer]:
                - text: Active
                - strong [ref=e252]: "0"
              - button [ref=e253] [cursor=pointer]:
                - text: Invitations
                - strong [ref=e255]: "1"
            - generic [ref=e257]:
              - generic [ref=e258]: Milestones across projects
              - strong [ref=e259]: "0"
            - generic [ref=e260]:
              - generic [ref=e261]: Awaiting your decision
              - strong [ref=e262]: "0"
            - button "Payments in progress 0" [ref=e263] [cursor=pointer]:
              - generic [ref=e264]: Payments in progress
              - strong [ref=e265]: 0↗
            - paragraph [ref=e266]: Counts update from your current project records.
      - generic [ref=e267]:
        - generic [ref=e268]:
          - generic [ref=e269]:
            - generic [ref=e270]:
              - text: WORKSPACE UPDATES
              - heading "Recent activity" [level=2] [ref=e271]
              - paragraph [ref=e272]: Updates recorded across your projects.
            - button "View insights →" [ref=e273] [cursor=pointer]
          - button "↗ Project created Playwright collaboration 1793639834704 11/2/2026, 10:47:18 PM · client" [ref=e275] [cursor=pointer]:
            - generic [ref=e276]: ↗
            - generic [ref=e277]:
              - strong [ref=e278]: Project created
              - generic [ref=e279]: Playwright collaboration 1793639834704
              - generic [ref=e280]: 11/2/2026, 10:47:18 PM · client
            - generic [aria-hidden] [ref=e281]: ↗
        - generic [ref=e282]:
          - generic [ref=e283]:
            - generic [ref=e284]:
              - text: ACCOUNT SNAPSHOT
              - heading "Your workspace details" [level=2] [ref=e285]
              - paragraph [ref=e286]: Current account and verification status.
            - button "Open account settings" [ref=e287] [cursor=pointer]: ↗
          - generic [ref=e288]:
            - generic [ref=e289]: P
            - generic [ref=e290]:
              - strong [ref=e291]: playwrightestclient@example.com
              - generic [ref=e292]: playwrightestclient@example.com
            - generic [ref=e293]: Verified
          - generic [ref=e295]:
            - generic [ref=e296]:
              - generic [ref=e297]: ACCOUNT ROLE
              - strong [ref=e298]: Client
            - generic [ref=e299]:
              - generic [ref=e300]: WORKSPACE
              - strong [ref=e301]: Client studio
            - generic [ref=e302]:
              - generic [ref=e303]: PROJECTS
              - strong [ref=e304]: 1 total
            - generic [ref=e305]:
              - generic [ref=e306]: SECURITY
              - strong [ref=e307]: Email confirmed
          - button "Manage account settings →" [ref=e308] [cursor=pointer]:
            - text: Manage account settings
            - generic [ref=e309]: →
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
  13 |   await page.getByRole('button', { name: 'Payments' }).click();
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
> 47 |   if (await markRead.isEnabled()) {
     |                      ^ Error: locator.isEnabled: Test timeout of 30000ms exceeded.
  48 |     await markRead.click();
  49 |     await expect(dialog.getByRole('button', { name: 'All caught up' })).toBeDisabled();
  50 |   } else {
  51 |     await expect(dialog.getByText('You’re all caught up.')).toBeVisible();
  52 |   }
  53 | });
  54 | 
  55 | 
```