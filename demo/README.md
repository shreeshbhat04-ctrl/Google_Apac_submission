# Demo Scripts

These demos use fabricated rows but run against a real AlloyDB-backed AlloyNative connection when your env vars point at a live cluster.

## Required Env

Set these before running either script:

```bash
export PYTHONPATH=py:.
export ALLOYNATIVE_PROJECT_ID=mystical-app-490317-v0
export ALLOYNATIVE_REGION=us-east4
export ALLOYNATIVE_CLUSTER=mytest
export ALLOYNATIVE_INSTANCE=mytest-primary
export ALLOYNATIVE_DATABASE=my_application_db
export ALLOYNATIVE_DB_USER=shreeshbhat04@gmail.com
export ALLOYNATIVE_IP_TYPE=PUBLIC
```

## Scripts

- [cymbal_shops_demo.py](c:\Users\shree\google_submission\p1\demo\cymbal_shops_demo.py)
  Seeds fabricated products and inventory rows, then proves positive and negative join-aware retrieval.
- [fraud_workflow_demo.py](c:\Users\shree\google_submission\p1\demo\fraud_workflow_demo.py)
  Seeds fabricated transactions and tries reranking first. If `google_ml.predict_row(...)` is not ready for the configured model, it automatically falls back to hybrid-only retrieval so the demo still completes.
- [sdk_live_smoke.py](c:\Users\shree\google_submission\p1\demo\sdk_live_smoke.py)
  Minimal live connectivity and product-search smoke test.

## Commands

```bash
python -u demo/cymbal_shops_demo.py
python -u demo/fraud_workflow_demo.py
```

Optional rerank overrides:

```bash
export ALLOYNATIVE_RERANK_MODEL=gemini-2.0-flash-global
export ALLOYNATIVE_RERANK_REQUIRED=false
```

If rerank is unavailable on your cluster, `fraud_workflow_demo.py` will print the reason and continue with hybrid-only search.
