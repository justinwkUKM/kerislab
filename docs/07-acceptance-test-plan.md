# KerisLab Acceptance and Test Plan

## 1. Release Gates

The current platform foundation is acceptable when:

- A user can sign in with Google or configured enterprise SSO.
- A user can view/update profile and settings.
- A workspace has members, roles, credit balance, and credit ledger.
- A user can configure a LiteLLM profile and test it.
- A user can create a project and approved blackbox target.
- A user can start an autonomous blackbox scan with guarded defaults.
- Starting the scan reserves one workspace credit.
- Completing the scan deducts one credit.
- Mission Control polls persisted events and restores active scan context after refresh.
- Safe actions execute automatically inside scope.
- Gated actions require approval before execution.
- Findings are evidence-backed and persisted.
- JSON reports generate from saved findings and can be downloaded.
- Docker Compose starts web, API, worker, PostgreSQL, Redis, MinIO, and LiteLLM with health checks.

Upcoming release gates:

- WebSocket or SSE event delivery for lower-latency Mission Control updates.
- Markdown, PDF, and SARIF report formats.
- Whitebox repository ingestion and deterministic scanner integrations.
- Production identity-provider management UI.
- Stronger per-scan worker isolation and multi-worker scheduling controls.

## 2. Functional Tests

Auth, profile, and workspace:

- Google login creates or links a user identity.
- Enterprise SSO login creates or links a user identity.
- Domain allowlist blocks unauthorized users.
- Logout invalidates session.
- Current-user endpoint returns profile, settings, workspace, role, and auth provider.
- User can update timezone, theme, notification preferences, and default workspace.
- Workspace admin can invite members and update SSO settings.

Credits:

- Owner/Admin can grant workspace credits.
- Starting a scan reserves one credit.
- Completed scan deducts the reserved credit exactly once.
- Failed, cancelled, blocked, or errored scan releases the reserved credit.
- Paused scan keeps the credit reserved.
- Retest requires a new credit.
- Scan start is blocked when available credits are zero.
- Concurrent scans cannot over-reserve credits.
- Credit ledger records grant, reserve, deduct, release, adjustment, and refund.

Projects and targets:

- Create, update, archive project.
- Add URL target with include and exclude rules.
- Reject invalid target formats.
- Persist scope snapshot when scan starts.

LiteLLM:

- Create model profile.
- Test profile success.
- Test profile failure with clear error.
- Log provider route, latency, token use, and redaction status.

Scans:

- Create passive blackbox scan.
- Create autonomous blackbox scan.
- Pause, resume, cancel.
- Add operator instruction during active scan.
- Stop scan on max runtime.
- Stop or pause scan on max cost.

Approvals:

- Create approval request for gated action.
- Approve request and continue.
- Reject request and force replan.
- Prevent execution before approval.

Findings:

- Create candidate finding.
- Attach evidence.
- Mark suspected.
- Mark verified after confirmation.
- Deduplicate repeated findings.

Reports:

- Generate JSON report.
- Download generated JSON report.
- Generate Markdown report as an upcoming report-format feature.
- Regenerate report without rerunning scan.

## 3. Security Tests

Scope enforcement:

- Block `127.0.0.1`.
- Block link-local ranges.
- Block cloud metadata endpoints.
- Block private IP targets by default.
- Block DNS name resolving to private IP by default.
- Block redirect to out-of-scope host.
- Respect excluded path rules.

Policy:

- Auto-allow safe GET requests in scope.
- Gate high-volume fuzzing.
- Gate destructive methods.
- Gate SSRF callback checks.
- Gate brute force attempts.
- Log blocked action event.

Secrets:

- Redact `.env` values.
- Redact API keys.
- Redact cookies and JWTs.
- Prevent redacted values from appearing in LLM call records.

## 4. UI Tests

Dashboard:

- Shows active scans, recent findings, queue health, model spend.
- Works on desktop and tablet widths.

New Scan:

- Shows scan type segmented control.
- Shows target picker.
- Shows autonomy policy preview for Autonomous Pentest.
- Shows required credits and workspace credit balance.
- Blocks scan start when credits are unavailable.
- Validates required fields.

Mission Control:

- Shows phase timeline.
- Shows current agent plan.
- Shows browser snapshot.
- Shows tool stream.
- Shows approval queue.
- Shows findings and evidence.
- Pause/resume/cancel controls update state.
- Approval modal supports keyboard use.
- Refresh restores local mission context and reloads historical events.

Accessibility:

- Icon-only buttons have labels.
- Focus rings are visible.
- Text contrast meets WCAG AA.
- Reduced motion setting is respected.

## 5. Integration Tests

- API creates scan job and worker consumes it.
- Worker writes scan events and UI receives them through polling.
- Worker calls LiteLLM through configured profile.
- Tool Gateway stores evidence artifacts and links them to findings.
- Approval request pauses gated action until resolution.
- Browser session captures screenshot and network metadata.

## 6. Load and Reliability Tests

- Run 10 concurrent passive scans.
- Run 3 concurrent autonomous scans.
- Restart worker mid-scan and confirm scan resumes or fails clearly.
- Refresh UI and confirm persisted events are reloaded.
- Simulate LiteLLM timeout and confirm scan pauses with clear error.
- Simulate browser crash and confirm one retry plus persisted failure if retry fails.

## 7. Visual QA

- Validate Apple-inspired visual direction without copying Apple assets.
- Confirm light-first theme, spacing, typography, translucency, and motion feel consistent.
- Confirm Mission Control remains usable when event volume is high.
- Confirm no text overlaps or overflows at desktop, tablet, and mobile widths.
