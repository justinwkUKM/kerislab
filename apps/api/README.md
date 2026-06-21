# KerisLab API MVP

This is the first backend slice of KerisLab. It provides the domain model and FastAPI entrypoints for:

- Google/SSO-ready identity shape with development login.
- User profile/settings.
- Workspaces and memberships.
- Workspace credits and immutable ledger entries.
- Projects and scoped targets.
- Scan creation with one-credit reservation.
- Passive scan execution with evidence-backed findings.
- Autonomous scan planning, approval gates, and event logging.
- Web/UI-driven scan planning with Playwright-oriented browser actions.
- Scan completion credit deduction and failure/cancellation release.

The core service layer is dependency-light and covered by pytest/unittest-compatible tests. FastAPI is used for the runtime API surface.

Run locally:

```bash
make run-api
```

Verify:

```bash
make test-api
```
