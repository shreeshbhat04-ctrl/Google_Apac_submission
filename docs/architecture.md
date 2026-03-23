# Architecture

AlloyNative has four layers:

1. SDK surface
2. SQL generation layer
3. transport/runtime layer
4. AlloyDB execution layer

## End-To-End Flow

Client code calls the SDK with:
- rows to upsert
- a search query
- top-level SQL filters
- optional join constraints against a related table
- optional rerank settings

The Python SDK then:
- validates identifiers and filter operators
- generates SQL that calls `google_ml.embedding(...)` inside AlloyDB
- optionally constrains candidates with relational joins
- optionally generates SQL that calls `google_ml.predict_row(...)`

AlloyDB then becomes the place where:
- embeddings are generated
- vector similarity is computed
- ordinary SQL filters are applied
- related-table constraints are resolved with SQL joins
- reranking can happen

## Why This Matters

The key advantage is that sensitive text can stay inside the database execution path.

That changes the developer experience from:
- app -> model API -> app -> database

to:
- app -> database SQL -> model call inside AlloyDB

This is the core moat and the main product story for AlloyNative.

The strongest empirical comparison point is the Pinecone divergence result captured in [pinecone_results_summary.md](c:\Users\shree\google_submission\p1\docs\pinecone_results_summary.md): Pinecone can reflect its own updates quickly and still be structurally stale when SQL remains the true source of business state.

## Runtime Layers

- Python SDK: canonical implementation with `AlloyDBClient` and `AlloyIndex`
- TypeScript SDK: transport-facing wrapper around the same contract, including an `AlloyIndex` helper
- REST server: primary demo and runtime path
- gRPC adapter: optional shared-contract layer, not required for AlloyDB connectivity
- MCP tools: thin wrappers over the same Python SDK operations

## Capability Detection

After connecting, AlloyNative inspects installed extensions and exposes a capability snapshot:

- `has_pgvector`
- `has_scann`
- `preferred_index_type`

This keeps the runtime AlloyDB-aware without making ScaNN a hard requirement.
