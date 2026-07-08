.PHONY: gen-proto db-up db-down run test worker

gen-proto:
	python3 -m grpc_tools.protoc \
	  -I proto \
	  --python_out=gen \
	  --grpc_python_out=gen \
	  proto/event/v1/event.proto
	touch gen/event/__init__.py gen/event/v1/__init__.py

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
