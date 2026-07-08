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

-- Automatically refresh updated_at on every row update.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER events_updated_at
BEFORE UPDATE ON events
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

/*Personal notes:
Here we are using a trigger procedure when a row is updated (ie. not a newly added row[insert]). In this case, we are only wanting to update the 
`updated_at` time, but this can be used for other instances. The reason we do not need this for an INSERT event is because we already are defining
default values for the newly added event, therefor this is not needed.
*/