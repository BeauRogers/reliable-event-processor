# One image for both Python services; compose picks the entrypoint
# (src/server.py vs src/worker.py) per service.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Generate the stubs inside the build so the image never depends on a stale
# host gen/ directory. grpcio-tools is already in requirements.txt.
COPY proto/ proto/
RUN mkdir -p gen && \
    python -m grpc_tools.protoc \
      -I proto \
      --python_out=gen \
      --grpc_python_out=gen \
      proto/event/v1/event.proto && \
    touch gen/event/__init__.py gen/event/v1/__init__.py

COPY src/ src/

ENV PYTHONPATH=/app/gen:/app/src
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/server.py"]
