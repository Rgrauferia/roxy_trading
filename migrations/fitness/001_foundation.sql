-- Manual, Home-only migration. Never executed automatically by application startup.
-- Provision a separate database/owner, encrypted connection/storage/backups and
-- a least-privilege runtime role BEFORE enabling ROXY_HOME_FITNESS_DATABASE_URL.
-- The runtime role must NOT own these tables, be superuser or have BYPASSRLS.
-- Do not grant the runtime role schema CREATE, DDL or membership of the owner role.
-- An operator must grant that role only USAGE on this schema, SELECT on schema_version
-- and SELECT/INSERT/UPDATE/DELETE on the two member tables. No PUBLIC grant.
BEGIN;
CREATE SCHEMA roxy_home_fitness;
REVOKE ALL ON SCHEMA roxy_home_fitness FROM PUBLIC;

CREATE TABLE roxy_home_fitness.schema_version (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    version INTEGER NOT NULL CHECK (version = 1)
);
INSERT INTO roxy_home_fitness.schema_version (singleton, version) VALUES (TRUE, 1);

CREATE TABLE roxy_home_fitness.member_state (
    member_id TEXT PRIMARY KEY CHECK (length(member_id) BETWEEN 1 AND 128),
    version BIGINT NOT NULL DEFAULT 0 CHECK (version >= 0 AND version < 9007199254740992),
    profile JSONB CHECK (profile IS NULL OR jsonb_typeof(profile) = 'object'),
    consent JSONB CHECK (consent IS NULL OR jsonb_typeof(consent) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE roxy_home_fitness.idempotency (
    member_id TEXT NOT NULL REFERENCES roxy_home_fitness.member_state(member_id) ON DELETE CASCADE,
    request_key TEXT NOT NULL CHECK (length(request_key) BETWEEN 8 AND 128),
    request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
    response_version BIGINT NOT NULL,
    PRIMARY KEY (member_id, request_key)
);
REVOKE ALL ON ALL TABLES IN SCHEMA roxy_home_fitness FROM PUBLIC;

ALTER TABLE roxy_home_fitness.member_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.member_state FORCE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE roxy_home_fitness.idempotency FORCE ROW LEVEL SECURITY;
CREATE POLICY member_only ON roxy_home_fitness.member_state
    USING (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''))
    WITH CHECK (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''));
CREATE POLICY member_only ON roxy_home_fitness.idempotency
    USING (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''))
    WITH CHECK (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''));

COMMENT ON TABLE roxy_home_fitness.member_state IS
    'Non-clinical preferences by authenticated member; deletion clears JSON but retains a version tombstone to reject stale requests. Backup retention is managed separately.';
COMMENT ON TABLE roxy_home_fitness.idempotency IS
    'Only the latest per-member mutation hash/version; never stores profile or clinical response bodies.';
COMMIT;
