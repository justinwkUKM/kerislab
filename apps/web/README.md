# KerisLab Web App

React/Vite front end for the KerisLab autonomous pentesting platform. The current screen set provides:

- Google/SSO-first login with local demo bootstrap separated from production auth.
- Dashboard with workspace credits, worker health, queue depth, approvals, and findings.
- New Scan wizard for scope, scan type, policy, spend, runtime, credits, and operator instructions.
- Mission Control autonomous scan cockpit with phase timeline, browser/evidence viewport, approval risk panel, event stream, evidence list, and agent plan.
- Command search for navigating scans, findings, targets, evidence, reports, and settings from the top bar.
- Findings workspace with search, severity/status filters, sorted triage table, selected row state, and detail panel.
- Evidence selection with copy/open artifact actions.
- Targets, Reports, Profile, Workspace, SSO, Credits, LiteLLM, and Runtime settings surfaces.
- Local session restore across refreshes for the active user/workspace/scan context.
- Live polling for runtime health, credits, scan events, approvals, findings, and evidence.
- Report generation, report download link, and editable profile notification/timezone settings.
- API-backed workflow for login, workspace bootstrap, model profile setup, autonomous scan, approval, completion, settings, events, evidence, health, and credit ledger.
- Shared KerisLab SVG assets from the root `assets/` folder.

Install and run:

```bash
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Build verification:

```bash
npm run build
```
