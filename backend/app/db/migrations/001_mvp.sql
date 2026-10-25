-- Additive migration for accounts, evidence revisions, assessment history,
-- explicit client decisions, and durable PayPal request state.
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users (lower(email));

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_hash TEXT PRIMARY KEY,
    csrf_token TEXT NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at);

CREATE TABLE IF NOT EXISTS auth_login_attempts (
    email TEXT NOT NULL,
    ip_hash TEXT NOT NULL,
    window_started_at TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(email, ip_hash)
);

ALTER TABLE projects ADD COLUMN IF NOT EXISTS membership_status TEXT NOT NULL DEFAULT 'accepted';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS membership_accepted_at TIMESTAMPTZ;
ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_membership_status_check;
ALTER TABLE projects ADD CONSTRAINT projects_membership_status_check
    CHECK (membership_status IN ('invited', 'accepted', 'declined'));
UPDATE projects SET membership_accepted_at = created_at
WHERE membership_status = 'accepted' AND membership_accepted_at IS NULL;

ALTER TABLE milestones ADD COLUMN IF NOT EXISTS evidence_revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE milestones ADD COLUMN IF NOT EXISTS currency CHAR(3);
UPDATE milestones m SET currency = p.currency FROM projects p WHERE p.id = m.project_id AND m.currency IS NULL;
UPDATE milestones SET currency = 'USD' WHERE currency IS NULL;
ALTER TABLE milestones ALTER COLUMN currency SET DEFAULT 'USD';
ALTER TABLE milestones ALTER COLUMN currency SET NOT NULL;
ALTER TABLE milestones ADD COLUMN IF NOT EXISTS approved_evidence_revision INTEGER;
ALTER TABLE milestones ADD COLUMN IF NOT EXISTS approved_assessment_id UUID;
ALTER TABLE milestones DROP CONSTRAINT IF EXISTS milestones_status_check;
ALTER TABLE milestones ADD CONSTRAINT milestones_status_check
    CHECK (status IN ('pending', 'in_progress', 'submitted', 'revision_requested', 'approved', 'rejected', 'paid'));

ALTER TABLE evidence ADD COLUMN IF NOT EXISTS evidence_revision INTEGER NOT NULL DEFAULT 1;
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS evidence_text TEXT NOT NULL DEFAULT '';
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS evidence_links JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS file_key TEXT;
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS file_name TEXT;
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS file_content_type TEXT;
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS file_data BYTEA;
WITH duplicate_milestones AS (
    SELECT milestone_id FROM evidence
    GROUP BY milestone_id HAVING COUNT(*) > COUNT(DISTINCT evidence_revision)
), resequenced AS (
    SELECT e.id, ROW_NUMBER() OVER (PARTITION BY e.milestone_id ORDER BY e.submitted_at, e.id)::INTEGER AS revision
    FROM evidence e JOIN duplicate_milestones d ON d.milestone_id = e.milestone_id
)
UPDATE evidence e SET evidence_revision = r.revision FROM resequenced r WHERE e.id = r.id;
UPDATE milestones m SET evidence_revision = GREATEST(m.evidence_revision, COALESCE(
    (SELECT MAX(e.evidence_revision) FROM evidence e WHERE e.milestone_id = m.id), 0
));
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_milestone_revision ON evidence(milestone_id, evidence_revision);

CREATE TABLE IF NOT EXISTS assessment_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    milestone_id UUID NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    evidence_revision INTEGER NOT NULL,
    report_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'empty_evidence', 'invalid_output', 'provider_error')),
    all_met BOOLEAN NOT NULL DEFAULT FALSE,
    is_stale BOOLEAN NOT NULL DEFAULT FALSE,
    result_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(milestone_id, evidence_revision, report_version)
);
CREATE INDEX IF NOT EXISTS idx_assessment_reports_milestone ON assessment_reports(milestone_id, created_at DESC);
ALTER TABLE milestones DROP CONSTRAINT IF EXISTS milestones_approved_assessment_fk;
ALTER TABLE milestones ADD CONSTRAINT milestones_approved_assessment_fk
    FOREIGN KEY (approved_assessment_id) REFERENCES assessment_reports(id);

CREATE TABLE IF NOT EXISTS assessment_findings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id UUID NOT NULL REFERENCES assessment_reports(id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    explanation TEXT NOT NULL,
    quote TEXT,
    missing_or_contradictory JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommended_next_action TEXT,
    UNIQUE(report_id, criterion_id)
);

CREATE TABLE IF NOT EXISTS milestone_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    milestone_id UUID NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'revision_requested', 'revoked')),
    evidence_revision INTEGER NOT NULL,
    assessment_report_id UUID REFERENCES assessment_reports(id),
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE milestone_decisions ADD COLUMN IF NOT EXISTS decision_no BIGINT GENERATED ALWAYS AS IDENTITY;
CREATE UNIQUE INDEX IF NOT EXISTS idx_milestone_decision_no ON milestone_decisions(decision_no);
CREATE INDEX IF NOT EXISTS idx_milestone_decisions_latest ON milestone_decisions(milestone_id, created_at DESC);

ALTER TABLE payments ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS create_request_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS paypal_approval_url TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS authorize_request_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS capture_request_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS last_provider_error TEXT;

ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS payload JSONB;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE webhook_events DROP CONSTRAINT IF EXISTS webhook_events_processing_status_check;
ALTER TABLE webhook_events ADD CONSTRAINT webhook_events_processing_status_check
    CHECK (processing_status IN ('received', 'processing', 'processed', 'failed'));

ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS actor_id UUID REFERENCES users(id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

CREATE TABLE IF NOT EXISTS integration_outbox (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_name TEXT NOT NULL,
    dedupe_key TEXT UNIQUE,
    payload JSONB NOT NULL,
    delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK (delivery_status IN ('pending', 'delivered')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_until TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_integration_outbox_pending ON integration_outbox(next_attempt_at, id)
    WHERE delivery_status = 'pending';
