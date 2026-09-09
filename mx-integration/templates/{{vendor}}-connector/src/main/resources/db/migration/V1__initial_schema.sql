-- V1__initial_schema.sql
-- Inbox/outbox tables required by mx-worker-spring-boot-starter, plus subscription state.
--
-- Column names and types are a framework contract, not a local choice: the starter's
-- repositories query these directly. Add columns in later migrations; do not rename these.
--
-- Later migrations are V2, V3, ... in order, named V##__snake_case.sql. Flyway will not
-- reorder them and will not re-run a checksum that changed, so an edit to this file after
-- it has been applied anywhere is a failed deploy.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE inbox (
    id BIGSERIAL PRIMARY KEY,
    headers JSONB NOT NULL,
    body BYTEA,
    otel_context JSONB,
    enqueued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    message_key TEXT NOT NULL,
    connector_msg_type TEXT,
    nattempts INTEGER NOT NULL DEFAULT 0,
    run_after TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE inbox_dead_letter (
    id                   BIGSERIAL PRIMARY KEY,
    headers              JSONB       NOT NULL,
    body                 BYTEA,
    message_key          TEXT        NOT NULL,
    connector_msg_type   TEXT,
    otel_context         JSONB,
    failed_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    error_message        TEXT        NOT NULL,
    original_enqueued_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE subscription_state (
    subscription_id    UUID PRIMARY KEY,
    status             TEXT        NOT NULL,
    last_input_version INTEGER     NOT NULL DEFAULT 0,
    last_seen_m_type   TEXT,
    created_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    cancelled_at       TIMESTAMP WITH TIME ZONE
);

CREATE TABLE outbox (
    id           BIGSERIAL PRIMARY KEY,
    topic        TEXT        NOT NULL,
    headers      JSONB       NOT NULL,
    body         BYTEA       NOT NULL,
    message_key  TEXT        NOT NULL,
    otel_context JSONB,
    enqueued_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    nattempts    INTEGER     NOT NULL DEFAULT 0,
    run_after    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE outbox_dead_letter (
    id                   BIGSERIAL PRIMARY KEY,
    topic                TEXT        NOT NULL,
    headers              JSONB       NOT NULL,
    body                 BYTEA       NOT NULL,
    message_key          TEXT        NOT NULL,
    otel_context         JSONB,
    failed_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    error_message        TEXT        NOT NULL,
    original_enqueued_at TIMESTAMP WITH TIME ZONE
);

-- run_after drives the workers' claim query; without these the pollers table-scan.
CREATE INDEX idx_inbox_message_key ON inbox(message_key);
CREATE INDEX idx_inbox_enqueued_at ON inbox(enqueued_at);
CREATE INDEX idx_inbox_run_after ON inbox(run_after);
CREATE INDEX idx_outbox_run_after ON outbox(run_after);
CREATE INDEX idx_subscription_state_status ON subscription_state(status);
CREATE INDEX idx_inbox_dlq_failed_at ON inbox_dead_letter(failed_at);
CREATE INDEX idx_outbox_dlq_failed_at ON outbox_dead_letter(failed_at);
