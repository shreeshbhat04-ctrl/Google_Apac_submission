# Python SDK

The Python SDK is the canonical AlloyNative implementation.

## Main Entry Point

Use [py/alloynative/client.py](c:\Users\shree\google_submission\p1\py\alloynative\client.py).

Primary methods:
- `AlloyDBClient.aconnect(...)`
- `AlloyDBClient.connect(...)`
- `execute(...)`
- `upsert_rows(...)`
- `upsert_raw_text(...)`
- `search_hybrid(...)`

## Design Notes

- connection and validation are separated from SQL generation
- sync access reuses the async core through a background event loop
- SQL builders are schema-aware but identifier-safe
- the SDK is generalized beyond a single RAG table shape

## Current Verification

- unit-tested offline
- validated previously against a live AlloyDB environment at the SQL level
- still needs end-to-end runtime verification with a recreated cluster
