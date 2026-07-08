import json
import random
import sys
import uuid
from pathlib import Path

import grpc

GEN_DIR = Path(__file__).resolve().parent.parent / "gen"
sys.path.insert(0, str(GEN_DIR))

from event.v1 import event_pb2  # noqa: E402
from event.v1 import event_pb2_grpc  # noqa: E402

import config  # noqa: E402

EVENT_TYPES = [
    "payment.succeeded",
    "payment.failed",
    "order.placed",
    "order.shipped",
    "user.signed_up",
]


def main():
    channel = grpc.insecure_channel(f"localhost:{config.GRPC_PORT}")
    stub = event_pb2_grpc.EventServiceStub(channel)

    # --- Idempotency test (fixed key, always the same event) ---
    print("=== idempotency test ===")
    key = "evt_123"
    req = event_pb2.IngestEventRequest(
        idempotency_key=key,
        type="payment.succeeded",
        payload=b'{"amount": 4200}',
    )

    first = stub.IngestEvent(req)
    print(f"first ingest:  duplicate={first.duplicate} event_id={first.event.event_id}")

    second = stub.IngestEvent(req)
    print(f"second ingest: duplicate={second.duplicate} event_id={second.event.event_id}")

    fetched = stub.GetEvent(event_pb2.GetEventRequest(event_id=first.event.event_id))
    print(f"get event:     type={fetched.type} status={event_pb2.EventStatus.Name(fetched.status)}")

    # --- Random event (unique key every run, picked up fresh by the worker) ---
    print("\n=== random event ===")
    event_type = random.choice(EVENT_TYPES)
    payload = json.dumps({
        "run_id": str(uuid.uuid4()),
        "value": random.randint(100, 9999),
    }).encode()

    random_req = event_pb2.IngestEventRequest(
        idempotency_key=f"evt_{uuid.uuid4()}",
        type=event_type,
        payload=payload,
    )
    result = stub.IngestEvent(random_req)
    print(f"ingested:  event_id={result.event.event_id}")
    print(f"           type={result.event.type}")
    print(f"           payload={payload.decode()}")
    print(f"           status={event_pb2.EventStatus.Name(result.event.status)}")
    print("worker should pick this up shortly — watch the worker terminal")

    # Test the original messages
    assert first.duplicate is False, "first ingest should not be a duplicate"
    assert second.duplicate is True, "second ingest should be a duplicate"
    assert first.event.event_id == second.event.event_id, "ids should match"
    print("all idempotency assertions passed")


if __name__ == "__main__":
    main()
