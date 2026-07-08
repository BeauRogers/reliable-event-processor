import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg
from psycopg_pool import ConnectionPool

GEN_DIR = Path(__file__).resolve().parent.parent / "gen"
sys.path.insert(0, str(GEN_DIR))

import config  # noqa: E402

MAX_ATTEMPTS = 5
POLL_INTERVAL = 2  # seconds to sleep when no events are ready

# Claim one eligible event and lock the row so concurrent workers skip it.
CLAIM_SQL = """
    SELECT id, type, payload, attempt_count
    FROM events
    WHERE status IN ('RECEIVED', 'FAILED')
      AND (next_attempt_at IS NULL OR next_attempt_at <= now())
    ORDER BY created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
"""

MARK_PROCESSING_SQL = """
    UPDATE events
    SET status = 'PROCESSING',
        attempt_count = attempt_count + 1,
        updated_at = now()
    WHERE id = %s
    RETURNING attempt_count
"""

MARK_SUCCEEDED_SQL = """
    UPDATE events
    SET status = 'SUCCEEDED', updated_at = now()
    WHERE id = %s
"""

# %s order: new_status, last_error, next_attempt_at, id
MARK_FAILED_SQL = """
    UPDATE events
    SET status = %s,
        last_error = %s,
        next_attempt_at = %s,
        updated_at = now()
    WHERE id = %s
"""


def handle_event(event_id: str, event_type: str, payload: bytes) -> None:
    """Stub handler — replace with real business logic per event type."""
    print(f"[handler] processing event_id={event_id} type={event_type}", flush=True)


def process_one(pool: ConnectionPool) -> bool:
    """Claim and process one event. Returns True if an event was found."""
    event_id = None
    event_type = None
    raw_payload = None
    new_attempt_count = None

    # Transaction 1: atomically claim the event and transition to PROCESSING.
    # SKIP LOCKED means a second worker will skip this row rather than block.
    with pool.connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(CLAIM_SQL)
                row = cur.fetchone()
                if row is None:
                    raise psycopg.Rollback()  # no work; rolls back silently

                event_id, event_type, raw_payload, _ = row
                cur.execute(MARK_PROCESSING_SQL, (event_id,))
                (new_attempt_count,) = cur.fetchone()

    if event_id is None:
        return False

    print(f"[worker] claimed event_id={event_id} attempt={new_attempt_count}", flush=True)

    try:
        handle_event(str(event_id), event_type, bytes(raw_payload) if raw_payload else b"")

        # Transaction 2: mark success.
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(MARK_SUCCEEDED_SQL, (event_id,))

        print(f"[worker] succeeded event_id={event_id}", flush=True)

    except Exception as exc:
        terminal = new_attempt_count >= MAX_ATTEMPTS
        new_status = "DEAD_LETTERED" if terminal else "FAILED"
        next_attempt = (
            None
            if terminal
            else datetime.now(timezone.utc) + timedelta(seconds=2**new_attempt_count)
        )

        # Transaction 2 (failure path): record the error and schedule retry.
        with pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        MARK_FAILED_SQL,
                        (new_status, str(exc), next_attempt, event_id),
                    )

        print(
            f"[worker] {new_status} event_id={event_id} "
            f"error={exc!r} next_attempt={next_attempt}",
            flush=True,
        )

    return True


def run() -> None:
    pool = ConnectionPool(
        conninfo=config.DATABASE_URL,
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True},
        open=True,
    )

    print(f"[worker] started, polling every {POLL_INTERVAL}s for events...", flush=True)
    try:
        while True:
            found = process_one(pool)
            if not found:
                time.sleep(POLL_INTERVAL)
    finally:
        pool.close()


if __name__ == "__main__":
    run()
