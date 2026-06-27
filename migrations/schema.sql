CREATE TABLE IF NOT EXISTS events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT        NOT NULL UNIQUE,
    type            TEXT        NOT NULL,
    payload         BYTEA,
    status          TEXT        NOT NULL DEFAULT 'RECEIVED',
    attempt_count   INT         NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

/*Personal notes:
We are creating a table which the main default key is the "id" of the event. We must also know the idempotency_key, type, status, 
attempt count, and created/updated_at. We will create this table of events if the events table does not already exist.
*/