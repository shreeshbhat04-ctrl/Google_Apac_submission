# Server

## Overview

The server is REST-first and uses the Python AlloyNative client as the single source of runtime behavior. Transport adapters may vary, but SQL generation and AlloyDB interaction remain centralized in the SDK layer.

## Key Files

- [main.py](c:\Users\shree\google_submission\p1\server\main.py)
  Process entrypoint and FastAPI application setup.
- [rest_routes.py](c:\Users\shree\google_submission\p1\server\rest_routes.py)
  REST routes for dashboard, search, upsert, and action execution.
- [dependencies.py](c:\Users\shree\google_submission\p1\server\dependencies.py)
  Environment-backed settings and client construction.
- [action_registry.py](c:\Users\shree\google_submission\p1\server\action_registry.py)
  Registration and execution of predefined SQL-backed actions.
- [mcp_tools.py](c:\Users\shree\google_submission\p1\server\mcp_tools.py)
  MCP-facing wrappers over the same client operations.
- [grpc_servicer.py](c:\Users\shree\google_submission\p1\server\grpc_servicer.py)
  Optional gRPC transport adapter.

## Runtime Modes

### Live mode

Used when `ALLOYNATIVE_DEV_MODE=false`.

Characteristics:

- connects to AlloyDB through the configured connector path
- uses live embeddings, hybrid search, and relational joins
- intended for validation, demos, and deployment

### Development mode

Used when `ALLOYNATIVE_DEV_MODE=true`.

Characteristics:

- runs with an in-memory mock client
- supports frontend work, route validation, and local API testing without infrastructure dependencies

## HTTP Surface

Primary routes:

- `GET /health`
- `GET /api/dashboard`
- `GET /api/run-test`
- `POST /v1/upsert`
- `POST /v1/search`
- `POST /v1/actions/register`
- `POST /v1/actions/execute`

## Lifecycle Behavior

- The application starts without forcing a database connection during process boot.
- The AlloyDB client is built lazily when a route requires it.
- Dashboard metadata can be served even when the live client is unavailable.
- The client is closed during application shutdown when present.

## Operational Intent

The server serves two roles:

1. A transport layer for SDK-backed operations.
2. A demonstration surface for live AlloyDB scenarios and validation evidence.

This keeps the implementation aligned across direct SDK use, HTTP access, and the UI demo flow.
