# AlloyDB Validation Summary

## Scope

This document records the live AlloyDB validation work completed for AlloyNative and the current status of the demonstration environment.

Validated environment:

- project: `mystical-app-490317-v0`
- region: `us-east4`
- cluster: `mytest`
- instance: `mytest-primary`
- database: `my_application_db`
- primary interactive user: `shreeshbhat04@gmail.com`

## Completed Validation

### 1. SDK connectivity

Verified through the Python SDK:

- AlloyDB connector authentication succeeded
- capability detection returned a valid snapshot
- embeddings were generated in-database
- a seeded product row was retrieved through `AlloyIndex.query(...)`

Representative output:

```text
Capabilities: CapabilitySnapshot(has_pgvector=True, has_scann=False, preferred_index_type='ivfflat')
Result count: 1
SearchResult(
  id='1',
  content='Lightweight Running Shoe Breathable daily trainer for road running',
  metadata={'brand': 'demo', 'color': 'blue'},
  score=0.017336838849365915,
  payload={'brand': 'demo', 'color': 'blue'},
  distance=0.2732395967968395
)
```

### 2. Join-aware retrieval

Verified against live AlloyDB tables with an inventory join.

Observed behavior:

- results were present when the join predicate matched current inventory state
- results were removed when the same item became ineligible under the join predicate

This confirms that result eligibility can be controlled by live relational state without re-upserting vector metadata.

### 3. Fabricated live demos

The project includes live-seeded demo workflows for screenshot and walkthrough purposes:

- [cymbal_shops_demo.py](c:\Users\shree\google_submission\p1\demo\cymbal_shops_demo.py)
- [fraud_workflow_demo.py](c:\Users\shree\google_submission\p1\demo\fraud_workflow_demo.py)

These scripts create required tables if needed, seed deterministic demo rows, and exercise the same AlloyDB-backed query path used by the SDK and server.

## Rerank Status

Hybrid retrieval is the production baseline.

Reranking remains environment-dependent because `google_ml.predict_row(...)` requires a supported model configuration in the connected cluster. The current demos handle this by:

- attempting rerank when configured
- falling back to hybrid-only search when rerank is unavailable

This keeps the demo path stable without misrepresenting model availability.

## Implementation Changes Confirmed During Validation

The following runtime issues were identified and corrected during live testing:

- `ip_type` normalization for string environment values
- JSONB serialization in `upsert_rows(...)`
- local/demo environment cleanup for reliable live mode activation
- REST dashboard behavior changed so the guide can load even if the live client is temporarily unavailable

## Current Status

- Offline SDK tests: complete
- Offline server tests: complete
- Live AlloyDB SDK connect/upsert/search: complete
- Live join-aware retrieval: complete
- Local REST dashboard backed by real environment values: complete
- Cloud Run runtime connection path: still under validation

## Recommended Next Steps

1. Finalize Cloud Run connectivity for the runtime service account.
2. Capture screenshot-ready evidence from the local dashboard using live scenario runs.
3. Complete the Pinecone comparison write-up using the same scenario set and outcome format.
