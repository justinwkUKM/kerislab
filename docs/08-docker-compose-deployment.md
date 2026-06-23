# Docker Compose Deployment

This deployment profile runs the full KerisLab platform on one Docker host.

## Services

- `web`: production-built React app served by nginx.
- `api`: FastAPI application, migrations, OAuth/SSO, billing webhooks, reports, scans, and evidence APIs.
- `worker`: separate KerisLab worker process that consumes Redis job notifications and drains persisted scan jobs from the shared database for recovery.
- `postgres`: primary relational database for platform state.
- `redis`: scan-job notification queue for the API and worker.
- `minio`: S3-compatible evidence/object-storage service.
- `minio-init`: one-shot bucket bootstrap for evidence storage.
- `litellm`: OpenAI-compatible model gateway for future autonomous agent calls.

## Local Start

Create a local env file from the template:

```bash
cp .env.example .env
```

Edit secrets before using this outside local development:

- `KERISLAB_POSTGRES_PASSWORD`
- `KERISLAB_MINIO_ROOT_PASSWORD`
- `LITELLM_MASTER_KEY`
- `KERISLAB_BILLING_WEBHOOK_SECRET`
- OAuth/SSO client IDs and secrets

Register the OAuth/SSO callback against the web origin because nginx proxies `/api/*` to the API service:

- `http://localhost:5173/api/auth/oidc/callback` for local Compose
- `https://<your-domain>/api/auth/oidc/callback` for a deployed host

Start the stack:

```bash
make compose-up
```

Open:

- Web: `http://localhost:5173`
- API health through web proxy: `http://localhost:5173/api/health`
- API health direct port: `http://localhost:8000/api/health`
- LiteLLM: `http://localhost:4000`
- MinIO console: `http://localhost:9001`

## Persistence

Compose creates named volumes:

- `kerislab_postgres-data`
- `kerislab_redis-data`
- `kerislab_minio-data`

The API applies normalized database migrations automatically when it connects to PostgreSQL.
Evidence artifacts are written to MinIO when the object-storage variables are configured. If object storage is not configured, the API falls back to the local evidence path defined by `KERISLAB_EVIDENCE_LOCAL_PATH`.

## Operations

Validate Compose configuration:

```bash
make compose-config
```

Run deployment preflight checks without starting containers:

```bash
make compose-preflight
```

Build, start, and verify the web, API, worker heartbeat, MinIO, and LiteLLM endpoints:

```bash
make compose-smoke
```

Follow logs:

```bash
make compose-logs
```

Create a timestamped backup under `backups/`:

```bash
make compose-backup
```

Restore from a backup directory:

```bash
make compose-restore RESTORE_DIR=backups/kerislab-YYYYMMDDTHHMMSSZ
```

Stop services without deleting volumes:

```bash
make compose-down
```

## Architecture Notes

- Compose health checks cover PostgreSQL, Redis, MinIO, LiteLLM, API, web, and the specific worker heartbeat identified by `KERISLAB_WORKER_ID`.
- The web container proxies `/api/*` to the API service, so browser clients can run from the web origin without hard-coding the API port.
- `api` does not run the in-process background worker in Compose. It persists scan jobs, exposes component health, and pushes Redis notifications; `worker` publishes heartbeats, consumes Redis, and also drains persisted queued jobs for recovery.
- Browser execution uses Playwright Chromium installed in the API image and reused by the worker image.
- Evidence metadata is stored in the application database, while artifact bodies are written to MinIO through the S3-compatible object-storage configuration.
- Redis is the fast scan-job notification queue. PostgreSQL remains the durable source of truth, so queued jobs can still be recovered if Redis is unavailable or restarted.
- `compose-backup` exports PostgreSQL to `postgres.sql` and mirrors the MinIO evidence bucket into the same timestamped backup directory. `compose-restore` replays the SQL dump and mirrors evidence back into MinIO.

## Verification Notes

`make verify` checks the API tests, Python compilation, and web production build without requiring Docker. `make compose-config` validates the Compose file syntax. `make compose-smoke` is the runtime deployment check and requires a working Docker daemon.
