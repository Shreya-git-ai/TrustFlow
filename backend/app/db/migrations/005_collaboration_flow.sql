-- Complete invitations, mutual milestone terms, and server-backed notification reads.
ALTER TABLE users ADD COLUMN IF NOT EXISTS paypal_merchant_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS paypal_onboarding_tracking_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS paypal_payee_merchant_id TEXT;
ALTER TABLE projects ALTER COLUMN freelancer_id DROP NOT NULL;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS invited_email TEXT;
UPDATE projects project
SET invited_email = freelancer.email
FROM users freelancer
WHERE freelancer.id = project.freelancer_id AND project.invited_email IS NULL;
ALTER TABLE projects ALTER COLUMN invited_email SET NOT NULL;
ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_membership_status_check;
ALTER TABLE projects ADD CONSTRAINT projects_membership_status_check
    CHECK (membership_status IN ('invited', 'accepted', 'declined', 'cancelled'));
CREATE INDEX IF NOT EXISTS idx_projects_invited_email ON projects (lower(invited_email));

ALTER TABLE milestones ADD COLUMN IF NOT EXISTS agreement_status TEXT;
UPDATE milestones SET agreement_status = 'accepted' WHERE agreement_status IS NULL;
ALTER TABLE milestones ALTER COLUMN agreement_status SET DEFAULT 'pending';
ALTER TABLE milestones ALTER COLUMN agreement_status SET NOT NULL;
ALTER TABLE milestones ADD COLUMN IF NOT EXISTS agreement_note TEXT NOT NULL DEFAULT '';
ALTER TABLE milestones DROP CONSTRAINT IF EXISTS milestones_agreement_status_check;
ALTER TABLE milestones ADD CONSTRAINT milestones_agreement_status_check
    CHECK (agreement_status IN ('pending', 'accepted', 'changes_requested'));

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
