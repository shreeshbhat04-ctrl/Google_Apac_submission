# Architecture

## Overview

AlloyNative provides a Pinecone-compatible developer surface backed by AlloyDB. The system keeps embeddings, metadata filters, relational joins, and optional reranking inside the database execution path rather than splitting state across a transactional store and a separate vector store.

## Core Layers

1. SDK layer
   Python and TypeScript clients expose `upsert`, `query`, and action-oriented workflows.
2. SQL generation layer
   Requests are translated into validated SQL with support for filters, joins, embeddings, and optional rerank operators.
3. Runtime layer
   The REST server and supporting adapters handle transport, configuration, and request lifecycle concerns.
4. AlloyDB execution layer
   AlloyDB executes SQL, generates embeddings through `google_ml.embedding(...)`, evaluates vector similarity, applies relational predicates, and can invoke `google_ml.predict_row(...)` when reranking is enabled.

## Request Flow

### Upsert path

1. Client submits rows and identifies the source text column for embedding generation.
2. AlloyNative validates table names, column names, and payload shape.
3. SQL is generated to write source columns and call `google_ml.embedding(...)` in the same statement.
4. AlloyDB stores relational columns and vectors in the same table.

### Query path

1. Client submits a query string, filters, and optional join constraints.
2. AlloyNative generates SQL for hybrid retrieval:
   vector similarity via `pgvector`
   full-text matching via PostgreSQL text search
   reciprocal rank fusion for a combined baseline result set
3. Optional join predicates constrain candidate eligibility using live relational data.
4. Optional reranking invokes `google_ml.predict_row(...)` if a supported model is configured.

## Design Rationale

The primary design objective is consistency. In common production deployments, operational truth lives in SQL while semantic retrieval lives in a separate vector system. That creates a propagation window in which search can return semantically relevant but operationally invalid rows. AlloyNative removes that split for supported workflows by executing the full retrieval path inside AlloyDB.

## Runtime Components

- [main.py](c:\Users\shree\google_submission\p1\server\main.py)
  FastAPI application entrypoint and process lifecycle.
- [rest_routes.py](c:\Users\shree\google_submission\p1\server\rest_routes.py)
  HTTP routes for dashboard, upsert, search, and actions.
- [dependencies.py](c:\Users\shree\google_submission\p1\server\dependencies.py)
  Environment-backed settings and client construction.
- [sql.py](c:\Users\shree\google_submission\p1\py\alloynative\sql.py)
  SQL construction logic for inserts, hybrid search, and rerank flows.
- [client.py](c:\Users\shree\google_submission\p1\py\alloynative\client.py)
  Core client implementation used by the SDK and server.

## Capability Detection

On connection, AlloyNative inspects the database environment and exposes a capability snapshot:

- `has_pgvector`
- `has_scann`
- `preferred_index_type`

This allows the runtime to adapt to the connected AlloyDB instance without assuming optional extensions are present.

## Operational Characteristics

- Single-system storage for relational and vector data
- IAM-compatible AlloyDB connector path
- Hybrid retrieval as the baseline execution model
- Join-aware eligibility control using live SQL state
- Optional rerank path that degrades cleanly when a model is unavailable
