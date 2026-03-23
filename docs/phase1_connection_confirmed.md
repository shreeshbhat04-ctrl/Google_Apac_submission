# AlloyDB Connection - Confirmed Behavior

> Based on: NeighborLoop project (`mystical-app-490317`) + easy-alloydb setup
> Status: Real cluster running - `my-alloydb-cluster` / `my-primary-inst` / `us-central1`

---

## Q1 - How are you authenticating today?

**Today (NeighborLoop):** Password auth via `pg8000` direct driver.

```text
postgresql+pg8000://postgres:YOUR_PASSWORD@PRIVATE_IP:5432/postgres
```

- Driver: `pg8000`
- User: built-in `postgres` superuser
- Auth method: plain password in DATABASE_URL env var
- Transport: direct TCP to private IP inside VPC

**For AlloyNative (the upgrade):** IAM auth via `AsyncConnector`.

```text
AsyncConnector + enable_iam_auth=True + asyncpg
```

- Driver: `asyncpg`
- User: service account email (IAM principal)
- Auth method: auto-rotating IAM tokens - zero passwords
- Transport: connector handles TLS + IAM handshake over private IP

**Why upgrade:** No password to rotate, no secret to leak in env vars,
tokens auto-refresh. This is the production-grade path Google recommends
and it is what makes the "data perimeter" security story credible for
healthcare and fintech.

---

## Q2 - Does the DB user have to be the IAM principal email exactly?

**Yes - with one critical truncation rule.**

| Principal type | What you put in `DB_USER` | Example |
|---|---|---|
| Personal Google account | Full email as-is | `you@gmail.com` |
| Service account | Drop `.gserviceaccount.com` suffix | `315569715049-compute@developer.gserviceaccount.com` -> use full email, connector truncates automatically |
| Workload identity | SA email, full | `my-sa@project.iam.gserviceaccount.com` |

> Note: When using `AsyncConnector` with `enable_iam_auth=True`,
> the connector handles the truncation for service accounts automatically.
> Pass the full SA email and do not truncate manually.

The DB user must also exist at the AlloyDB level. IAM role alone is
not enough. You must provision the database user explicitly:

```bash
gcloud alloydb users create \
  "315569715049-compute@developer.gserviceaccount.com" \
  --cluster=my-alloydb-cluster \
  --region=us-central1 \
  --type=ALLOYDB_IAM_PRINCIPAL
```

If this step is skipped, you get `password authentication failed` even
though IAM is configured. It looks like a connection error but it is a
missing DB user record.

---

## Q3 - Are you using public IP, private IP, or auth proxy?

**Your setup: Private IP only.**

From the deployment logs:

```text
Creating Subnet easy-alloydb-subnet...
NETWORK: easy-alloydb-vpc
RANGE: 10.0.0.0/24
Checking Private Services Access...
Creating Private Services Access Range...
Ensuring VPC Peering is connected...
```

And from the NeighborLoop deploy command:

```bash
gcloud beta run deploy neighbor-loop \
  --network=easy-alloydb-vpc \
  --subnet=easy-alloydb-subnet \
  --vpc-egress=all-traffic
```

This means:
- No public IP on the AlloyDB instance
- Cloud Run must be deployed into the same VPC to reach it
- Local machine cannot connect directly and must use Cloud Shell or
  a VM inside `easy-alloydb-vpc`
- `ip_type=IPTypes.PRIVATE` must be set in the connector

**For AlloyNative Cloud Run deployment**, reuse the same VPC config:

```bash
gcloud beta run deploy alloynative \
  --network=easy-alloydb-vpc \
  --subnet=easy-alloydb-subnet \
  --vpc-egress=all-traffic \
  --region=us-central1
```

---

## Q4 - Real successful flow: config shape + `SELECT 1`

### Step 1 - Prerequisites (run once in Cloud Shell)

```bash
# Enable IAM auth flag on the instance
gcloud alloydb instances update my-primary-inst \
  --cluster=my-alloydb-cluster \
  --region=us-central1 \
  --database-flags=alloydb.iam_authentication=on

# Grant AlloyDB client role to Compute SA (already done in your project)
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/alloydb.client"

# Create the IAM DB user
gcloud alloydb users create \
  "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --cluster=my-alloydb-cluster \
  --region=us-central1 \
  --type=ALLOYDB_IAM_PRINCIPAL

# Enable required extensions (use your existing postgres password here)
PRIVATE_IP="YOUR_ALLOYDB_PRIVATE_IP"
psql "postgresql://postgres:YOUR_PASSWORD@${PRIVATE_IP}:5432/postgres" \
  -c "CREATE EXTENSION IF NOT EXISTS vector CASCADE;"
psql "postgresql://postgres:YOUR_PASSWORD@${PRIVATE_IP}:5432/postgres" \
  -c "CREATE EXTENSION IF NOT EXISTS google_ml_integration VERSION '1.5.3' CASCADE;"
```

### Step 2 - Install dependencies (Cloud Shell)

```bash
pip install "google-cloud-alloydb-connector[asyncpg]" \
            sqlalchemy \
            asyncpg
```

### Step 3 - `test_connection.py`

```python
import asyncio
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from google.cloud.alloydb.connector import AsyncConnector, IPTypes

PROJECT_ID = "mystical-app-490317"
REGION = "us-central1"
CLUSTER = "my-alloydb-cluster"
INSTANCE = "my-primary-inst"
DATABASE = "postgres"

DB_USER = "315569715049-compute@developer.gserviceaccount.com"

INSTANCE_URI = (
    f"projects/{PROJECT_ID}/locations/{REGION}"
    f"/clusters/{CLUSTER}/instances/{INSTANCE}"
)


async def test_connection():
    async with AsyncConnector(refresh_strategy="lazy") as connector:

        async def getconn():
            return await connector.connect(
                INSTANCE_URI,
                "asyncpg",
                user=DB_USER,
                db=DATABASE,
                enable_iam_auth=True,
                ip_type=IPTypes.PRIVATE,
            )

        engine = create_async_engine(
            "postgresql+asyncpg://",
            async_creator=getconn,
        )

        async with engine.connect() as conn:
            result = await conn.execute(sqlalchemy.text("SELECT 1"))
            row = result.fetchone()
            print(f"[1] Basic connectivity:  SELECT 1 = {row[0]}")

            result2 = await conn.execute(sqlalchemy.text("""
                SELECT extname FROM pg_extension
                WHERE extname IN ('vector', 'google_ml_integration')
                ORDER BY extname
            """))
            exts = [r[0] for r in result2.fetchall()]
            print(f"[2] Extensions found:    {exts}")

            result3 = await conn.execute(sqlalchemy.text("""
                SELECT setting FROM pg_settings
                WHERE name = 'alloydb.iam_authentication'
            """))
            flag = result3.fetchone()
            print(f"[3] IAM auth flag:       {flag[0] if flag else 'NOT SET'}")

            result4 = await conn.execute(sqlalchemy.text("""
                SELECT COUNT(*) FROM google_ml.model_info_view
            """))
            model_count = result4.fetchone()[0]
            print(f"[4] Registered ML models: {model_count}")

        await engine.dispose()
        print("\nPhase 1 DONE - all checks passed.")


asyncio.run(test_connection())
```

### Step 4 - Run from Cloud Shell

```bash
python test_connection.py
```

### Expected output - Phase 1 confirmed

```text
[1] Basic connectivity:  SELECT 1 = 1
[2] Extensions found:    ['google_ml_integration', 'vector']
[3] IAM auth flag:       on
[4] Registered ML models: 0

Phase 1 DONE - all checks passed.
```

In this project environment, that earlier "`0` models is expected" assumption
turned out not to be universally true. Your actual cluster exposes built-in
Google-available models through `google_ml.model_info_view`.

---

## What each check confirms

| Check | What it proves |
|---|---|
| `SELECT 1 = 1` | Connector auth works, VPC routing works, DB user exists |
| Extensions found | `upsert_raw_text()` and `search_hybrid()` will have the SQL primitives they need |
| IAM auth flag on | `enable_iam_auth=True` in connector is actually enforced by the DB |
| ML models view | `google_ml_integration` is reachable and model metadata can be queried |

---

## Common failure modes and fixes

| Error | Cause | Fix |
|---|---|---|
| `password authentication failed` | IAM DB user not created | Run `gcloud alloydb users create` from Step 1 |
| `could not connect to server` | Running from local machine, not Cloud Shell | Move to Cloud Shell because the setup is private IP only |
| `extension "vector" does not exist` | Extensions not enabled | Run the `psql` extension commands in Step 1 |
| `IAM auth flag NOT SET` | DB flag not updated | Run `gcloud alloydb instances update` with `alloydb.iam_authentication=on` |
| `Token refresh failed` | Missing `refresh_strategy="lazy"` | Add `AsyncConnector(refresh_strategy="lazy")` because this is critical for serverless |
| `connection pool exhausted` | Cold start burst, too many connections | Add `pool_size=5, max_overflow=2` to `create_async_engine` |

---

## Phase 1 done signal

When `test_connection.py` prints all four checks with expected values,
Phase 1 is complete. Do not move to Phase 2 (`upsert_raw_text()`) until
this script passes clean. Every subsequent method depends on these
four things being true simultaneously.

---

## Confirmed Follow-Up Facts From The Running Cluster

The following were later confirmed directly from your instance:

```sql
SELECT name, setting
FROM pg_settings
WHERE name IN (
  'google_ml_integration.enable_ai_query_engine',
  'google_ml_integration.enable_model_support'
)
ORDER BY name;
```

Returned:

```text
google_ml_integration.enable_ai_query_engine | on
google_ml_integration.enable_model_support   | on
```

And:

```sql
SELECT vector_dims(google_ml.embedding('text-embedding-005', 'hello world')::vector);
```

Returned:

```text
768
```

This confirms:
- both ML-related flags are enabled in this cluster
- `text-embedding-005` is callable in the running environment
- `vector(768)` is the correct embedding column dimension for the current v1 schema

And the following additional checks were confirmed directly:

```sql
SELECT extversion
FROM pg_extension
WHERE extname = 'vector';
```

Returned:

```text
0.8.1.google-1
```

```sql
INSERT INTO products (name, description, price, category, metadata, embedding)
VALUES (
  'Test product',
  'A lightweight running shoe for daily training',
  79.99,
  'shoes',
  '{"brand":"demo","color":"blue"}'::jsonb,
  google_ml.embedding('text-embedding-005', 'A lightweight running shoe for daily training')::vector
)
RETURNING id, name;
```

Returned:

```text
1 | Test product
```

```sql
SELECT id, name, category, price,
       embedding <=> google_ml.embedding('text-embedding-005', 'running shoes')::vector AS distance
FROM products
ORDER BY distance
LIMIT 5;
```

Returned a successful similarity result for the inserted row with distance:

```text
0.2051991270772745
```

```sql
SELECT id, name, category, price,
       embedding <=> google_ml.embedding('text-embedding-005', 'running shoes')::vector AS distance
FROM products
WHERE category = 'shoes'
  AND price <= 100
ORDER BY distance
LIMIT 5;
```

Returned the same row successfully under filter constraints.

This confirms the current cluster supports:
- in-database embedding generation during insert
- vector similarity search over stored embeddings
- vector similarity search combined with ordinary SQL filters
