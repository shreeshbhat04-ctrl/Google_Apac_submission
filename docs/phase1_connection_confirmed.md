# Phase 1 Connection Validation

## Purpose

This document records the baseline connection model and the checks required before any higher-level AlloyNative workflow is considered valid.

## Connection Model

Validated connection path:

- connector: Google AlloyDB `AsyncConnector`
- driver: `asyncpg`
- auth: IAM database authentication
- transport: AlloyDB connector-managed TLS

This is the preferred runtime model for AlloyNative because it avoids static database passwords and aligns with service-account-based deployment.

## Identity Requirements

### Database user

The database user must correspond to the IAM principal used by the connector.

Examples:

- personal account: use the full email address
- service account: pass the full service account email address

The principal must also exist as an AlloyDB IAM database user. IAM role binding alone is not sufficient.

Example:

```powershell
gcloud alloydb users create "SERVICE_ACCOUNT_EMAIL" `
  --cluster=mytest `
  --region=us-east4 `
  --type=IAM_BASED
```

### Required IAM role

The calling principal must have:

- `roles/alloydb.client`

## Required Database State

Before SDK-level validation, confirm:

- `alloydb.iam_authentication=on`
- `vector` extension installed
- `google_ml_integration` extension installed

## Minimal Validation Script

A minimal successful validation should prove:

1. the connector can establish a session
2. `SELECT 1` succeeds
3. required extensions are visible
4. model metadata can be queried

Representative checks:

```sql
SELECT 1;

SELECT extname
FROM pg_extension
WHERE extname IN ('vector', 'google_ml_integration')
ORDER BY extname;

SELECT setting
FROM pg_settings
WHERE name = 'alloydb.iam_authentication';

SELECT COUNT(*)
FROM google_ml.model_info_view;
```

## Confirmed Cluster Facts

The running cluster later confirmed the following:

- ML support flags were enabled
- `text-embedding-005` produced `768`-dimension vectors
- vector inserts and similarity search executed successfully
- vector search combined with SQL filters executed successfully

These results are the baseline prerequisites for the higher-level `upsert` and `query` flows documented elsewhere in the project.

## Common Failure Modes

| Error | Likely cause | Action |
|---|---|---|
| `password authentication failed` | IAM database user missing | Create the AlloyDB IAM user |
| connector timeout | network path or environment mismatch | verify Cloud Shell or VPC path |
| `extension "vector" does not exist` | extension missing | install required extensions |
| IAM auth flag not enabled | instance not configured for IAM auth | update database flags |

## Exit Criteria

Phase 1 is complete when the environment can:

- connect through the AlloyDB connector
- execute a trivial query
- confirm required extensions
- confirm basic ML integration visibility

No application-level feature should be treated as valid until these checks pass consistently.
