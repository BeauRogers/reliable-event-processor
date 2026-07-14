import sys
import uuid
from concurrent import futures
from pathlib import Path

import grpc
from psycopg_pool import ConnectionPool

# The generated stubs import each other as `from event.v1 import event_pb2`,
# so the gen/ directory has to be on the import path for that to resolve.
GEN_DIR = Path(__file__).resolve().parent.parent / "gen"
sys.path.insert(0, str(GEN_DIR))

from event.v1 import event_pb2  # noqa: E402
from event.v1 import event_pb2_grpc  # noqa: E402

import config  # noqa: E402

# Map between the text stored in the status column and the proto enum.
STATUS_TEXT_TO_ENUM = {
    "RECEIVED": event_pb2.EVENT_STATUS_RECEIVED,
    "PROCESSING": event_pb2.EVENT_STATUS_PROCESSING,
    "SUCCEEDED": event_pb2.EVENT_STATUS_SUCCEEDED,
    "FAILED": event_pb2.EVENT_STATUS_FAILED,
    "DEAD_LETTERED": event_pb2.EVENT_STATUS_DEAD_LETTERED,
}

# Columns selected in a fixed order so one builder can turn any row into an Event.
EVENT_COLUMNS = (
    "id, idempotency_key, type, payload, status, "
    "attempt_count, last_error, created_at, updated_at"
)


def row_to_event(row):
    """Turn a database row (in EVENT_COLUMNS order) into an Event proto."""
    (
        row_id,
        idempotency_key,
        type_,
        payload,
        status,
        attempt_count,
        last_error,
        created_at,
        updated_at,
    ) = row

    event = event_pb2.Event(
        event_id=str(row_id),
        idempotency_key=idempotency_key,
        type=type_,
        payload=bytes(payload) if payload is not None else b"",
        status=STATUS_TEXT_TO_ENUM.get(status, event_pb2.EVENT_STATUS_UNSPECIFIED),
        attempt_count=attempt_count,
        last_error=last_error or "",
    )
    # created_at and updated_at are tz-aware datetimes from TIMESTAMPTZ.
    # FromDatetime converts to UTC and fills the proto Timestamp in place.
    event.created_at.FromDatetime(created_at)
    event.updated_at.FromDatetime(updated_at)
    return event


class EventService(event_pb2_grpc.EventServiceServicer):#EventService was defined in our proto file
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def IngestEvent(self, request, context):
        # Try to insert. ON CONFLICT DO NOTHING means a row comes back only when
        # this idempotency_key is new. No row means the key already existed.
        insert_sql = f"""
            INSERT INTO events (idempotency_key, type, payload)
            VALUES (%s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING {EVENT_COLUMNS}
        """
        select_sql = f"SELECT {EVENT_COLUMNS} FROM events WHERE idempotency_key = %s"

        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    (request.idempotency_key, request.type, request.payload),
                )
                row = cur.fetchone()

                if row is not None:
                    # Brand new event.
                    return event_pb2.IngestEventResponse(
                        event=row_to_event(row),
                        duplicate=False,
                    )

                # Conflict path: the key already existed, fetch the stored event.
                cur.execute(select_sql, (request.idempotency_key,))
                existing = cur.fetchone()
                return event_pb2.IngestEventResponse(
                    event=row_to_event(existing),
                    duplicate=True,
                )

    def GetEvent(self, request, context):
        # The id column is a uuid, so reject anything that is not a valid uuid
        # before touching the database.
        try:
            uuid.UUID(request.event_id)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "event_id is not a valid UUID")

        select_sql = f"SELECT {EVENT_COLUMNS} FROM events WHERE id = %s::uuid"
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(select_sql, (request.event_id,))
                row = cur.fetchone()

        if row is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"event {request.event_id} not found")
        return row_to_event(row)


def serve():
    # A connection pool, not a single shared connection. The gRPC server runs
    # requests on a thread pool and a psycopg connection is not safe to use from
    # several threads at once, so each request checks out its own connection.
    # autocommit is fine here because every RPC is one or two independent
    # statements. The worker milestone will switch to explicit transactions.
    pool = ConnectionPool(
        conninfo=config.DATABASE_URL,
        min_size=1,
        max_size=10,#we have up to 10 threads that can run
        kwargs={"autocommit": True},
        open=True,
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    event_pb2_grpc.add_EventServiceServicer_to_server(EventService(pool), server)
    server.add_insecure_port(f"[::]:{config.GRPC_PORT}")
    server.start()
    print(f"EventService listening on :{config.GRPC_PORT}", flush=True)
    try:
        server.wait_for_termination()
    finally:
        pool.close()


if __name__ == "__main__":
    serve()
