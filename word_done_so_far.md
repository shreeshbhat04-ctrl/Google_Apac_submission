<!--
This file tracks what has already been scaffolded so the project can resume
cleanly after interruptions.

Current state:
- Phase 0 knowledge capture exists in LEARNINGS.md.
- The full project folder structure has been created.
- Phase 1 and Phase 2 Python implementation now exists in the `py/alloynative`
  package.
- Phase 3 shared contract and TypeScript client scaffolding now exists in `ts/`.
- A thin server-side gRPC transport adapter now exists in `server/grpc_servicer.py`.

Immediate next implementation order:
1. Python SDK connection layer.
2. Python SQL generation layer.
3. Python tests for connect and raw execute.
4. Shared proto contract.
5. TypeScript client generation and wrapper.
6. MCP/server runtime and deployment files.
-->

<!--
Update:
- Added docs/build_order.md to turn the phase list into a concrete execution order.
- Added docs/phase1_connection_confirmed.md to capture the real NeighborLoop and easy-alloydb connection truth.
- Added docs/ml_integration_research_notes.md to store extension and model-management research separately from confirmed facts.
- The first implementation target is now explicitly narrowed to:
  errors.py -> config.py -> auth.py -> connection.py -> validation.py -> client.py -> test_client.py
- The intent is to reach a real Phase 1 milestone before touching gRPC, proto, or TypeScript.
-->

<!--
Key confirmed Phase 1 facts:
- Target auth path is AsyncConnector + asyncpg + enable_iam_auth=True.
- The environment is private-IP only, so the SDK should default toward IPTypes.PRIVATE for this project context.
- The DB user should be passed as the full service-account email and the connector will handle service-account truncation.
- A valid Phase 1 smoke test is:
  SELECT 1
  extension presence for vector + google_ml_integration
  alloydb.iam_authentication = on
  google_ml.model_info_view reachable, even if row count is 0
-->

<!--
Open verification items now tracked separately:
- Exact google_ml_integration extension version in the running instance
-->

<!--
New confirmed facts from direct SQL output:
- google_ml_integration.enable_ai_query_engine = on
- google_ml_integration.enable_model_support = on
- google_ml.model_info_view returns Google-available built-in embedding models
- text-embedding-005 is callable in this cluster
- vector_dims(google_ml.embedding('text-embedding-005', 'hello world')::vector) = 768
- The current products table using embedding vector(768) is aligned with the live model output
- google_ml_integration extension version = 1.5.9
- vector extension version = 0.8.1.google-1
- insert with google_ml.embedding(... )::vector into products works
- plain vector search works
- filtered vector search works
- google_ml.predict_row(...) is confirmed working; the full response contains candidate text and is wrapped in a top-level array
-->

<!--
Persistence added after cluster teardown:
- docs/cluster_snapshot.md stores the validated environment state, schema, versions, and successful test queries
- sql/extensions.sql stores the extension setup SQL
- sql/products_schema.sql stores the validated products table DDL
- sql/smoke_test.sql stores the key recreation checks to run on the next cluster
-->

<!--
Implementation update:
- Implemented Python SDK config, auth, sync runner, connection manager, validation layer, SQL builders, result models, and public AlloyDBClient
- Added Python unit tests for auth helpers, validation, SQL generation, and client behavior
- Verified Python tests pass: 10 tests under `py/tests`
- Implemented shared proto contract in `ts/proto/alloynative.proto`
- Implemented TypeScript request/response types and a transport-backed AlloyDBClient wrapper
- Added TypeScript package metadata and compiler config
- Implemented `server/grpc_servicer.py` as a thin adapter from RPC-shaped payloads to AlloyDBClient calls
- Added and passed server adapter tests: 2 tests under `server/tests`
- TypeScript build/codegen was not run in this pass because the repo does not yet have installed Node dependencies
-->

<!--
General-purpose schema update:
- The SDK is no longer limited to a `content` + `metadata` style schema
- Added `upsert_rows(...)` for arbitrary row-shaped inserts with a designated embedding source column
- `search_hybrid(...)` now supports arbitrary `text_columns`, optional `metadata_column`, and explicit `return_columns`
- Search results now include a `payload` object so callers can retrieve schema-specific fields cleanly
- The proto and TypeScript types were updated to reflect row-based upserts and multi-column search
- Python tests now pass at 12 tests after the schema-generalization changes
-->

<!--
REST-first server update:
- Implemented server settings and client construction in `server/dependencies.py`
- Implemented SQL action registration and execution in `server/action_registry.py`
- Implemented FastAPI route shaping helpers and REST app creation in `server/rest_routes.py`
- Implemented MCP-friendly wrappers in `server/mcp_tools.py`
- Implemented a runnable server entrypoint in `server/main.py`
- Replaced placeholder deployment files with a real Python/uvicorn Dockerfile and Cloud Run service manifest
- Server tests now pass at 6 tests across gRPC adapter, REST helpers, and MCP wrappers
-->

<!--
Local-dev and docs update:
- Added `.env.example` for local configuration
- Added simple `.env` loading in `server/dependencies.py`
- Added `ALLOYNATIVE_DEV_MODE=true` support with an in-memory `MockAlloyDBClient`
- Added tests for server settings, mock client behavior, and REST app creation
- Added `docs/api_examples.md` and `docs/filter_behavior.md`
- Added sample JSON payloads under `demo/payload_examples/`
- Current verification status: 12 Python SDK tests passing and 10 server tests passing
-->

<!--
Repo polish update:
- Added a real top-level `README.md`
- Added `.gitignore`
- Replaced placeholder docs for architecture, Python SDK, TypeScript SDK, server, and deployment
- Added `docs/testing_with_postman.md` for local REST testing
- Replaced placeholder `server/README.md` and `ts/README.md`
-->

<!--
Submission-finish update:
- Added `CapabilitySnapshot` and runtime extension detection for pgvector and AlloyDB ScaNN
- Added `AlloyIndex` as a Pinecone-familiar wrapper over `AlloyDBClient`
- Extended hybrid search across Python, REST, gRPC adapter, proto, and TypeScript to support validated join-aware retrieval
- Updated mock/dev mode so join-constrained searches can still be demoed offline
- Updated README and architecture/docs to position REST as the primary submission/runtime path and gRPC as optional contract surface
-->

<!--
Comparative evidence update:
- Added `docs/pinecone_results_summary.md` to preserve the propagation vs divergence findings from Pinecone tests
- Linked that document into the README and architecture story as evidence for AlloyNative's one-write, one-place design advantage
-->
