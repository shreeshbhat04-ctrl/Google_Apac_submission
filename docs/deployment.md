# Deployment

## Scope

This document covers local execution and Cloud Run deployment for the REST server.

Primary deployment assets:

- [server/Dockerfile](c:\Users\shree\google_submission\p1\server\Dockerfile)
- [server/cloudbuild.yaml](c:\Users\shree\google_submission\p1\server\cloudbuild.yaml)
- [server/service.yaml](c:\Users\shree\google_submission\p1\server\service.yaml)

## Local Runtime

### Prerequisites

- Python environment with project dependencies installed
- Valid AlloyDB environment variables in [`.env`](c:\Users\shree\google_submission\p1\.env) or shell session
- `ALLOYNATIVE_DEV_MODE=false` for live AlloyDB validation

### Start the server

From the `p1` directory:

```powershell
python -m server.main
```

The server binds to `0.0.0.0`, but local access should use:

```text
http://127.0.0.1:8080/
```

## Cloud Run Configuration

The checked-in manifest is aligned to the validated AlloyDB environment:

- project: `mystical-app-490317-v0`
- region: `us-east4`
- cluster: `mytest`
- instance: `mytest-primary`
- database: `my_application_db`
- runtime service account: `alloynative-run@mystical-app-490317-v0.iam.gserviceaccount.com`
- network/subnetwork: `default`
- egress: `private-ranges-only`

## Pre-Deployment Checklist

Confirm the following before deployment:

- Artifact Registry repository exists in `us-east4`
- Cloud Run service account exists
- Cloud Run service account has `roles/alloydb.client`
- The same principal exists as an AlloyDB IAM database user
- Required extensions are installed in the target database:
  - `vector`
  - `google_ml_integration`
- `ALLOYNATIVE_*` environment variables in the manifest match the intended target
- `ALLOYNATIVE_IP_TYPE=PRIVATE` is used for the Cloud Run deployment path

## Build and Deploy

From the `p1` directory:

```powershell
gcloud config set project mystical-app-490317-v0
```

Recommended image build with a unique tag:

```powershell
$TAG = Get-Date -Format "yyyyMMdd-HHmmss"
$IMAGE = "us-east4-docker.pkg.dev/mystical-app-490317-v0/alloynative/alloynative:$TAG"

gcloud builds submit . --config server/cloudbuild.yaml --substitutions=_IMAGE=$IMAGE
gcloud run services update alloynative --region us-east4 --image $IMAGE
```

If the service does not yet exist, use:

```powershell
gcloud run services replace server/service.yaml --region us-east4
```

## Public Access

To make the service publicly reachable:

```powershell
gcloud run services add-iam-policy-binding alloynative `
  --region us-east4 `
  --member="allUsers" `
  --role="roles/run.invoker"
```

## Verification

Verify the service in this order:

1. `GET /health`
2. `GET /api/dashboard`
3. `GET /`
4. `GET /api/run-test?scenario=ecommerce`

Expected behavior:

- `/health` returns immediately
- `/api/dashboard` returns configuration metadata and scenario guide content
- `/api/run-test` exercises the live AlloyDB-backed scenario path

## Notes

- The container starts with `python -m server.main` and respects the Cloud Run `PORT` variable.
- The server no longer falls back to `local-dev-*` defaults outside `ALLOYNATIVE_DEV_MODE=true`.
- `private-ranges-only` egress is required unless outbound internet access is separately handled through Cloud NAT.
- `.dockerignore` excludes local environment files and non-runtime assets from the build context.
