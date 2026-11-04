# TrustFlow browser flows

These Playwright scripts open a visible Chromium window and exercise the deployed TrustFlow test site. The default URL is https://trustflow-test.vercel.app/; set TRUSTFLOW_FRONTEND_URL to override it.

Covered flows:
- Invalid and successful sign-in, followed by sign-out.
- Workspace navigation, payment overview, insights, resources, account settings, and notification preferences.
- Client creates a project, freelancer accepts the invitation, client creates a milestone, and freelancer submits evidence.

## Install Playwright

From the repository's playwright folder:

    cd "/Users/bb.raghav/Desktop/TrustFlow(PayPal)/TrustFlow-team/playwright"
    npm install
    npx playwright install chromium

## Run against the deployed test site

Use existing test accounts registered in the deployed TrustFlow test environment:

    export TRUSTFLOW_FRONTEND_URL="https://trustflow-test.vercel.app/"
    export TRUSTFLOW_CLIENT_EMAIL="client@example.com"
    export TRUSTFLOW_CLIENT_PASSWORD="client-password"
    export TRUSTFLOW_FREELANCER_EMAIL="freelancer@example.com"
    export TRUSTFLOW_FREELANCER_PASSWORD="freelancer-password"
    npm test

The test config sets headless: false, and npm test passes --headed. You can also explicitly run:

    npx playwright test --headed

Individual scripts:

    npm run test:auth
    npm run test:workspace
    npm run test:collaboration

The collaboration flow writes project, milestone, and evidence records to the configured deployment. Run it only with the intended test accounts and test environment. Gemini assessment and PayPal checkout are not triggered because they require external provider setup and can have side effects.

