-- Agent refund recommendations require a separate, human-reviewed payment flow.
ALTER TABLE payments ADD COLUMN IF NOT EXISTS refunded_amount NUMERIC(12, 2) NOT NULL DEFAULT 0;
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_status_check;
ALTER TABLE payments ADD CONSTRAINT payments_status_check
    CHECK (status IN (
        'created', 'buyer_approved', 'authorized', 'capture_pending', 'captured',
        'partially_refunded', 'refunded', 'failed', 'voided'
    ));

CREATE TABLE IF NOT EXISTS refund_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    proposal_key TEXT NOT NULL UNIQUE,
    agent_name TEXT NOT NULL DEFAULT 'TrustFlow Refund Agent',
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'refunded', 'rejected', 'failed')),
    zendesk_ticket_id BIGINT CHECK (zendesk_ticket_id > 0),
    slack_channel_id TEXT,
    slack_thread_ts TEXT,
    paypal_request_id TEXT NOT NULL UNIQUE,
    paypal_refund_id TEXT UNIQUE,
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_refund_proposals_payment_status
    ON refund_proposals(payment_id, status, proposed_at DESC);

CREATE TABLE IF NOT EXISTS payment_refunds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    proposal_id UUID REFERENCES refund_proposals(id) ON DELETE SET NULL,
    paypal_refund_id TEXT NOT NULL UNIQUE,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED')),
    webhook_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    webhook_event_id TEXT,
    completion_notified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE payment_refunds ADD COLUMN IF NOT EXISTS completion_notified BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_payment_refunds_payment_status
    ON payment_refunds(payment_id, status);
