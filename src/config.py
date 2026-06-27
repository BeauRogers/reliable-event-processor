import os

# Connection string for Postgres. Override with the DATABASE_URL env var.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://events:events@localhost:5432/events",
)

# Port the gRPC server listens on. 50051 is the conventional gRPC default.
GRPC_PORT = int(os.environ.get("GRPC_PORT", "50051"))
