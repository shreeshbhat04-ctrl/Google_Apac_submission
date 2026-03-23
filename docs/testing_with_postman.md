# Testing With Postman

This guide is for local offline testing with the REST server in dev mode.

## Start The Server

Create a `.env` file in the repo root with:

```env
ALLOYNATIVE_DEV_MODE=true
PORT=8080
```

Then run:

```powershell
cd C:\Users\shree\google_submission\p1
$env:PYTHONPATH = "py;."
python -m pip install -e py fastapi "uvicorn[standard]"
uvicorn server.main:app --host 0.0.0.0 --port 8080
```

## Base URL

```text
http://localhost:8080
```

## Health Check

- Method: `GET`
- URL: `/health`

Expected response:

```json
{
  "status": "ok"
}
```

## Recommended Test Order

1. `GET /health`
2. `POST /v1/upsert`
3. `POST /v1/search`
4. `POST /v1/actions/register`
5. `POST /v1/actions/execute`

## Request Setup

For all `POST` requests:
- Header: `Content-Type: application/json`
- Body mode: `raw`
- Body type: `JSON`

## Example Files

Use the payloads under [demo/payload_examples](c:\Users\shree\google_submission\p1\demo\payload_examples):

- `products_upsert.json`
- `products_search.json`
- `transactions_upsert.json`
- `transactions_search.json`
- `transactions_action_register.json`
- `transactions_action_execute.json`
- `documents_upsert.json`
- `documents_search.json`

## Important Mock-Mode Behavior

- Upserts are stored in memory only
- Restarting the server clears all mock data
- Search results are heuristic, not real AlloyDB vector scores
- You must upsert before searching if you want results

## Common Mistakes

- Sending a search payload to `/v1/upsert`
  - symptom: missing `embedding_source_column`
- Searching before upserting
  - symptom: empty `results`
- Restarting the server and expecting old test data to persist
  - symptom: previously searchable rows disappear
