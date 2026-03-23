# AlloyNative

AlloyNative is a generalized AlloyDB SDK and server runtime that makes AlloyDB feel closer to a modern vector platform while keeping data, filters, and model execution inside the database boundary.

The friendly surface is `AlloyIndex`; the lower-level power surface is `AlloyDBClient`.

Core capabilities:
- in-database embedding generation with `google_ml.embedding(...)`
- hybrid retrieval with SQL filters plus vector similarity
- optional join-constrained retrieval across related tables
- optional in-database reranking with `google_ml.predict_row(...)`
- runtime capability detection for pgvector and AlloyDB ScaNN
- Python, TypeScript, REST, and MCP-style integration points

## What Exists Today

- Python SDK in [py/alloynative](c:\Users\shree\google_submission\p1\py\alloynative)
- Shared proto contract in [ts/proto/alloynative.proto](c:\Users\shree\google_submission\p1\ts\proto\alloynative.proto)
- TypeScript client surface in [ts/src](c:\Users\shree\google_submission\p1\ts\src)
- REST-first server in [server](c:\Users\shree\google_submission\p1\server)
- Offline mock/dev mode for local demos without a live AlloyDB cluster

## Core Idea

Instead of generating embeddings in application code and then shipping vectors to a database,
AlloyNative pushes the model call into AlloyDB itself. That gives one SQL execution path for:
- ordinary filters
- vector similarity
- full-text search
- relational joins that constrain eligible rows
- optional LLM reranking

That is the main product moat and the reason this project is positioned differently from
standalone vector databases.

## Current Status

The SDK and server are built and locally testable.

What is verified offline:
- Python SDK tests
- server tests
- TypeScript build
- proto generation
- REST endpoint flows in mock mode

What is now verified live:
- AlloyDB connection through the Python SDK
- capability detection for pgvector / ScaNN availability
- live product upsert with in-database embedding generation
- live product retrieval through `AlloyIndex`
- live join-constrained behavior through the AlloyNative query path

What still needs a live AlloyDB cluster:
- optional rerank validation for the chosen `google_ml.predict_row(...)` model
- Cloud Run deployment verification

## REST-First Submission Scope

AlloyNative is submission-scoped as a REST-first product.

- AlloyDB connectivity uses the AlloyDB connector and the PostgreSQL protocol
- REST is the primary runtime and demo path
- gRPC remains optional as a shared contract and adapter layer, not a required transport for AlloyDB itself

## What AlloyNative Actually Simplifies

AlloyNative does not replace infrastructure provisioning. You still need to:
- create the AlloyDB cluster and instance
- configure networking and IAM
- enable extensions and required database flags
- deploy the server runtime

What AlloyNative simplifies is everything after the database exists:

- no hand-written `google_ml.embedding(...)` insert SQL for every table
- no hand-written BM25 + vector + RRF query construction
- no hand-written `google_ml.predict_row(...)` rerank SQL
- no custom request-shaping glue across Python, TypeScript, REST, and MCP-style tool wrappers
- no separate app-side orchestration for join-constrained retrieval patterns

That turns AlloyDB from "powerful but SQL-heavy" into "usable as an application-facing retrieval platform".

The practical developer experience becomes:

```python
index = await AlloyIndex.aconnect(...)
await index.upsert(rows)
results = await index.query(
    "running shoes",
    filters={"category": "shoes"},
    join_table="inventory",
    left_join_column="id",
    right_join_column="product_id",
    join_filter={"stock__gt": 0},
    rerank=True,
)
```

instead of repeatedly hand-authoring vector SQL, filter SQL, rerank SQL, and API translation code.

## Friendly Index Surface

```python
from alloynative import AlloyIndex

index = await AlloyIndex.aconnect(
    table="products",
    project_id="my-project",
    region="us-central1",
    cluster="my-cluster",
    instance="my-instance",
    database="my_database",
    text_columns=["name", "description"],
    embedding_source_column="description",
)

await index.upsert(
    [{"id": 1, "name": "Running Shoe", "description": "Daily trainer"}]
)

results = await index.query(
    "running shoes",
    filters={"category": "shoes"},
    join_table="inventory",
    left_join_column="id",
    right_join_column="product_id",
    join_filter={"stock__gt": 0},
)
```

## Local Dev Mode

You can run the server without AlloyDB by setting:

```env
ALLOYNATIVE_DEV_MODE=true
PORT=8080
```

Then start the server:

```powershell
cd C:\Users\shree\google_submission\p1
$env:PYTHONPATH = "py;."
python -m pip install -e py fastapi "uvicorn[standard]"
uvicorn server.main:app --host 0.0.0.0 --port 8080
```

In mock mode:
- upserts are stored in memory
- search uses a lightweight heuristic scorer
- join-aware search works against in-memory related tables
- action endpoints still work for request-flow testing

For live demos with fabricated data, see [demo/README.md](c:\Users\shree\google_submission\p1\demo\README.md). The fraud demo will fall back to hybrid-only search if rerank is not ready on the cluster.

## Suggested Reading Order

1. [LEARNINGS.md](c:\Users\shree\google_submission\p1\LEARNINGS.md)
2. [docs/cluster_snapshot.md](c:\Users\shree\google_submission\p1\docs\cluster_snapshot.md)
3. [docs/pinecone_results_summary.md](c:\Users\shree\google_submission\p1\docs\pinecone_results_summary.md)
4. [docs/alloydb_results_summary.md](c:\Users\shree\google_submission\p1\docs\alloydb_results_summary.md)
5. [docs/api_examples.md](c:\Users\shree\google_submission\p1\docs\api_examples.md)
6. [docs/filter_behavior.md](c:\Users\shree\google_submission\p1\docs\filter_behavior.md)
7. [docs/live_comparison_checklist.md](c:\Users\shree\google_submission\p1\docs\live_comparison_checklist.md)
8. [docs/testing_with_postman.md](c:\Users\shree\google_submission\p1\docs\testing_with_postman.md)

## Quick API Flow

1. `POST /v1/upsert`
2. `POST /v1/search`
3. optional `POST /v1/actions/register`
4. optional `POST /v1/actions/execute`

Example payloads live in [demo/payload_examples](c:\Users\shree\google_submission\p1\demo\payload_examples).
