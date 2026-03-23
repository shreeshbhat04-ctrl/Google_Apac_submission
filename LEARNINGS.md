# AlloyNative SDK - Development Learnings

> Extracted from studying `langchain-google-alloydb-pg`, GenWealth sample, and FirstBatch SDK patterns.

---

## 1. Problem Statement

**The 5-Component Manual Wiring Problem:**
A developer who wants AlloyDB for RAG today must manually wire:
1. AlloyDB connection pooling with IAM auth
2. `google_ml_integration` extension setup
3. Embedding generation via Vertex AI
4. pgvector index creation and tuning
5. Retrieval + reranking query construction

Each component has its own documentation, failure modes, and GCP IAM surface. Result: developers who could benefit from AlloyDB reach for Pinecone instead because the path is 20x shorter.

**What AlloyNative Solves:**
- **Time to first retrieval**: `pip install` + 3 method calls = working RAG
- **SQL-or-nothing trap**: Abstract away `<=>` operator, `SET LOCAL ivfflat.probes`, pgvector syntax into `embed()`, `store()`, `retrieve()`

---

## 2. Architecture Decision: SQL Generation vs API Calls

### The LangChain Approach (What NOT to do)
```
Python App → Vertex AI (generate embedding) → Python gets vector → INSERT into AlloyDB
```
The embedding is generated in Python, then stored. This works but:
- Requires separate Vertex AI client setup
- Network round-trip from Python to Vertex AI
- Embedding logic lives outside the database

### The AlloyNative Approach (Our Moat)
```
Python App → SQL with google_ml.embedding() → AlloyDB calls Vertex AI internally
```

**Critical SQL pattern from GenWealth `llm.sql`:**
```sql
-- Embeddings generated INSIDE the database:
ORDER BY analysis_embedding <=> google_ml.embedding('text-embedding-005', extractive_response)::vector

-- LLM predictions also happen in SQL:
SELECT google_ml.predict_row(model, json_build_object(
    'contents', json_build_array(
        json_build_object('role', 'user', 'parts', json_build_array(
            json_build_object('text', llm_prompt)
        ))
    ),
    'generationConfig', json_build_object(
        'temperature', 0.0,
        'topP', 0.95,
        'topK', 40,
        'maxOutputTokens', 512
    )
)) -> 'candidates' -> 0 -> 'content' -> 'parts' -> 0 ->> 'text'
```

**Why this matters:**
1. No Vertex AI client needed in Python
2. Hybrid search (WHERE clause + vector similarity) in ONE query
3. AlloyDB handles auth, connection pooling to Vertex AI
4. This is what Pinecone literally cannot do

---

## 3. Connection Patterns (from `engine.py`)

### IAM Authentication Flow
```python
from google.cloud.alloydb.connector import AsyncConnector, IPTypes, RefreshStrategy

async def connect():
    connector = AsyncConnector(
        user_agent="alloynative/0.1.0",
        refresh_strategy=RefreshStrategy.LAZY
    )

    # Auto-detect IAM principal for DB auth
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/userinfo.email"]
    )
    db_user = await _get_iam_principal_email(credentials)

    # Create connection via connector
    conn = await connector.connect(
        f"projects/{project}/locations/{region}/clusters/{cluster}/instances/{instance}",
        "asyncpg",
        user=db_user,
        db=database,
        enable_iam_auth=True,
        ip_type=IPTypes.PUBLIC,
    )
    return conn
```

### Sync-from-Async Pattern
LangChain uses a background thread event loop to support sync methods from async core:
```python
# Running a loop in background thread allows sync methods from non-async env
if cls._default_loop is None:
    cls._default_loop = asyncio.new_event_loop()
    cls._default_thread = Thread(target=cls._default_loop.run_forever, daemon=True)
    cls._default_thread.start()

# Run async coro from sync context
return asyncio.run_coroutine_threadsafe(coro, cls._default_loop).result()
```

---

## 4. SQL Patterns for In-Database ML

### Extension Setup
```sql
-- Check/create extension
DO $$
BEGIN
IF NOT EXISTS (
    SELECT 1 FROM pg_extension WHERE extname = 'google_ml_integration'
) THEN
    CREATE EXTENSION google_ml_integration VERSION '1.5.3' CASCADE;
END IF;
END $$;

-- Verify DB flag is set
SELECT setting FROM pg_settings
WHERE name = 'google_ml_integration.enable_model_support';
-- Must return 'on'
```

### Model Registration
```sql
-- Register a custom embedding model
CALL google_ml.create_model(
    model_id => 'text-embedding-005',
    model_provider => 'google',
    model_type => 'text_embedding',
    model_qualified_name => 'text-embedding-005'
);

-- List registered models
SELECT * FROM google_ml.model_info_view;
```

### Embedding Generation (In-SQL)
```sql
-- Generate embedding for a text string
SELECT google_ml.embedding('text-embedding-005', 'search query text')::vector;

-- Use in similarity search with hybrid filter
SELECT id, content,
       embedding <=> google_ml.embedding('text-embedding-005', $1)::vector AS distance
FROM documents
WHERE department = 'cardiology'
  AND created_at > '2024-01-01'
ORDER BY distance
LIMIT 10;
```

### LLM Prediction (In-SQL)
```sql
SELECT google_ml.predict_row(
    'gemini',  -- model_id
    json_build_object(
        'contents', json_build_array(
            json_build_object(
                'role', 'user',
                'parts', json_build_array(
                    json_build_object('text', 'Your prompt here')
                )
            )
        ),
        'generationConfig', json_build_object(
            'temperature', 0.0,
            'maxOutputTokens', 512
        )
    )
) -> 'candidates' -> 0 -> 'content' -> 'parts' -> 0 ->> 'text' AS response;
```

---

## 5. Index Configuration

### Available Index Types

| Index | Use Case | Extension |
|-------|----------|-----------|
| `IVFIndex` | AlloyDB-optimized, sq8 quantizer | built-in |
| `ScaNNIndex` | Google's fast ANN | `alloydb_scann` |
| `HNSWIndex` | General purpose | `pgvector` |
| `IVFFlatIndex` | Memory-efficient | `pgvector` |

### Index Creation SQL
```sql
-- IVF Index (AlloyDB native)
CREATE INDEX ON documents
USING ivf (embedding vector_cosine_ops)
WITH (lists = 100, quantizer = 'sq8');

-- ScaNN Index (requires extension)
CREATE EXTENSION IF NOT EXISTS alloydb_scann;
CREATE INDEX ON documents
USING scann (embedding cosine)
WITH (num_leaves = 5, quantizer = 'sq8');

-- Set query options at runtime
SET LOCAL ivf.probes = 10;
SET LOCAL scann.num_leaves_to_search = 1;
```

### Memory Configuration for ScaNN
```sql
-- Required before creating large ScaNN indexes
-- Formula: 50 * num_leaves * vector_size * 4 / 1024 / 1024 MB
SET maintenance_work_mem TO '256 MB';
```

---

## 6. Phase-by-Phase Build Guide

### Phase 0 - Understanding (1 day)
**Goal:** Understand exactly what SQL your SDK will generate.

**Tasks:**
- [ ] Read `engine.py`, `vectorstore.py`, `indexes.py` from langchain reference
- [ ] Run Cymbal Shops codelab end-to-end
- [ ] Document the SQL queries executed for each operation

**Output:** This LEARNINGS.md file completed.

---

### Phase 1 - Connection (2 days)
**Goal:** `AlloyDBClient.connect()` works with IAM auth.

**Files to create:**
```
alloynative/
├── py/
│   └── alloynative/
│       ├── __init__.py
│       ├── client.py      # AlloyDBClient class
│       └── auth.py        # IAM auth helpers
├── ts/                    # (empty, Phase 3)
├── demo/                  # (empty, Phase 5)
└── docs/                  # (empty, Phase 5)
```

**Target API:**
```python
from alloynative import AlloyDBClient

client = AlloyDBClient.connect(
    project_id="my-project",
    region="us-central1",
    cluster="my-cluster",
    instance="my-instance",
    database="my_database"
)

# Test raw query works
result = await client.execute("SELECT 1")
```

**Done when:** Tests pass for connect + raw query.

---

### Phase 2 - Core Methods (3-4 days)
**Goal:** Three methods that generate SQL internally.

**Method 1: `upsert_raw_text()` (The Moat)**
```python
await client.upsert_raw_text(
    table="clinical_notes",
    texts=["Patient presents with chest pain...", ...],
    metadata=[{"department": "cardiology", "date": "2024-01-15"}, ...],
    embedding_model="text-embedding-005"
)
```
**Generated SQL:**
```sql
INSERT INTO clinical_notes (content, embedding, department, date)
VALUES (
    $1,
    google_ml.embedding('text-embedding-005', $1)::vector,
    $2,
    $3
)
ON CONFLICT (id) DO UPDATE SET
    content = EXCLUDED.content,
    embedding = EXCLUDED.embedding;
```

**Method 2: `search_hybrid()` - True Hybrid (BM25 + Vector + RRF)**
```python
results = await client.search_hybrid(
    table="clinical_notes",
    query="chest pain symptoms",
    filters={"department": "cardiology", "date__gte": "2024-01-01"},
    limit=10
)
```
**Generated SQL (True Hybrid with Reciprocal Rank Fusion):**
```sql
WITH vector_search AS (
    SELECT id, content, metadata,
           ROW_NUMBER() OVER (ORDER BY
               embedding <=> google_ml.embedding('text-embedding-005', $1)::vector
           ) AS rank
    FROM clinical_notes
    WHERE department = $2 AND date >= $3
),
text_search AS (
    SELECT id, content, metadata,
           ROW_NUMBER() OVER (ORDER BY
               ts_rank(to_tsvector('english', content), plainto_tsquery($1)) DESC
           ) AS rank
    FROM clinical_notes
    WHERE department = $2 AND date >= $3
      AND to_tsvector('english', content) @@ plainto_tsquery($1)
),
rrf AS (
    SELECT COALESCE(v.id, t.id) AS id,
           COALESCE(v.content, t.content) AS content,
           COALESCE(v.metadata, t.metadata) AS metadata,
           (1.0 / (60 + COALESCE(v.rank, 1000))) +
           (1.0 / (60 + COALESCE(t.rank, 1000))) AS rrf_score
    FROM vector_search v
    FULL OUTER JOIN text_search t ON v.id = t.id
)
SELECT id, content, metadata, rrf_score AS distance
FROM rrf
ORDER BY rrf_score DESC
LIMIT $4;
```

**Why RRF (Reciprocal Rank Fusion):**
- Combines BM25 keyword ranking with vector semantic ranking
- `60` is the standard RRF constant (from research papers)
- `1000` penalty for items that only appear in one search
- This is what makes it "hybrid" — not just filtered vector search

**Method 3: `search_hybrid(..., rerank=True)`**
```python
results = await client.search_hybrid(
    table="clinical_notes",
    query="chest pain symptoms",
    filters={"department": "cardiology"},
    limit=10,
    rerank=True,
    rerank_model="gemini"
)
```
**Generated SQL (two-stage):**
```sql
-- Stage 1: Retrieve candidates
WITH candidates AS (
    SELECT id, content, metadata,
           embedding <=> google_ml.embedding('text-embedding-005', $1)::vector AS distance
    FROM clinical_notes
    WHERE department = $2
    ORDER BY distance
    LIMIT 50
)
-- Stage 2: Rerank via LLM
SELECT id, content, metadata, distance,
       google_ml.predict_row('gemini', json_build_object(...)) AS relevance_score
FROM candidates
ORDER BY relevance_score DESC
LIMIT $3;
```

**Done when:** All three methods work with generated SQL.

---

### Phase 3 - TypeScript Port (2 days)
**Goal:** Proto-generated TypeScript SDK (zero manual porting).

**Approach:** Use `protoc` with `ts-proto` plugin to generate TypeScript client from `alloynative.proto`. This ensures "one proto, two languages, zero drift".

**Files:**
```
ts/
├── src/
│   ├── index.ts           # Re-exports
│   ├── client.ts          # High-level wrapper
│   └── generated/         # Proto-generated stubs
│       ├── alloynative.ts
│       └── alloynative_grpc_pb.ts
├── proto/
│   └── alloynative.proto  # Shared with Python
├── package.json
└── tsconfig.json
```

**Dependencies:**
- `@grpc/grpc-js` - gRPC client
- `google-protobuf` - Proto runtime
- `google-auth-library` - IAM auth
- `ts-proto` - Code generation (dev)

**Target API (must match Python):**
```typescript
import { AlloyDBClient } from 'alloynative';

const client = await AlloyDBClient.connect({
    projectId: "my-project",
    region: "us-central1",
    cluster: "my-cluster",
    instance: "my-instance",
    database: "my_database"
});

const results = await client.searchHybrid({
    table: "clinical_notes",
    query: "chest pain symptoms",
    filters: { department: "cardiology" },
    limit: 10
});
```

**Done when:** npm package `alloynative` publishes successfully.

---

### Phase 4 - MCP Tools + Cloud Run Deployment (2 days)
**Goal:** SDK methods exposed as MCP tools for AI agents, deployed on Cloud Run.

**Files:**
```
server/
├── main.py              # asyncio.gather(serve_grpc, serve_rest)
├── grpc_servicer.py     # gRPC implementation
├── rest_routes.py       # FastAPI routes
├── mcp_tools.py         # MCP tool definitions
├── Dockerfile
└── service.yaml         # Cloud Run with auth proxy sidecar
```

**MCP Tool Definitions:**
```python
@mcp.tool()
async def search_documents(query: str, table: str, filters: dict) -> list:
    """Semantic search with hybrid filters."""
    return await client.search_hybrid(table=table, query=query, filters=filters)

@mcp.tool()
async def register_action(action_id: str, table: str, action_sql: str):
    """Register a SQL action an agent can trigger."""
    # For fraud demo: freeze_account action
    pass

@mcp.tool()
async def execute_action(action_id: str, params: dict):
    """Execute a registered action."""
    # UPDATE accounts SET frozen = true WHERE id = $1
    pass
```

**Deployment:**
```bash
# Build and push
gcloud builds submit --tag gcr.io/${PROJECT}/alloynative

# Deploy with sidecar
gcloud run services replace service.yaml --region=${REGION}
```

**Done when:** MCP server deploys on Cloud Run, agent can search + act.

---

### Phase 5 - Demo & Submission (1-2 days)
**Goal:** Working demo with Cymbal Shops data.

**Demo Query (What Pinecone Cannot Do):**
```python
# Hybrid filter + semantic search + action in ONE call
results = await client.search_hybrid(
    table="transactions",
    query="suspicious large withdrawal",
    filters={
        "amount__gte": 10000,
        "timestamp__gte": "2024-01-01",
        "account_type": "checking"
    },
    limit=5,
    rerank=True
)

# Agent decides to freeze account
await client.execute_action("freeze_account", {"account_id": results[0]["account_id"]})
```

**Submission README structure:**
1. **Problem:** 5-component manual wiring, SQL-or-nothing trap
2. **Solution:** AlloyNative SDK - 3 methods, SQL generation
3. **Why AlloyDB Wins:** Hybrid search impossible in Pinecone
4. **Demo Video:** 3-minute walkthrough

**Done when:** Demo video recorded, README complete, submitted.

---

## 7. Target API Surface

```python
from alloynative import AlloyDBClient

# Connect (Phase 1)
client = AlloyDBClient.connect(project, region, cluster, instance, database)

# Store with auto-embedding (Phase 2)
await client.upsert_raw_text(
    table="documents",
    texts=["...", "..."],
    metadata=[{...}, {...}],
    embedding_model="text-embedding-005"
)

# Hybrid search (Phase 2)
results = await client.search_hybrid(
    table="documents",
    query="search query",
    filters={"column": "value", "column__gte": 100},
    limit=10,
    rerank=True  # Optional
)

# Raw SQL escape hatch
await client.execute("SELECT * FROM ...")
```

**That's it.** Three methods plus connect. Everything else is SQL generation.

---

## 8. Serverless Architecture

### Single Container, Two Ports
- **FastAPI on port 8080** (REST) - for HTTP clients
- **gRPC on port 50051** - for high-performance clients
- Both servers in same Cloud Run container using `asyncio.gather()`
- Cloud Run supports HTTP/2 natively, so gRPC works without extra infrastructure

```python
# main.py entry point
async def main():
    await asyncio.gather(
        serve_grpc(port=50051),   # gRPC servicer
        serve_rest(port=8080),    # FastAPI
    )
```

### Proto File as Contract (Zero Drift Between Languages)

```proto
syntax = "proto3";
package alloynative.v1;

service AlloyNative {
  rpc Upsert(UpsertRequest) returns (UpsertResponse);
  rpc Search(SearchRequest) returns (SearchResponse);
  rpc SearchStream(SearchRequest) returns (stream SearchResult);
}

message UpsertRequest {
  string table = 1;
  repeated string texts = 2;
  repeated Metadata metadata = 3;
  string embedding_model = 4;
}

message SearchRequest {
  string table = 1;
  string query = 2;
  map<string, string> filters = 3;
  int32 limit = 4;
  bool rerank = 5;
  string rerank_model = 6;
}

message SearchResponse {
  repeated SearchResult results = 1;
}

message SearchResult {
  string id = 1;
  string content = 2;
  float score = 3;
  map<string, string> metadata = 4;
}

message UpsertResponse {
  int32 count = 1;
  repeated string ids = 2;
}

message Metadata {
  map<string, string> fields = 1;
}
```

**Key insight:** Run `protoc` once → generates Python servicer stubs AND TypeScript client stubs. TypeScript SDK is auto-generated from proto, not manually ported. Strong submission story: "one proto, two languages, zero drift".

### Auth Proxy Sidecar Pattern

Cloud Run cold starts would kill connection pools. The sidecar keeps the proxy process alive independently of your app container.

```yaml
# service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: alloynative
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cpu-throttling: "false"  # Critical: prevents IAM token refresh thread from starving
        run.googleapis.com/sessionAffinity: "true"
        autoscaling.knative.dev/minScale: "1"
    spec:
      containers:
        - name: app
          image: alloynative:latest
          ports:
            - containerPort: 8080
            - containerPort: 50051
          env:
            - name: DB_HOST
              value: "127.0.0.1"
            - name: DB_PORT
              value: "5432"
        - name: alloydb-auth-proxy
          image: gcr.io/alloydb-connectors/alloydb-auth-proxy:1.11.0
          args:
            - "--port=5432"
            - "projects/${PROJECT}/locations/${REGION}/clusters/${CLUSTER}/instances/${INSTANCE}"
```

Reconnection on cold start = fast local socket connect to `127.0.0.1:5432`.

### Data Perimeter Security Story

The `upsert_raw_text()` flow:
```
HTTP POST → FastAPI → SDK generates SQL → AlloyDB executes:
INSERT INTO products (text, embedding)
VALUES ($1, google_ml.embedding('text-embedding-005', $1))
```

**Critical insight:** Vertex AI gets called from inside the DB, not from Cloud Run container. Sensitive text never transits through application memory. This is the data perimeter story for healthcare/fintech.

---

## 9. API Design Patterns (From Weaviate SDK Reference)

### Dependency Injection Pattern
```python
# Accept external client, don't manage connections internally
class Weaviate(VectorStore):
    def __init__(self, client: WeaviateClient, **kwargs):
        self.client = client
```

### Sync + Async API Duality
```python
def search(self, query: Query, **kwargs) -> QueryResult:
    """Synchronous search."""
    pass

async def asearch(self, query: Query, **kwargs) -> QueryResult:
    """Asynchronous search."""
    pass

def multi_search(self, batch_query: BatchQuery, **kwargs) -> BatchQueryResult:
    """Batch search."""
    pass
```

### Consistent Return Types
```python
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class DistanceMetric(Enum):
    COSINE_SIM = "cosine_sim"
    EUCLIDEAN_DIST = "euclidean_dist"
    DOT_PRODUCT = "dot_product"

@dataclass
class QueryResult:
    ids: List[str]
    vectors: Optional[List[List[float]]] = None
    metadata: Optional[List[dict]] = None
    scores: Optional[List[float]] = None
    distance_metric: DistanceMetric = DistanceMetric.COSINE_SIM
```

### Batch Operations with Concurrency Control
```python
import asyncio

async def batch_upsert(data_iterator, max_concurrency=10):
    pending: set[asyncio.Task] = set()

    for ids, contents, embeddings, metadatas in data_iterator:
        pending.add(asyncio.ensure_future(
            vs.aadd_embeddings(texts=contents, embeddings=embeddings,
                              metadatas=metadatas, ids=ids)
        ))

        if len(pending) >= max_concurrency:
            _, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

    # Wait for remaining tasks
    if pending:
        await asyncio.wait(pending)
```

---

## 10. Phase Timeline Summary

| Phase | Duration | Output |
|-------|----------|--------|
| 0 | 1 day | This LEARNINGS.md complete |
| 1 | 2 days | `AlloyDBClient.connect()` works |
| 2 | 3-4 days | `upsert_raw_text()`, `search_hybrid()` work |
| 3 | 2 days | Proto-generated TypeScript SDK |
| 4 | 2 days | MCP tools + Cloud Run deployment |
| 5 | 1-2 days | Demo video + submission |

**Total: ~2 weeks**

---

## 11. Tech Stack Reference

| Component | Source | Key File |
|-----------|--------|----------|
| AlloyDB Connection | langchain-google-alloydb-pg | `engine.py` |
| FastAPI Patterns | genai-experience-concierge | `server.py`, `fastapi_app.py` |
| Cloud Run Config | langgraph-demo | `service.yaml.template` |
| Auth Proxy | integration tests | `integration.cloudbuild.yaml` |
| SDK Patterns | firstbatch-sdk | `weaviate.py`, `base.py` |
| In-DB ML | GenWealth | `llm.sql` |

---

## 12. Error Handling Taxonomy

Serverless failure modes are specific. Map each to a clear exception class.

### Exception Classes

```python
class AlloyNativeError(Exception):
    """Base exception for all AlloyNative errors."""
    pass

class AlloyNativeAuthError(AlloyNativeError):
    """IAM authentication failures."""
    pass

class AlloyNativeConnectionError(AlloyNativeError):
    """Database connection failures."""
    pass

class AlloyNativeExtensionError(AlloyNativeError):
    """Required PostgreSQL extension not available."""
    pass

class AlloyNativeIndexError(AlloyNativeError):
    """Vector index not built or misconfigured."""
    pass

class AlloyNativeModelError(AlloyNativeError):
    """ML model not registered or unavailable."""
    pass
```

### Failure Mode Mapping

| Failure Mode | Exception Class | Detection | User-Facing Message |
|--------------|-----------------|-----------|---------------------|
| IAM token expired mid-request | `AlloyNativeAuthError` | `asyncpg.InvalidAuthorizationSpecificationError` | "IAM token expired. Reconnecting..." |
| Connection limit exceeded (cold start burst) | `AlloyNativeConnectionError` | `asyncpg.TooManyConnectionsError` | "Connection pool exhausted. Retry in {n}s." |
| `google_ml_integration` not enabled | `AlloyNativeExtensionError` | Query for `pg_extension` returns empty | "Extension 'google_ml_integration' not installed. Run: CREATE EXTENSION google_ml_integration;" |
| `alloydb_scann` not enabled | `AlloyNativeExtensionError` | Query for `pg_extension` returns empty | "Extension 'alloydb_scann' not installed for ScaNN index." |
| Vector index not built (sequential scan) | `AlloyNativeIndexError` | `EXPLAIN ANALYZE` shows `Seq Scan` on large table | "No vector index found on '{table}.embedding'. Query will be slow." |
| Model not registered | `AlloyNativeModelError` | `google_ml.model_info_view` missing model_id | "Model '{model_id}' not registered. Run: CALL google_ml.create_model(...);" |
| DB flag not set | `AlloyNativeExtensionError` | `pg_settings` check returns 'off' | "Database flag 'google_ml_integration.enable_model_support' must be 'on'." |

### Detection Queries

```python
async def _check_extension(conn, extension_name: str) -> bool:
    """Check if a PostgreSQL extension is installed."""
    result = await conn.fetchval(
        "SELECT 1 FROM pg_extension WHERE extname = $1",
        extension_name
    )
    return result is not None

async def _check_db_flag(conn, flag_name: str) -> bool:
    """Check if a database flag is enabled."""
    result = await conn.fetchval(
        "SELECT setting FROM pg_settings WHERE name = $1",
        flag_name
    )
    return result == 'on'

async def _check_index_exists(conn, table: str, column: str) -> bool:
    """Check if a vector index exists on a column."""
    result = await conn.fetchval("""
        SELECT 1 FROM pg_indexes
        WHERE tablename = $1
          AND indexdef LIKE '%' || $2 || '%'
          AND (indexdef LIKE '%ivf%' OR indexdef LIKE '%hnsw%' OR indexdef LIKE '%scann%')
    """, table, column)
    return result is not None

async def _check_model_registered(conn, model_id: str) -> bool:
    """Check if an ML model is registered."""
    result = await conn.fetchval(
        "SELECT 1 FROM google_ml.model_info_view WHERE model_id = $1",
        model_id
    )
    return result is not None
```

### Startup Validation

Run these checks on `connect()` to fail fast with clear errors:

```python
async def _validate_environment(conn):
    """Validate AlloyDB environment on connection."""
    errors = []

    # Check google_ml_integration extension
    if not await _check_extension(conn, 'google_ml_integration'):
        errors.append(AlloyNativeExtensionError(
            "Extension 'google_ml_integration' not installed."
        ))

    # Check DB flag
    if not await _check_db_flag(conn, 'google_ml_integration.enable_model_support'):
        errors.append(AlloyNativeExtensionError(
            "Database flag 'google_ml_integration.enable_model_support' is not enabled."
        ))

    # Check default embedding model
    if not await _check_model_registered(conn, 'text-embedding-005'):
        errors.append(AlloyNativeModelError(
            "Default embedding model 'text-embedding-005' not registered."
        ))

    if errors:
        raise AlloyNativeError(
            f"Environment validation failed with {len(errors)} error(s):\n" +
            "\n".join(f"  - {e}" for e in errors)
        )
```

---

## References

| File | What We Learned |
|------|-----------------|
| `engine.py` | IAM auth, AsyncConnector, background thread pattern |
| `vectorstore.py` | Factory method pattern, async/sync duality |
| `indexes.py` | Index types, distance strategies, query options |
| `model_manager.py` | google_ml extension setup, model registration |
| `llm.sql` | In-SQL embedding generation, LLM prediction patterns |
