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
- TanStack Query for API state.
- WebSocket or SSE client for scan events.
- Apple-inspired design system implemented as CSS variables and reusable components.

API:

- FastAPI.
- Google OAuth, enterprise SSO, sessions, profile/settings, workspace membership, credits, projects, targets, scans, findings, reports, settings, audit logs.
- Creates scan jobs and reads persisted scan state.
- Streams scan events.

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

Object Storage:

- Local filesystem for MVP.
- S3-compatible storage for scale.
- Stores screenshots, transcripts, logs, source snippets, report files, and scanner artifacts.

## 3. Core Data Entities

- `projects`
- `users`
- `user_profiles`
- `user_settings`
- `auth_identities`
- `sessions`
- `workspaces`
- `workspace_memberships`
- `sso_configurations`
- `workspace_credit_accounts`
- `credit_ledger_entries`
- `scan_credit_reservations`
- `targets`
- `target_scope_rules`
- `scan_policies`
- `scans`
- `scan_phases`
- `scan_events`
- `agent_plans`
- `agent_memory`
- `approval_requests`
- `tool_runs`
- `llm_calls`
- `browser_sessions`
- `findings`
- `finding_evidence`
- `reports`
- `audit_logs`

## 4. API Surface

Auth and profile:

- `GET /api/auth/providers`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/users/me`
- `PATCH /api/users/me`

Workspaces:

- `GET /api/workspaces`
- `GET /api/workspaces/{workspace_id}`
- `GET /api/workspaces/{workspace_id}/members`
- `POST /api/workspaces/{workspace_id}/members/invite`
- `PATCH /api/workspaces/{workspace_id}/sso`
- `GET /api/workspaces/{workspace_id}/credits`
- `GET /api/workspaces/{workspace_id}/credit-ledger`

Projects and targets:

- `POST /api/projects`
- `GET /api/projects`
- `POST /api/projects/{project_id}/targets`
- `GET /api/projects/{project_id}/targets`

Scans:

- `POST /api/scans`
- `GET /api/scans/{scan_id}`
- `GET /api/scans/{scan_id}/events`
- `POST /api/scans/{scan_id}/pause`
- `POST /api/scans/{scan_id}/resume`
- `POST /api/scans/{scan_id}/cancel`
- `POST /api/scans/{scan_id}/instructions`

Approvals:

- `GET /api/scans/{scan_id}/approvals`
- `POST /api/approvals/{approval_id}/approve`
- `POST /api/approvals/{approval_id}/reject`

Findings and reports:

- `GET /api/findings`
- `GET /api/findings/{finding_id}`
- `PATCH /api/findings/{finding_id}`
- `POST /api/reports`
- `GET /api/reports/{report_id}/download`

Settings:

- `GET /api/settings/llm/profiles`
- `POST /api/settings/llm/profiles`
- `POST /api/settings/llm/profiles/{profile_id}/test`
- `GET /api/settings/policies`
- `PATCH /api/settings/policies/{policy_id}`

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

## 6. Event Stream

Use append-only persisted events and stream them live to the UI.

Event envelope:

- `id`
- `scan_id`
- `sequence`
- `timestamp`
- `type`
- `actor`
- `severity`
- `summary`
- `payload`

The UI must be able to reconnect and request events after the last seen `sequence`.

## 7. Security and Policy

- Production access requires Google OAuth or configured enterprise SSO.
- Workspace membership and role are checked on every project, target, scan, finding, report, settings, and credit endpoint.
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
