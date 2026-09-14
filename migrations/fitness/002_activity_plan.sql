-- Manual additive migration, run by the separate Home database owner.
-- Requires 001_foundation.sql; preferences v1 remain compatible.
-- Runtime role: USAGE on schema, SELECT/INSERT/UPDATE/DELETE on these two tables.
-- Runtime must not be owner, superuser, BYPASSRLS, or a member of the owner role.
BEGIN;
CREATE TABLE roxy_home_fitness.activity_plan_state (
    member_id TEXT PRIMARY KEY CHECK (length(member_id) BETWEEN 1 AND 128),
    version BIGINT NOT NULL DEFAULT 0 CHECK (version >= 0 AND version < 9007199254740992),
    plan JSONB CHECK (plan IS NULL OR jsonb_typeof(plan) = 'object'),
    consent JSONB CHECK (consent IS NULL OR jsonb_typeof(consent) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE roxy_home_fitness.activity_plan_idempotency (
    member_id TEXT NOT NULL REFERENCES roxy_home_fitness.activity_plan_state(member_id) ON DELETE CASCADE,
    request_key TEXT NOT NULL CHECK (length(request_key) BETWEEN 8 AND 128),
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    response_version BIGINT NOT NULL,
    PRIMARY KEY (member_id, request_key)
);
REVOKE ALL ON roxy_home_fitness.activity_plan_state, roxy_home_fitness.activity_plan_idempotency FROM PUBLIC;
ALTER TABLE roxy_home_fitness.activity_plan_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.activity_plan_state FORCE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.activity_plan_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.activity_plan_idempotency FORCE ROW LEVEL SECURITY;
CREATE POLICY member_only ON roxy_home_fitness.activity_plan_state
    USING (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''))
    WITH CHECK (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''));
CREATE POLICY member_only ON roxy_home_fitness.activity_plan_idempotency
    USING (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''))
    WITH CHECK (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''));
COMMENT ON TABLE roxy_home_fitness.activity_plan_state IS
    'Member-private educational guide selection, voluntary schedule and self-reported completion. No clinical prescription. Retains version tombstones after erasure.';
COMMIT;
