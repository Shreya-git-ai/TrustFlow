CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL CHECK (role IN ('client', 'freelancer')),
    paypal_merchant_id TEXT,
    paypal_onboarding_tracking_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES users(id),
    freelancer_id UUID REFERENCES users(id),
    invited_email TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'cancelled')),
    membership_status TEXT NOT NULL DEFAULT 'invited'
        CHECK (membership_status IN ('invited', 'accepted', 'declined', 'cancelled')),
    membership_accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    title TEXT NOT NULL,
    acceptance_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    due_at TIMESTAMPTZ,
    agreement_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (agreement_status IN ('pending', 'accepted', 'changes_requested')),
    agreement_note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'in_progress', 'submitted',
            'approved', 'rejected', 'paid'
        )),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    milestone_id UUID NOT NULL REFERENCES milestones(id),
    source TEXT NOT NULL DEFAULT 'manual',
    source_url TEXT,
    description TEXT,
    assessment JSONB,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    milestone_id UUID NOT NULL UNIQUE REFERENCES milestones(id),
    provider TEXT NOT NULL DEFAULT 'paypal',
    paypal_order_id TEXT UNIQUE,
    paypal_authorization_id TEXT UNIQUE,
    paypal_capture_id TEXT UNIQUE,
    paypal_payee_merchant_id TEXT,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'created'
        CHECK (status IN (
            'created', 'buyer_approved', 'authorized',
            'capture_pending', 'captured', 'failed', 'voided'
        )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    milestone_id UUID REFERENCES milestones(id),
    payment_id UUID REFERENCES payments(id),
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    processing_status TEXT NOT NULL DEFAULT 'received'
        CHECK (processing_status IN ('received', 'processed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_freelancer ON projects(freelancer_id);
CREATE INDEX IF NOT EXISTS idx_milestones_project ON milestones(project_id);
CREATE INDEX IF NOT EXISTS idx_evidence_milestone ON evidence(milestone_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at DESC);

CREATE TABLE IF NOT EXISTS notification_reads (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    audit_event_id BIGINT NOT NULL REFERENCES audit_events(id) ON DELETE CASCADE,
    read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, audit_event_id)
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    project_updates BOOLEAN NOT NULL DEFAULT TRUE,
    payment_alerts BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
