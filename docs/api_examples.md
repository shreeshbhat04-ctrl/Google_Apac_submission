# AlloyNative API Examples

> Three domains - products, transactions, documents.
> Each shows the full upsert -> search -> (optional) action cycle.
> These are your reference payloads for testing, demo, and README.
>
> These are domain examples and reference payloads, not a strict wire-level contract.
> Response shapes and internal SQL are illustrative of intent.
> Exact wire behavior is tracked in the implemented server code.

---

## Domain 1 - Products

**Use case:** Hybrid product search combining category and price filters,
live inventory constraints, and semantic similarity on descriptions in one request.

### POST /v1/upsert

```json
{
  "table": "products",
  "rows": [
    {
      "id": 1,
      "name": "Lightweight Running Shoe",
      "description": "Breathable daily trainer for road running",
      "category": "shoes",
      "price": 79.99,
      "metadata": {
        "brand": "demo",
        "color": "blue"
      }
    },
    {
      "id": 2,
      "name": "Trail Running Shoe",
      "description": "Rugged grip for off-road terrain and mud",
      "category": "shoes",
      "price": 94.99,
      "metadata": {
        "brand": "demo",
        "color": "grey"
      }
    }
  ],
  "embedding_source_column": "description",
  "embedding_column": "embedding",
  "id_column": "id"
}
```

### POST /v1/search

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
  "metadata_column": "metadata",
  "return_columns": ["name", "category", "price"],
  "embedding_column": "embedding",
  "limit": 5,
  "rerank": false
}
```

**Illustrative response shape:**

```json
{
  "results": [
    {
      "name": "Lightweight Running Shoe",
      "category": "shoes",
      "price": 79.99,
      "score": 0.97
    }
  ]
}
```

---

## Domain 2 - Transactions

**Use case:** Fraud detection retrieval plus a follow-up SQL action.

### POST /v1/upsert

```json
{
  "table": "transactions",
  "rows": [
    {
      "id": "txn_001",
      "account_id": "acc_8821",
      "merchant_name": "ATM Withdrawal",
      "description": "Large cash withdrawal at 2am outside usual geography",
      "amount": 15000.0,
      "account_type": "checking",
      "timestamp": "2024-03-15T02:14:00Z",
      "metadata": {
        "country": "SG",
        "flagged": false
      }
    }
  ],
  "embedding_source_column": "description",
  "embedding_column": "embedding",
  "id_column": "id"
}
```

### POST /v1/search

```json
{
  "table": "transactions",
  "query": "suspicious large withdrawal unusual location",
  "filters": {
    "amount__gte": 10000,
    "account_type": "checking"
  },
  "text_columns": ["merchant_name", "description"],
  "return_columns": ["account_id", "amount", "timestamp", "merchant_name"],
  "embedding_column": "embedding",
  "limit": 5,
  "rerank": true
}
```

### POST /v1/actions/register

```json
{
  "action_id": "freeze_account",
  "description": "Freeze a checking account flagged for fraud",
  "sql": "UPDATE accounts SET frozen = true, frozen_at = NOW() WHERE account_id = :account_id RETURNING account_id"
}
```

### POST /v1/actions/execute

```json
{
  "action_id": "freeze_account",
  "params": {
    "account_id": "acc_8821"
  }
}
```

---

## Domain 3 - Documents

**Use case:** Clinical note retrieval inside the database perimeter.

### POST /v1/upsert

```json
{
  "table": "documents",
  "rows": [
    {
      "id": "doc_441",
      "title": "Cardiology Case - Acute Chest Pain",
      "body": "48yo male presents with sudden onset chest pain radiating to left arm, diaphoresis, and shortness of breath. ECG shows ST elevation in leads II, III, aVF.",
      "author": "Dr. Meera Nair",
      "department": "cardiology",
      "created_at": "2024-02-10",
      "metadata": {
        "icd_code": "I21.9",
        "severity": "critical"
      }
    }
  ],
  "embedding_source_column": "body",
  "embedding_column": "embedding",
  "id_column": "id"
}
```

### POST /v1/search

```json
{
  "table": "documents",
  "query": "patient chest pain symptoms ST elevation",
  "filters": {
    "department": "cardiology",
    "created_at__gte": "2024-01-01"
  },
  "text_columns": ["title", "body"],
  "metadata_column": "metadata",
  "return_columns": ["title", "author", "department", "created_at"],
  "embedding_column": "embedding",
  "limit": 10,
  "rerank": true
}
```

---

## Payload Field Reference

| Field | Required | Description |
|---|---|---|
| `table` | yes | Target AlloyDB table name |
| `rows` | yes for upsert | Array of row objects to insert or update |
| `embedding_source_column` | yes for upsert | Column whose text gets embedded |
| `embedding_column` | no, recommended | Column that stores the vector |
| `id_column` | no, recommended | Primary key column used for upsert semantics |
| `query` | yes for search | Natural language search string |
| `filters` | no | Top-level column filters using the supported v1 operators |
| `join_table` | no | Related table used to constrain eligible candidates |
| `left_join_column` | no | Column on the base table used in the join |
| `right_join_column` | no | Column on the joined table used in the join |
| `join_filter` | no | Structured filters applied to the joined table |
| `text_columns` | yes for search | Columns used to build the search text |
| `metadata_column` | no | JSONB column returned in payload but not deeply filtered in v1 |
| `return_columns` | no | Recommended columns to include in the response payload |
| `limit` | no | Max results, default 10 |
| `rerank` | no | Whether to run the LLM rerank stage |
