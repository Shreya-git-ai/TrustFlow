# Backend demo checklist

1. Start the backend from `backend/` using `python -m app.main` after following the setup in the root README and configuring sandbox credentials.
2. Call `GET /health` and `GET /paypal/test-auth`.
3. Call `POST /paypal/create-order` with a sandbox amount and currency, then follow its `approvalUrl` in the PayPal sandbox.
4. After buyer approval, submit the order ID to `POST /paypal/authorize-order`.
5. For a sandbox-only capture demonstration, call `POST /paypal/capture-authorization` with the returned authorization ID and `milestoneApproved: true`.
6. Optionally check `GET /db/test` after configuring a test PostgreSQL database. Review the schema before calling `POST /db/setup-schema`.

The frontend currently supports evidence assessment only; these PayPal steps remain API-only. No live transaction, webhook, or persisted payment record is part of this demo.
