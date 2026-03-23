# Results Summary: Pinecone Consistency & Divergence

## The Architectural Verdict

**Pinecone's internal consistency is very fast.** In all of our propagation tests, metadata updates were visible in the very first query cycle at roughly `230ms`. The vector index is reliable and snappy.

**However, the real issue is architectural divergence.** The SQL-only tests proved that if your primary source of truth updates but the vector database update fails or is forgotten, the divergence is absolute and permanent. Pinecone has no awareness of your primary data and will serve stale data until a manual re-upsert occurs.

### Pinecone vs. AlloyDB

| Property | Pinecone | AlloyDB |
|---|---|---|
| Metadata propagation speed | Fast (`~230ms`, 1 query) | Instantaneous (same transaction) |
| SQL state awareness | Zero, requires dual-write | Native, same row |
| Divergence risk | Permanent if sync is missed | Impossible by design |
| Operational burden | Every SQL update needs Pinecone upsert | One write, one place |
| Failure recovery | Manual re-upsert | ACID rollback |

Note: In `ecommerce_run_1`, query latency spiked to `452ms` versus the `~234ms` baseline. Even with a small sample size, that shows the tail-latency variance you inherit from serverless infrastructure.

---

## Part 1: Propagation Tests

These tests measure how fast Pinecone reflects an update after it successfully receives the upsert command.

### Healthcare: Ward Flip (`ICU -> General`)

**Scenario:** Patient moved from `ICU` to `General`.
**Result:** Immediate visibility.

| Run ID | Patient ID | Stale Found | Queries to Old Absent | Queries to New Visible | Avg Latency (ms) |
|---|---|---|---|---|---|
| healthcare_run_0 | P001 | 0 | 0 | 1 | 235.72 |
| healthcare_run_1 | P001 | 0 | 0 | 1 | 232.22 |
| healthcare_run_2 | P001 | 0 | 0 | 1 | 236.85 |
| healthcare_run_3 | P001 | 0 | 0 | 1 | 232.89 |
| healthcare_run_4 | P001 | 0 | 0 | 1 | 229.89 |

### Fintech: Status Flip (`flagged -> verified`)

**Scenario:** Updating transaction status from `flagged` to `verified`.
**Result:** Immediate visibility.

| Run ID | Transaction ID | Stale Found | Queries to Old Consistent | Queries to New Consistent | Avg Latency (ms) |
|---|---|---|---|---|---|
| fintech_run_0 | candidate_0 | 0 | 1 | 1 | 224.19 |
| fintech_run_1 | candidate_0 | 0 | 1 | 1 | 228.80 |
| fintech_run_2 | candidate_0 | 0 | 1 | 1 | 229.94 |
| fintech_run_3 | candidate_0 | 0 | 1 | 1 | 229.37 |
| fintech_run_4 | candidate_0 | 0 | 1 | 1 | 226.01 |

### Ecommerce: Inventory Flip (`available -> out of stock`)

**Scenario:** Item stock state flipped from `available` to `out of stock`.
**Result:** Immediate visibility.

| Run ID | Product ID | Stale Found | Queries to Old Consistent | Queries to New Consistent | Avg Latency (ms) |
|---|---|---|---|---|---|
| ecommerce_run_0 | 1e9e8ef | 0 | 1 | 1 | 233.90 |
| ecommerce_run_1 | 1e9e8ef | 0 | 1 | 1 | 452.50 |
| ecommerce_run_2 | 1e9e8ef | 0 | 1 | 1 | 235.85 |
| ecommerce_run_3 | 1e9e8ef | 0 | 1 | 1 | 234.19 |
| ecommerce_run_4 | 1e9e8ef | 0 | 1 | 1 | 232.65 |

---

## Part 2: Divergence Tests

These tests simulate an update to the primary SQL database without a corresponding update to Pinecone.

### Fintech Divergence

**Scenario:** SQL updates transaction to `verified`. Pinecone is never told.
**Result:** Absolute divergence. Pinecone permanently serves the old `flagged` state.

| Run ID | Vector ID | Found in Flagged Every Poll | Absent from Verified Every Poll | Avg Latency (ms) |
|---|---|---|---|---|
| sql_only_run_0 | TX001 | 1 | 1 | 233.9 / 237.6 |
| sql_only_run_1 | TX001 | 1 | 1 | 235.1 / 236.2 |
| sql_only_run_2 | TX001 | 1 | 1 | 262.4 / 237.2 |
| sql_only_run_3 | TX001 | 1 | 1 | 237.2 / 235.8 |
| sql_only_run_4 | TX001 | 1 | 1 | 236.5 / 237.1 |

### Ecommerce Divergence

**Scenario:** SQL updates inventory to `out of stock`. Pinecone is never told.
**Result:** Absolute divergence. Pinecone permanently serves the old `available` state, creating oversell risk.

| Run ID | Vector ID | Found in Available Every Poll | Absent from Out of Stock Every Poll | Avg Latency (ms) |
|---|---|---|---|---|
| sql_only_run_0 | 1e9e8ef | 1 | 1 | 251.3 / 251.4 |
| sql_only_run_1 | 1e9e8ef | 1 | 1 | 250.1 / 250.2 |
| sql_only_run_2 | 1e9e8ef | 1 | 1 | 251.7 / 257.0 |
| sql_only_run_3 | 1e9e8ef | 1 | 1 | 255.5 / 255.5 |
| sql_only_run_4 | 1e9e8ef | 1 | 1 | 259.7 / 253.6 |

---

## Why This Matters for AlloyNative

This is the strongest framing for AlloyNative's architecture:

- Pinecone can be internally fast and still be structurally wrong
- the dual-write problem is the real source of risk, not propagation lag
- AlloyDB eliminates that failure mode by keeping filters, business state, and embeddings on the same row in the same transactional system
- join-aware retrieval makes the gap even clearer because live relational state can participate in the retrieval query itself
