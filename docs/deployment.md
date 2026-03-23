# Deployment

The repo includes a container and Cloud Run manifest for the REST-first server path.

## Files

- [server/Dockerfile](c:\Users\shree\google_submission\p1\server\Dockerfile)
- [server/service.yaml](c:\Users\shree\google_submission\p1\server\service.yaml)

## Local

Local development is easiest with:
- editable Python install
- FastAPI + uvicorn
- mock mode enabled in `.env`

## Cloud Run

The current manifest is a template-level starting point.

Before a real deployment you should verify:
- image registry path
- VPC config
- project, region, cluster, instance, and database env vars
- whether you want a proxy sidecar or direct connector path

## What Still Needs Live Verification

- real container boot against a running AlloyDB instance
- real Cloud Run startup and shutdown behavior
- IAM and VPC connectivity in the deployed environment
