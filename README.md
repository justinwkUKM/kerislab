# KerisLab MVP

KerisLab is a guarded autonomous security testing platform. This MVP contains a FastAPI backend, a React/Vite web shell, shared SVG brand assets, and tests for the core scan, approval, settings, model profile, and credit flows.

## Current Stack

- Backend: FastAPI, Pydantic, Python service layer.
- Frontend: React 19, TypeScript, Vite.
- Runtime: Docker Compose for API, web, and LiteLLM gateway.
- Storage: in-memory MVP repository.
- Tests: pytest for API/domain behavior and TypeScript/Vite production build for web verification.

## Verified MVP Flows

- Google-first identity shape through development login.
- User profile and settings update.
- Workspace creation with initial credits.
- Project and scoped target creation.
- LiteLLM model profile creation and test route.
- Scan creation reserves one credit.
- Successful scan completion deducts one reserved credit exactly once.
- Failed/cancelled scans release reserved credit.
- Autonomous pentest start, gated approval request, approval resolution, and event logging.
- Web/UI-driven autonomous scan planning with Playwright-oriented browser actions and approval-required steps.
- Frontend workflow button exercises the API flow when the FastAPI backend is running.

## Local Verification

```bash
make verify
```

Equivalent commands:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q apps/api tests
cd apps/web && npm run build
```

## Local Runtime

Run API and web separately:

```bash
make run-api
make run-web
```

Or use Docker Compose:

```bash
docker compose up --build
```

The web app runs on `http://localhost:5173` and the API runs on `http://localhost:8000`.

## Production Gaps

- Replace in-memory store with PostgreSQL and migrations.
- Replace development login with real Google OAuth/OIDC and enterprise SSO.
- Move scan execution to isolated workers with queueing and sandbox controls.
- Add persistent audit logs, report storage, tenant isolation, and billing integration.
- Execute browser plans in isolated Playwright workers with screenshots, DOM snapshots, and network traces.
