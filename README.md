# What is this project #
This project is a demo project for learning purposes. This project demonstrates ingesting JSON messages of payment statuses over HTTP, processing them as gRPC message into a postgres database and then processing those messages for validity, duplication and dead-lettering.


# Architecture #
This project is composed of four services

## PostGres ##
This is the database that contains the information of the events. The information that is stored in the database is:
1. event_id - unique ID of the event
2. idempotency_key - key given to us by the client to identify the event and look for duplicates
3. type - type of event
4. payload - event data
5. status - event's processing status
6. attempt_count - number of attempt to process the event
7. last_error - reason for last error
8. created_at - date-time stamp event was created
9. updated_at - date-time stamp event was updated

## Server ##
Python implemented server that waits for events to process them. This will receive the events written in gRPC from the client/Envoy and filter out invalid events and/or duplicate events

## Envoy ##
This will recieve JSON/HTTP requests from the client and translate them into gRPC message and forwarded to the server

## Worker(s) ##
The worker thread(s) will process the events that are in the Postgres database and mark them as SUCCEEDED, FAILED or DEAD-LETTERED

## Diagram ##

curl --> Envoy:8080 --> gRPC Server:50051 --> Postgres:5432 --> Worker(s)


# API #
This project will recieve curl requests  in the following structure.

`curl -X POST localhost:8080/v1/events -H 'Content-Type: application/json' -d '{"idempotency_key":"{KeyValue}","type":"{paymentType}","payload":""}'`
`curl localhost:8080/v1/events/{event_id}`

The `idempotency_key` will be the identification of the transaction that is sent such that the server can parse potential duplicate payments.


# Getting Started #

Prerequisites

Docker and Docker Compose
Python 3.12+
`grpcio-tools` (pip install grpcio-tools googleapis-common-protos)
Running the full stack

1. Generate the Python stubs from the proto:
`make gen-proto`

2. Generate the Envoy descriptor:
`make gen-descriptor`

3. Start all services:
`docker compose up --build`


The stack is ready when you see:
`EventService listening on :50051`

Running locally (server and worker on host, Postgres in Docker)
`make db-up`      # start Postgres
`make run`        # gRPC server (terminal 1)
`make worker`     # background worker (terminal 2)

Stopping
`docker compose down`


# How to test it #

Testing via JSON/HTTP (Envoy path)

Ingest an event:
`curl -X POST localhost:8080/v1/events \`
`  -H 'Content-Type: application/json' \`
`  -d '{"idempotency_key":"my-key-1","type":"payment.succeeded","payload":""}'`

Test idempotency by running the exact same command again -- the response should come back with "duplicate": true and the same event_id:
`curl -X POST localhost:8080/v1/events \`
`  -H 'Content-Type: application/json' \`
`  -d '{"idempotency_key":"my-key-1","type":"payment.succeeded","payload":""}'`

Fetch the event by ID (use the event_id returned above):
`curl localhost:8080/v1/events/<event_id>`


Test a 404 with an ID that doesn't exist:
`curl -o /dev/null -w '%{http_code}\n' localhost:8080/v1/events/00000000-0000-0000-0000-000000000000`

Testing via native gRPC
`make test`

This runs `src/client.py` directly against port 50051, bypassing Envoy entirely.

Verifying the worker processed an event
Watch the worker logs:
`docker compose logs -f worker`

Within a few seconds of ingesting an event you should see it claimed and marked succeeded. You can also confirm in Postgres:
`docker exec <postgres_container> psql -U events -d events -c "SELECT id, status FROM events"`

# Project Structure #

Envoy yaml file indicating how the client messages need to be translated and to which server the result needs to be forwarded to
-enoy
    - envoy.yaml

Schema of the Postgres database, indicating data strucutre as well as TRIGGER functions for updating the `updated_at` field when the row is updated
-migrations
    - schema.sql

proto file that defines what our eventServer looks like as well as defines how the gRPC events are structred
-proto
    - event/v1/event.proto
Google-published protofiles
-proto
    - google/api
        - annotations.proto
        - http.proto

python scripts running the worker(s), server and test-client
-src
    - client.py
    - config.py
    - server.py
    - worker.py

Docker files, make file and requirement file.
- docker-compose
- Dockerfile
- Makefile
- requirements.txt

# Next steps #
- Currently, the business logic for processing the specific payload of the transactions if left blank, with the logic of the project focusing on the infrastructure to handle payments being services through Postgres, Envoy and server logic. Next steps would be to fill in this business logic.
- Add more unit test coverage for all the server functions