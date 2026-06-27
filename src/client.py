import sys
from pathlib import Path

import grpc

GEN_DIR = Path(__file__).resolve().parent.parent / "gen"
sys.path.insert(0, str(GEN_DIR))

from event.v1 import event_pb2  # noqa: E402
from event.v1 import event_pb2_grpc  # noqa: E402

import config  # noqa: E402


def main():
    channel = grpc.insecure_channel(f"localhost:{config.GRPC_PORT}")
    stub = event_pb2_grpc.EventServiceStub(channel)

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

    assert first.duplicate is False, "first ingest should not be a duplicate"
    assert second.duplicate is True, "second ingest should be a duplicate"
    assert first.event.event_id == second.event.event_id, "ids should match"
    print("all client assertions passed")


if __name__ == "__main__":
    main()
