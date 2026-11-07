ALTER TABLE integration_outbox
    ADD COLUMN IF NOT EXISTS smtp_delivered_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS webhook_delivered_at TIMESTAMPTZ;
