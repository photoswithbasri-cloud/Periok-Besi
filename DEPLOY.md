# Deploying to Google Cloud Run

**Status: not yet deployed, and not deployable yet.** Credentials and a GCP
project ID for this hackathon are issued via the organizers' portal on
**Day 1 (18 Sep)** — they don't exist before then. Nothing in this file has
been run against real GCP; it's scaffolding to follow once those
credentials exist.

## Prerequisites (once you have Day-1 credentials)

1. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install).
2. Authenticate:
   ```bash
   gcloud auth login
   ```
3. Set your project (project ID comes from the hackathon's GCP portal):
   ```bash
   gcloud config set project <YOUR_PROJECT_ID>
   ```
4. Enable the required APIs (one-time per project):
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
   ```

## Deploy

Run from the repository root (same directory as this file and the
`Dockerfile`):

```bash
gcloud run deploy rail-fleet-health-monitor \
  --source . \
  --project <YOUR_PROJECT_ID> \
  --region <YOUR_REGION> \
  --platform managed \
  --allow-unauthenticated
```

- `--source .` — Cloud Run builds the image from this repo's `Dockerfile`
  via Cloud Build; no local Docker install or manual registry push needed
  for this path (though building/testing locally first, below, is still a
  good idea).
- `<YOUR_PROJECT_ID>` — from the hackathon's Google Cloud portal, Day 1.
- `<YOUR_REGION>` — e.g. `asia-southeast1` (Singapore); use whatever the
  organizers recommend or whatever your project is set up for.
- `--allow-unauthenticated` makes the demo URL publicly reachable without a
  Google sign-in prompt — convenient for a hackathon demo; drop it if judges
  require authenticated access instead.
- Cloud Run always sets the `PORT` env var itself and expects the container
  to bind `0.0.0.0:$PORT` — already handled by this repo's `Dockerfile` and
  `backend/app.py`, nothing to change here.

## Local verification before deploying

```bash
docker build -t rail-fleet-health-monitor .
docker run -p 8080:8080 rail-fleet-health-monitor
# then open http://localhost:8080
```
