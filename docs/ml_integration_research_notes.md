# AlloyDB ML Integration - Research Notes To Verify

> Source: user-provided setup notes and guidance text
> Status: useful direction, but not yet treated as direct instance output

This file captures working guidance and open questions around
`google_ml_integration` so implementation can distinguish between:
- confirmed behavior from your running environment
- likely behavior that still needs a direct SQL check

---

## What Seems Solid

### Enabling `google_ml_integration` is a database operation plus instance configuration

The extension is enabled inside PostgreSQL with SQL, not with a
`gcloud components install` command.

The expected database command is:

```sql
CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;
```

And `vector` is also enabled inside the database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Instance-level support must be enabled separately

The AlloyDB instance itself must be configured to support ML integration
through database flags and IAM permissions.

Example create/update guidance captured from the notes:

```bash
gcloud alloydb instances create INSTANCE_NAME \
  --database-version=POSTGRES_15 \
  --tier=MACHINE_TYPE \
  --region=REGION_NAME \
  --cluster=CLUSTER_NAME \
  --database-flags=google_ml_integration.enable_ai_query_engine=on
```

```bash
gcloud alloydb instances update INSTANCE_NAME \
  --database-flags=google_ml_integration.enable_ai_query_engine=on \
  --region=REGION_NAME \
  --cluster=CLUSTER_NAME
```

### Direct verification queries we should run against the real instance

```sql
SELECT extversion
FROM pg_extension
WHERE extname = 'google_ml_integration';
```

```sql
SELECT *
FROM google_ml.model_info_view;
```

---

## Claims That Need Direct Verification In Your Instance

These points originally needed verification. Some are now resolved from
your direct instance output.

### 1. Which flag name is the real one for your instance?

Resolved. Your instance reports both:
- `google_ml_integration.enable_ai_query_engine = on`
- `google_ml_integration.enable_model_support = on`

Implementation note:
- `validation.py` should check both when possible for this project context.

### 2. Is `text-embedding-005` already available without explicit registration?

Resolved strongly enough for v1. Your instance:
- exposes `text-embedding-005` in `google_ml.model_info_view`
- returns `vector_dims(...) = 768` for
  `google_ml.embedding('text-embedding-005', 'hello world')::vector`

Implementation note:
- for this environment, `text-embedding-005` can be treated as available by default
- we should still keep validation defensive in case another cluster differs

### 3. Does `google_ml.model_info_view` work before any custom model registration?

Resolved. The view works in your instance and returns Google-available models.

### 4. Which minimum extension version should AlloyNative enforce?

The notes mention:
- `1.5.2+` for multimodal embeddings
- `1.4.2+` for general use

Your earlier Phase 1 notes used `1.5.3`.

We should not hardcode a minimum until we know which exact SDK features
we want in v1 and what your instance actually runs.

---

## Remaining Things We Still Need Back From The Real Database

Please still bring back the exact outputs for these if available:

```sql
SELECT extversion
FROM pg_extension
WHERE extname = 'google_ml_integration';
```

```sql
SELECT setting
FROM pg_settings
WHERE name IN (
  'google_ml_integration.enable_ai_query_engine',
  'google_ml_integration.enable_model_support'
)
ORDER BY name;
```

The latter two have effectively been answered already, but keeping them here
preserves the verification checklist.

---

## Implementation Impact

These answers affect:
- `py/alloynative/validation.py`
- `py/alloynative/client.py`
- Phase 2 model registration behavior
- user-facing setup instructions

Updated stance:
- the SDK can now safely assume `vector(768)` for the current v1 `products` table
- the SDK can likely default to `text-embedding-005` for this project
- extension version is still worth checking before we hardcode strict minimums

Direct follow-up verification has now also shown:
- `google_ml_integration` extension version is `1.5.9`
- `vector` extension version is `0.8.1.google-1`
- `google_ml.embedding(...)::vector` can be inserted directly into the `products.embedding` column
- similarity search using `<=>` works against stored embeddings
- similarity search plus ordinary SQL filters works on the same query

There is now a direct `google_ml.predict_row(...)` confirmation:

```sql
SELECT google_ml.predict_row(
  'gemini_flash_model',
  json_build_object(
    'contents', json_build_array(
      json_build_object(
        'role', 'user',
        'parts', json_build_array(
          json_build_object('text', 'Reply with only the word OK')
        )
      )
    )
  )
)->'candidates'->0->'content'->'parts'->0->'text';
```

Observed result:
- query executed successfully
- the full JSON response included a candidate with text `"OK"`
- the response shape is wrapped in an array at the top level

Representative response shape:

```json
[
  {
    "candidates": [
      {
        "content": {
          "role": "model",
          "parts": [
            {
              "text": "OK"
            }
          ]
        },
        "finishReason": "STOP"
      }
    ],
    "usageMetadata": {
      "promptTokenCount": 6,
      "candidatesTokenCount": 1,
      "totalTokenCount": 22
    }
  }
]
```

Implementation note:
- `predict_row` support is confirmed in this environment
- earlier empty extraction likely came from using the wrong JSON path against
  the array-wrapped response
- rerank support can now be treated as a real Phase 2 target rather than a speculative one
