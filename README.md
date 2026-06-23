# KerisLab

KerisLab is a guarded AI security testing platform for teams that need to run autonomous pentests without giving up control.

It is designed around a simple rule: the system can explore, test, and reason on its own, but risky actions stay behind explicit approval gates. That makes it useful for security teams that want automation for breadth and speed, while still keeping humans in charge of scope, credits, and high-risk steps.

## What It Does

- Runs blackbox, whitebox, and hybrid security assessments.
- Supports autonomous testing with approval requests for risky browser or HTTP actions.
- Tracks workspace credits and deducts one credit for each completed scan.
- Stores findings, evidence, scan events, and reports in a structured workflow.
- Supports Google-first authentication and enterprise SSO as product requirements.

## How The Product Is Shaped

KerisLab is built as a control surface, not just a scanner.

- The backend exposes authentication, workspaces, credits, scans, approvals, findings, and reports.
- The web app is a Mission Control-style dashboard for starting scans and reviewing results.
- The autonomous engine creates plans, emits events, and pauses for operator approval when needed.
- The browser-driven workflow is modeled around Playwright-style steps and evidence capture.

## Who It Is For

- Security leads who need repeatable assessments with human oversight.
- Pentesters who want automation for reconnaissance and safe testing.
- Developers who need clear findings, evidence, and remediation context.
- Operators who need workspace-level credit control and auditability.

## Current MVP Scope

This repository currently includes:

- FastAPI backend with in-memory MVP storage.
- React + TypeScript + Vite frontend.
- Credit reservation and deduction flow.
- User profile and settings endpoints.
- Workspace, project, target, scan, approval, finding, and report flows.
- Persistent state storage with Postgres-first, SQLite fallback when Postgres is unavailable, and in-memory fallback if local persistence fails.
- Normalized SQL migration artifacts for the production relational schema.
- Scan execution queue with Redis notifications, durable database fallback, and a worker loop for background processing.
- API-backed autonomous scan planning.
- Browser/UI-driven autonomous scan planning.
- Tests for the main API and service behavior.

## Local Verification

```bash
make verify
```

That runs:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q apps/api tests
cd apps/web && npm run build
```

## Local Development

Run the API and web app separately:

```bash
make run-api
make run-web
```

Or start the full Compose stack:

```bash
docker compose up --build
```

Web: `http://localhost:5173`

API: `http://localhost:8000`

The Compose stack runs web, API, worker, PostgreSQL, Redis, MinIO, and LiteLLM. See [Docker Compose Deployment](docs/08-docker-compose-deployment.md).

Local non-Compose SQLite state is stored in `.kerislab/kerislab.db` by default.

The local Compose stack starts the background scan worker automatically.

The API applies normalized schema migrations automatically when it initializes the configured Postgres or SQLite store. You can also apply them explicitly with `make migrate`.

Install optional Playwright runtime support for live browser execution:

```bash
.venv/bin/python -m pip install -e ".[browser]"
.venv/bin/python -m playwright install chromium
```

## Upcoming Features

The implemented platform foundation now covers OAuth/SSO entrypoints, allowed-domain SSO auto-join, migrations, browser execution records, audit, tenancy, credit accounting, provider-neutral billing checkout records, and signed billing webhook processing. The next milestones focus on production hardening and scale:

- Hosted identity provider management UI and enterprise SSO rollout workflows.
- Horizontally scaled worker pools with stronger isolation and scheduling controls.
- Evidence object storage for browser screenshots, transcripts, and scanner artifacts.
- Hosted billing provider adapters for provider-specific checkout creation and customer portal flows.
- Deployment hardening for multi-tenant production environments.
