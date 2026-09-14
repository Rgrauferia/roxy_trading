-- Manual additive migration, executed by the separate Home database owner.
-- Requires 001_foundation.sql. No automatic production migration.
-- Runtime role needs SELECT/INSERT/UPDATE/DELETE on these two private tables;
-- runtime must not own them, inherit the owner role, or bypass row security.
BEGIN;
CREATE TABLE roxy_home_fitness.measurements_state (
    member_id TEXT PRIMARY KEY CHECK (length(member_id) BETWEEN 1 AND 128),
    version BIGINT NOT NULL DEFAULT 0 CHECK (version >= 0 AND version < 9007199254740992),
    measurements JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(measurements) = 'array' AND jsonb_array_length(measurements) <= 500),
    consent JSONB CHECK (consent IS NULL OR jsonb_typeof(consent) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE roxy_home_fitness.measurements_idempotency (
    member_id TEXT NOT NULL REFERENCES roxy_home_fitness.measurements_state(member_id) ON DELETE CASCADE,
    request_key TEXT NOT NULL CHECK (length(request_key) BETWEEN 8 AND 128),
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    response_version BIGINT NOT NULL CHECK (response_version >= 0 AND response_version < 9007199254740992),
    PRIMARY KEY (member_id, request_key)
);
REVOKE ALL ON roxy_home_fitness.measurements_state, roxy_home_fitness.measurements_idempotency FROM PUBLIC;
ALTER TABLE roxy_home_fitness.measurements_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.measurements_state FORCE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.measurements_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.measurements_idempotency FORCE ROW LEVEL SECURITY;
CREATE POLICY member_only ON roxy_home_fitness.measurements_state
    USING (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''))
    WITH CHECK (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''));
CREATE POLICY member_only ON roxy_home_fitness.measurements_idempotency
    USING (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''))
    WITH CHECK (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''));
COMMENT ON TABLE roxy_home_fitness.measurements_state IS
    'Optional member-private self-reported weight and height with separate consent. No diagnosis, BMI, calories or inferred goal. Erasure retains only a version tombstone; backup expiry is separate.';
COMMENT ON TABLE roxy_home_fitness.measurements_idempotency IS
    'Latest per-member mutation hash/version only; never stores measurement response bodies.';
COMMIT;
