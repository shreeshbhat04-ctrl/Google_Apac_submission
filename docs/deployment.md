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

Before deploying, verify:
- the Artifact Registry repo path in [service.yaml](c:\Users\shree\google_submission\p1\server\service.yaml)
- that the Cloud Run service account exists and has `roles/alloydb.client`
- that the same principal exists as an AlloyDB IAM database user
- that `vector` and `google_ml_integration` are installed in `my_application_db`

Suggested deployment flow:

```bash
gcloud config set project mystical-app-490317-v0
gcloud builds submit p1/server \
  --tag us-east4-docker.pkg.dev/mystical-app-490317-v0/alloynative/alloynative:latest

gcloud run services replace p1/server/service.yaml \
  --region us-east4
```

## Rerank Note

Hybrid search is the reliable baseline. LLM reranking depends on the model IDs available in `google_ml.model_info_view` for your cluster. The manifest and demos default to `gemini-2.0-flash-global`, but the runtime can override this per request with `rerank_model`.
