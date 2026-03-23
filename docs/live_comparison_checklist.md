# Live Comparison Checklist

This guide is the fastest path to proving AlloyNative on a live AlloyDB cluster and comparing it directly with Pinecone.

Use it in this order:

1. database sanity checks
2. direct AlloyDB SQL proof
3. Python SDK proof
4. REST server proof
5. Pinecone comparison summary

## 1. Database Sanity Checks

Connect to the live AlloyDB instance and run:

```sql
SELECT extversion
FROM pg_extension
WHERE extname = 'google_ml_integration';

SELECT extversion
FROM pg_extension
WHERE extname = 'vector';

SELECT name, setting
FROM pg_settings
WHERE name IN (
  'alloydb.iam_authentication',
  'google_ml_integration.enable_ai_query_engine',
  'google_ml_integration.enable_model_support'
)
ORDER BY name;

SELECT vector_dims(google_ml.embedding('text-embedding-005', 'hello world')::vector);
```

Expected:
- `google_ml_integration` present
- `vector` present
- both ML flags set to `on`
- embedding dimension `768`

## 2. Create Minimal Demo Tables

### Products

Use [products_schema.sql](c:\Users\shree\google_submission\p1\sql\products_schema.sql), then create a matching inventory table:

```sql
CREATE TABLE IF NOT EXISTS inventory (
    product_id BIGINT PRIMARY KEY,
    stock INTEGER NOT NULL,
    warehouse VARCHAR(100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Transactions

Create a minimal transaction table for the fraud story:

```sql
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    merchant_name TEXT NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    account_type TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768)
);
```

### Documents

Create a minimal healthcare table:

```sql
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT,
    department TEXT,
    created_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768)
);
```

## 3. Direct AlloyDB SQL Proof

### In-database embedding write

```sql
INSERT INTO products (name, description, price, category, metadata, embedding)
VALUES (
  'Lightweight Running Shoe',
  'Breathable daily trainer for road running',
  79.99,
  'shoes',
  '{"brand":"demo","color":"blue"}'::jsonb,
  google_ml.embedding('text-embedding-005', 'Breathable daily trainer for road running')::vector
);
```

### Join-aware retrieval

```sql
INSERT INTO inventory (product_id, stock, warehouse)
VALUES (1, 5, 'east');

SELECT p.id, p.name, p.category, p.price,
       p.embedding <=> google_ml.embedding('text-embedding-005', 'comfortable running shoes')::vector AS distance
FROM products AS p
INNER JOIN inventory AS i
  ON p.id = i.product_id
WHERE p.category = 'shoes'
  AND p.price <= 100
  AND i.stock > 0
ORDER BY distance
LIMIT 5;
```

This is the SQL-level proof that AlloyNative’s join-aware query story maps to real AlloyDB behavior.

## 4. Python SDK Proof

Use the SDK in a one-off script or REPL.

Current milestone:
- basic live `AlloyIndex` connect + upsert + query has already been proven against the live cluster
- the repo now includes fabricated live demos that create their own tables and seed data
- reranking should be treated as optional until the chosen model is confirmed through `google_ml.model_info_view`
- for the final demo narrative, focus on the expected success conditions below rather than intermediate exploratory counts

### Products / joins

Expected success condition:
- with `stock > 0`, the query returns the eligible running shoe rows
- after stock is set to `0`, those join-constrained results disappear
- the important proof is the immediate behavior change without a second vector upsert

```python
import asyncio
from alloynative import AlloyIndex


async def main():
    index = await AlloyIndex.aconnect(
        table="products",
        project_id="mystical-app-490317-v0",
        region="us-east4",
        cluster="mytest",
        instance="mytest-primary",
        database="my_application_db",
        text_columns=["name", "description"],
        embedding_source_column="description",
    )

    print(index.capabilities)

    results = await index.query(
        "comfortable running shoes",
        filters={"category": "shoes", "price__lte": 100},
        join_table="inventory",
        left_join_column="id",
        right_join_column="product_id",
        join_filter={"stock__gt": 0},
    )
    print(results)
    await index.close()


asyncio.run(main())
```

### Fraud / rerank

Expected success condition:
- preferred: rerank executes with the configured model and returns suspicious transactions at the top
- acceptable fallback: hybrid search still returns the suspicious transactions and the script clearly explains that rerank is not yet available on the chosen model

```python
import asyncio
from alloynative import AlloyIndex


async def main():
    index = await AlloyIndex.aconnect(
        table="transactions",
        project_id="mystical-app-490317-v0",
        region="us-east4",
        cluster="mytest",
        instance="mytest-primary",
        database="my_application_db",
        text_columns=["merchant_name", "description"],
        embedding_source_column="description",
    )

    results = await index.query(
        "suspicious large withdrawal unusual location",
        filters={"amount__gte": 10000, "account_type": "checking"},
        rerank=True,
        rerank_model="gemini-2.0-flash-global",
    )
    print(results)
    await index.close()


asyncio.run(main())
```

## 5. REST Server Proof

Update [service.yaml](c:\Users\shree\google_submission\p1\server\service.yaml) or your local env to point at:
- project: `mystical-app-490317-v0`
- region: `us-east4`
- cluster: `mytest`
- instance: `mytest-primary`
- database: `my_application_db`

Then run the server locally in non-dev mode and test:

1. `GET /health`
2. `POST /v1/upsert`
3. `POST /v1/search`
4. `POST /v1/actions/register`
5. `POST /v1/actions/execute`

Use the existing payloads in [demo/payload_examples](c:\Users\shree\google_submission\p1\demo\payload_examples), then add one products search payload with join fields:

```json
{
  "table": "products",
  "query": "comfortable running shoes",
  "filters": {
    "category": "shoes",
    "price__lte": 100
  },
  "join_table": "inventory",
  "left_join_column": "id",
  "right_join_column": "product_id",
  "join_filter": {
    "stock__gt": 0
  },
  "text_columns": ["name", "description"],
  "return_columns": ["name", "category", "price"],
  "metadata_column": "metadata",
  "embedding_column": "embedding",
  "limit": 5
}
```

## 6. What To Compare Against Pinecone

Use the same categories you already tested:

### A. Propagation / visibility
- update a record
- query immediately
- measure whether the new state is visible

### B. Divergence
- update SQL truth only
- skip the vector-system sync
- ask whether retrieval can still serve stale state

For AlloyDB, the architectural claim is:
- when business state and embeddings live on the same row in the same system, there is no Pinecone-style dual-write drift

### C. Join-constrained retrieval
- Pinecone baseline: requires external orchestration or pre-synced metadata tricks
- AlloyDB baseline: native SQL join in the retrieval path

This is the strongest differentiator to demonstrate live.

## 7. Evidence To Save

Capture:
- exact SQL queries
- exact SDK calls
- API responses
- screenshots
- timing notes
- one final summary table

The Pinecone side already lives in [pinecone_results_summary.md](c:\Users\shree\google_submission\p1\docs\pinecone_results_summary.md).

Add the AlloyDB side as a sibling document once you finish:
- `docs/alloydb_results_summary.md`

## 8. Recommended Order For You

1. prove extensions and flags
2. create tables
3. insert 1 or 2 rows manually with SQL
4. prove join-aware SQL
5. prove SDK `AlloyIndex`
6. prove REST API
7. compare notes against Pinecone
8. record the demo

## 9. Current Live Progress

Completed:
- live SDK connect
- capability detection
- live `products` upsert
- live `products` query
- live join-aware behavior validated during exploratory runs

Recorded in:
- [alloydb_results_summary.md](c:\Users\shree\google_submission\p1\docs\alloydb_results_summary.md)

Next:
- run [demo/cymbal_shops_demo.py](c:\Users\shree\google_submission\p1\demo\cymbal_shops_demo.py) for the fully scripted join demo
- run [demo/fraud_workflow_demo.py](c:\Users\shree\google_submission\p1\demo\fraud_workflow_demo.py) for the fabricated fraud workflow
- run REST proof
- deploy Cloud Run with the updated manifest
