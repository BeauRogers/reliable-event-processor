.PHONY: gen-proto gen-descriptor db-up db-down run test worker

gen-proto:
	python3 -m grpc_tools.protoc \
	  -I proto \
	  --python_out=gen \
	  --grpc_python_out=gen \
	  proto/event/v1/event.proto
	touch gen/event/__init__.py gen/event/v1/__init__.py

# Binary descriptor set for Envoy's grpc_json_transcoder. --include_imports is
# mandatory: without it the descriptor omits Timestamp and the annotations and
# Envoy fails at startup. Build artifact, not committed; regenerate after any
# proto change and restart Envoy.
gen-descriptor:
	python3 -m grpc_tools.protoc \
	  -I proto \
	  --include_imports \
	  --include_source_info \
	  --descriptor_set_out=envoy/descriptor.pb \
	  proto/event/v1/event.proto

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

run:
	PYTHONPATH=gen:src python3 src/server.py

test:
	PYTHONPATH=gen:src python3 src/client.py

worker:
	PYTHONPATH=gen:src python3 src/worker.py
