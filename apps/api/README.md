# KerisLab API

This is the FastAPI backend for KerisLab. It provides the domain model, persistence layer, and API entrypoints for:

- Google OAuth and enterprise SSO initiation/callback endpoints with one-time OAuth state records, userinfo lookup, and id-token nonce/audience/issuer validation.
- Persisted bearer-token sessions with logout revocation.
- User profile/settings.
- Workspaces, allowed-domain SSO auto-join, memberships, and role-aware authorization for admin/security operations.
- Workspace credits and immutable ledger entries.
- Provider-neutral billing checkout, invoice, payment, and signed webhook records for credit purchases.
- Projects and scoped targets.
- Scan creation with one-credit reservation.
- Passive scan execution with evidence-backed findings.
- Autonomous scan planning, approval gates, and event logging.
- Web/UI-driven scan planning, persisted Playwright browser execution results, and durable evidence artifacts.
- Scan completion credit deduction and failure/cancellation release.
- Persistent storage with Postgres-first, SQLite fallback, and in-memory fallback.
- Scan execution queue with optional Redis notifications, durable database fallback, and background worker.

Live browser execution requires the optional Playwright extra and browser binaries:

```bash
.venv/bin/python -m pip install -e ".[browser]"
.venv/bin/python -m playwright install chromium
```

OAuth/SSO runtime configuration:

- `KERISLAB_GOOGLE_CLIENT_ID`
- `KERISLAB_GOOGLE_CLIENT_SECRET`
- `KERISLAB_GOOGLE_REDIRECT_URI`
- `KERISLAB_GOOGLE_ISSUER_URLS` optional comma-separated trusted issuers, defaults to Google issuers
- `KERISLAB_SSO_CLIENT_ID`
- `KERISLAB_SSO_CLIENT_SECRET`
- `KERISLAB_SSO_AUTHORIZE_URL`
- `KERISLAB_SSO_TOKEN_URL`
- `KERISLAB_SSO_REDIRECT_URI`
- `KERISLAB_SSO_ISSUER_URLS` optional comma-separated trusted issuers for enterprise `id_token` validation
- `KERISLAB_SSO_USERINFO_URL` when the provider does not return email claims in `id_token`

OIDC providers should redirect to `GET /api/auth/oidc/callback?code=...&state=...`. The API also supports `POST /api/auth/oidc/callback` for programmatic clients and tests.

Login and OIDC callback responses include `access_token` and `token_type: bearer`. Production clients should send `Authorization: Bearer <access_token>` on API requests. `X-KerisLab-User` remains available for development-only local flows.

Billing webhook runtime configuration:

- `KERISLAB_BILLING_WEBHOOK_SECRET`
- Webhook calls must send `X-KerisLab-Signature` as an HMAC-SHA256 over canonical JSON payload.
- Webhook event IDs are stored and processed idempotently.

Storage and worker runtime configuration:

- `KERISLAB_DATABASE_URL`: PostgreSQL connection URL. The API falls back to SQLite and then in-memory storage if persistence cannot initialize.
- `KERISLAB_REDIS_URL`: optional Redis connection used for scan-job notifications.
- `KERISLAB_REDIS_QUEUE`: Redis queue name, default `kerislab:scan-jobs`.
- `KERISLAB_OBJECT_STORAGE_ENDPOINT`: optional S3-compatible endpoint such as MinIO.
- `KERISLAB_OBJECT_STORAGE_BUCKET`: evidence bucket, default `kerislab-evidence`.
- `KERISLAB_OBJECT_STORAGE_ACCESS_KEY`
- `KERISLAB_OBJECT_STORAGE_SECRET_KEY`
- `KERISLAB_EVIDENCE_LOCAL_PATH`: local evidence fallback path, default `.kerislab/evidence`.
- `KERISLAB_WORKER_ID`, `KERISLAB_WORKER_NAME`, and `KERISLAB_WORKER_POLL_INTERVAL`: background worker identity and polling configuration.

The Docker Compose defaults are documented in the root `.env.example` and [deployment guide](../../docs/08-docker-compose-deployment.md).

The core service layer is dependency-light and covered by pytest/unittest-compatible tests. FastAPI is used for the runtime API surface.

Run locally:

```bash
make run-api
```

Verify:

```bash
make test-api
```
