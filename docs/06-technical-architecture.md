# KerisLab Technical Architecture

## 1. System Overview

KerisLab starts as a Docker Compose deployment and scales into separated services. The core architecture is API, web app, Google/SSO identity, workspace credits, worker pool, Redis queue, PostgreSQL, object storage, and LiteLLM.

```text
React Web UI
  -> FastAPI API Server
  -> PostgreSQL
  -> Redis Queue
  -> Worker Pool
  -> Autonomous Orchestrator
  -> Tool Gateway
  -> Playwright / HTTP / Scanner / Code Tools
  -> Evidence Store
  -> LiteLLM Gateway
```

## 2. Services

Web:

- React, TypeScript, Vite.
- Plain React state with a typed API client for the current web app.
- Local session restore with `localStorage` for active user/workspace/scan context.
- Polling for runtime health, credits, scan events, approvals, findings, and evidence.
- Apple-inspired design system implemented as CSS variables and reusable components.
- Command search, findings filtering, evidence actions, and report download affordances.

API:

- FastAPI.
- Google OAuth, enterprise SSO, one-time OAuth state records, userinfo/id-token profile resolution, id-token nonce/audience/issuer validation, allowed-domain workspace auto-join, sessions, profile/settings, workspace membership, credits, projects, targets, scans, findings, reports, settings, audit logs.
- Creates scan jobs and reads persisted scan state.
- Persists scan events and exposes them through polling endpoints. WebSocket/SSE event streaming is an upcoming scale feature.

Worker:

- Redis-backed queue worker.
- Runs scan phases and autonomous orchestration.
- Owns tool execution through the Tool Gateway.
- Writes events, findings, tool runs, LLM calls, and evidence references.

LiteLLM:

- Runs as separate service.
- Stores or references provider credentials.
- Exposes OpenAI-compatible model endpoint to KerisLab.

PostgreSQL:

- System of record for projects, scans, findings, events, policies, approvals, and audit.
- Preferred production database when `KERISLAB_DATABASE_URL` is configured.
- Normalized schema migrations are applied during API store initialization and can also be run explicitly with `make migrate`.
- If the configured PostgreSQL connection cannot be opened, the API falls back to SQLite so local startup is not blocked by database availability.

SQLite:

- Local fallback database for single-node development and offline runs.
- Stores the same serialized platform state as PostgreSQL when no Postgres URL is available or the Postgres connection fails.
- Normalized schema migrations are applied before the SQLite-backed store opens.
- If SQLite cannot be initialized, the API falls back to in-memory storage for emergency development and test runs.

Object Storage:

- Local filesystem fallback for development.
- S3-compatible storage for deployment, including MinIO in Docker Compose.
- Stores screenshots, transcripts, logs, source snippets, report files, and scanner artifacts.

## 3. Core Data Entities

- `projects`
- `users`
- `user_profiles`
- `user_settings`
- `user_sessions`
- `oauth_states`
- `auth_identities`
- `workspaces`
- `workspace_memberships`
- `sso_configurations`
- `workspace_credit_accounts`
- `credit_ledger_entries`
- `scan_credit_reservations`
- `billing_customers`
- `billing_checkout_sessions`
- `billing_invoices`
- `billing_payments`
- `billing_webhook_events`
- `targets`
- `target_scope_rules`
- `scan_policies`
- `scans`
- `scan_phases`
- `scan_events`
- `agent_plans`
- `browser_plans`
- `browser_executions`
- `evidence_artifacts`
- `agent_memory`
- `approval_requests`
- `tool_runs`
- `llm_calls`
- `browser_sessions`
- `findings`
- `reports`
- `audit_logs`

## 4. API Surface

Auth and profile:

- `GET /api/auth/providers`
- `GET /api/auth/google/login`
- `GET /api/auth/sso/login`
- `GET /api/auth/oidc/callback`
- `POST /api/auth/oidc/callback`
- `POST /api/auth/dev-login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `PATCH /api/users/me`

Workspaces:

- `POST /api/workspaces`
- `GET /api/workspaces`
- `GET /api/workspaces/{workspace_id}`
- `PATCH /api/workspaces/{workspace_id}/sso`
- `GET /api/workspaces/{workspace_id}/credits`
- `POST /api/workspaces/{workspace_id}/credits/grant`
- `GET /api/workspaces/{workspace_id}/credit-ledger`
- `POST /api/workspaces/{workspace_id}/billing/checkout-sessions`
- `POST /api/billing/checkout-sessions/{checkout_session_id}/confirm`
- `POST /api/billing/webhooks`

Projects and targets:

- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_id}/targets`
- `POST /api/targets`

Scans:

- `POST /api/scans`
- `GET /api/scans/{scan_id}`
- `GET /api/scans/{scan_id}/events`
- `GET /api/execution/jobs`
- `GET /api/audit-logs`
- `POST /api/execution/drain`
- `POST /api/scans/{scan_id}/run-passive`
- `POST /api/scans/{scan_id}/pause`
- `POST /api/scans/{scan_id}/resume`
- `POST /api/scans/{scan_id}/cancel`
- `POST /api/scans/{scan_id}/instructions`
- `POST /api/scans/{scan_id}/complete`
- `POST /api/scans/{scan_id}/fail`
- `POST /api/scans/{scan_id}/start-autonomous`
- `GET /api/scans/{scan_id}/browser-plan`
- `POST /api/scans/{scan_id}/browser-plan/execute`
- `GET /api/scans/{scan_id}/evidence`
- `POST /api/scans/{scan_id}/approvals/request-upload-verification`

Approvals:

- `GET /api/scans/{scan_id}/approvals`
- `POST /api/approvals/{approval_id}/approve`
- `POST /api/approvals/{approval_id}/reject`

Findings and reports:

- `GET /api/findings`
- `GET /api/findings/{finding_id}`
- `POST /api/reports`
- `GET /api/reports/{report_id}/download`

Settings:

- `POST /api/settings/llm/profiles`
- `POST /api/settings/llm/profiles/{profile_id}/test`

## 5. Scan Creation Contract

Required fields:

- `workspace_id`
- `project_id`
- `target_id`
- `scan_type`
- `model_profile_id`

Important optional fields:

- `autonomy_level`: default `guarded`.
- `intensity`: default `normal`.
- `max_runtime_minutes`: default `120`.
- `max_cost_usd`: deployment default.
- `instructions`: operator free-text guidance.
- `policy_overrides`: restricted to users with permission.

Supported `scan_type` values:

- `passive_blackbox`
- `active_blackbox`
- `autonomous_blackbox`
- `whitebox`
- `hybrid`

Credit behavior:

- Validate available workspace credits before accepting a scan.
- Reserve one credit transactionally when the scan is queued.
- Deduct the reserved credit exactly once when scan status becomes `completed`.
- Release the reserved credit when scan status becomes `failed`, `cancelled`, or `blocked`.
- Keep the reservation while status is `queued`, `running`, `paused`, or `awaiting_approval`.
- Record every credit state change in the immutable credit ledger.
- Confirmed billing checkout sessions create invoice and payment records, then grant purchased credits through the same immutable credit ledger.
- Reconfirming an already paid checkout session is idempotent and does not grant credits twice.
- Signed billing webhooks are verified with `KERISLAB_BILLING_WEBHOOK_SECRET`, stored as provider events, and processed idempotently by provider event ID.

## 6. Event Delivery

Use append-only persisted events and expose them to the UI. The current web app polls `GET /api/scans/{scan_id}/events` and refreshes related scan state. WebSocket or SSE delivery is an upcoming scale feature for lower-latency Mission Control updates.

Event envelope:

- `id`
- `scan_id`
- `type`
- `summary`
- `payload`
- `created_at`

The UI restores the active mission from local storage and reloads historical events from the API after refresh.

## 7. Security and Policy

- Production access requires Google OAuth or configured enterprise SSO.
- API clients authenticate with persisted bearer-token sessions; logout revokes the session token.
- Workspace Owner/Admin users configure allowed SSO email domains; matching Google/SSO identities auto-join as Developer members.
- Workspace membership is checked on every project, target, scan, finding, report, event, audit, and credit endpoint.
- Owner/Admin roles are required for manual credit grants and billing checkout confirmation.
- Owner/Admin/Security Lead roles are required for model provider profile management.
- Resolve DNS and validate IP before every network action.
- Re-check scope after redirects.
- All tool execution goes through policy.
- Redact secrets before LLM calls and logs.
- Persist blocked actions as events.
- Approval decisions create audit log entries.
- Scan workers run in isolated workspaces.

## 8. Deployment Modes

Local:

- Docker Compose.
- Local object storage path.
- One API and one worker.
- Google OAuth or development-only auth bypass.

Team:

- API replicas.
- Multiple workers.
- Managed PostgreSQL.
- Redis.
- S3-compatible object storage.
- Dedicated LiteLLM service.

Enterprise:

- Kubernetes.
- Per-scan job isolation.
- NetworkPolicies.
- Google OAuth plus enterprise OIDC/SAML SSO.
- Central logs and metrics.
- External secret manager.
