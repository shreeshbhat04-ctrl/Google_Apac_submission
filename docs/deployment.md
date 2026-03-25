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

The manifest now matches the live AlloyDB environment used during validation:

- project: `mystical-app-490317-v0`
- region: `us-east4`
- cluster: `mytest`
- instance: `mytest-primary`
- database: `my_application_db`
- VPC network/subnet: `default`
- runtime service account: `alloynative-run@mystical-app-490317-v0.iam.gserviceaccount.com`
- VPC egress mode: `private-ranges-only`

Before deploying, verify:
- the Artifact Registry repo path in [service.yaml](c:\Users\shree\google_submission\p1\server\service.yaml)
- that the Cloud Run service account exists and has `roles/alloydb.client`
- that the same principal exists as an AlloyDB IAM database user
- that `vector` and `google_ml_integration` are installed in `my_application_db`
- that Cloud Run reaches AlloyDB over the configured VPC path with `ALLOYNATIVE_IP_TYPE=PRIVATE`
- that Cloud Run egress is `private-ranges-only` unless you have Cloud NAT configured for `all-traffic`
- that all required `ALLOYNATIVE_*` env vars are present because the server now fails fast when production settings are missing

Suggested deployment flow from the `p1` directory:

```bash
gcloud config set project mystical-app-490317-v0

# Make sure to run this INSIDE the `p1` folder because the Dockerfile copies `py/` and `server/`
gcloud builds submit . \
  --config server/cloudbuild.yaml

gcloud run services replace server/service.yaml \
  --region us-east4
```

Production runtime notes:
- the container now starts with `python -m server.main`, so it respects the Cloud Run `PORT` env var
- the server no longer falls back to `local-dev-*` defaults outside `ALLOYNATIVE_DEV_MODE=true`
- the manifest uses `private-ranges-only` egress so the connector can still reach Google control-plane APIs while private AlloyDB traffic stays on the VPC path
- `.dockerignore` excludes datasets, local env files, docs, and other non-runtime assets from the build context

## Rerank Note

Hybrid search is the reliable baseline. LLM reranking depends on the model IDs available in `google_ml.model_info_view` for your cluster. The manifest and demos default to `gemini-2.0-flash-global`, but the runtime can override this per request with `rerank_model`.
