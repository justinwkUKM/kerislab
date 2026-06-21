# KerisLab Functional Specification Document

## 1. Overview

KerisLab is a self-hosted AI security testing platform for guarded autonomous pentesting, blackbox testing, whitebox testing, and hybrid source-plus-runtime assessments. It provides a polished Web UI, autonomous agents powered through LiteLLM, sandboxed tool execution, evidence-backed findings, and exportable reports.

## 2. Goals

- Let security operators run approved autonomous blackbox pentests from a Mission Control UI.
- Let application teams run repeatable whitebox scans against source repositories.
- Let teams combine source and staging URLs for hybrid assessments.
- Support OpenAI-compatible providers through LiteLLM without provider-specific app code.
- Support Google OAuth and enterprise SSO as first-class login paths from the first release.
- Track workspace credits and deduct one credit for each completed scan.
- Make every scan auditable: scope, policy, plan, LLM calls, tool runs, approvals, evidence, findings, reports.
- Use an Apple-inspired design language: sleek, calm, precise, light-first, and high trust.

## 3. Users and Roles

- Owner: configures deployment, model providers, auth, retention, and global policies.
- Security Lead: creates projects, approves risky actions, reviews reports.
- Pentester: runs autonomous and manual scans, triages findings, adds instructions.
- Developer: reviews whitebox findings and remediation guidance.
- Auditor: reads evidence, reports, and audit logs.

## 4. Core Capabilities

### 4.0 Authentication, Profile, and Workspace

- Users sign in with Google OAuth or a configured enterprise SSO provider.
- Workspace access is controlled through invited membership, allowed domains, or SSO claims.
- User profile includes display name, email, avatar, auth provider, role, default workspace, preferred theme, timezone, and notification preferences.
- User settings include profile preferences, connected identity display, sessions/devices, notification settings, and default workspace.
- Workspace settings include members, roles, SSO configuration, allowed domains, credit balance, credit ledger, LiteLLM profiles, retention, and notification webhooks.
- Production deployments must not rely on anonymous access; local development may use a development-only auth bypass.

### 4.1 Projects

- Create, edit, archive, and delete projects.
- Projects group targets, scans, findings, evidence, reports, and settings.
- Project settings define default model profile, scan policy, retention, and notification hooks.

### 4.2 Targets and Scope

- Create blackbox targets: URL, domain, API base URL, IP range, or explicit host list.
- Create whitebox targets: Git URL, uploaded archive, or local mounted path.
- Define includes, excludes, allowed schemes, allowed ports, max rate, auth context, and private-network allowance.
- Persist a scope snapshot at scan start.
- Block loopback, metadata, link-local, private IP, and out-of-scope redirects unless explicitly allowed.

### 4.3 Scan Types

- Passive blackbox scan: recon and low-risk checks.
- Active blackbox scan: DAST checks within defined intensity and rate.
- Autonomous blackbox pentest: guarded agent-driven end-to-end test.
- Whitebox scan: static and code-aware review.
- Hybrid scan: source-aware dynamic testing against a live URL.

### 4.3.1 Scan Credits

- Credits belong to a workspace.
- Creating a scan requires one available workspace credit unless the scan is explicitly marked as admin/test bypass.
- Starting a scan reserves one credit.
- A completed scan deducts the reserved credit.
- Failed, cancelled, blocked, or errored scans release the reserved credit.
- Paused scans keep the credit reserved.
- Retests are new scans and require a new credit.
- Credit ledger entries are immutable and record grants, reserves, deductions, releases, adjustments, and refunds.

### 4.4 Autonomous Blackbox Pentest

- Operator starts a scan from the UI with target, model profile, intensity, max runtime, max spend, and optional instructions.
- Agent creates a plan with phases and objectives.
- Safe actions run automatically.
- Risky actions produce approval requests.
- Mission Control streams phase status, plan changes, browser snapshots, tool calls, approvals, findings, and evidence.
- Operator can pause, resume, cancel, approve, reject, or add instructions.

### 4.5 Whitebox Testing

- Ingest source from Git, archive, or mounted path.
- Index manifests, routes, API schemas, dependencies, IaC, secrets patterns, and framework clues.
- Run deterministic scanners first: Semgrep, dependency audit, secret scan.
- Use LLMs for prioritization, explanation, and remediation, not unsupported claims.
- Findings include source references and confidence.

### 4.6 Findings

- Findings require evidence before they can be marked verified.
- Findings include severity, confidence, status, category, CWE/OWASP, affected asset, impact, reproduction, evidence, remediation, and source refs.
- Finding statuses: new, triaged, verified, false_positive, accepted_risk, fixed, retest_required.
- Verification statuses: unverified, suspected, verified.

### 4.7 Evidence

- Store HTTP transcripts, screenshots, browser snapshots, terminal logs, source snippets, scanner output, and generated reports.
- Raw evidence is immutable.
- User notes and edits are stored separately.
- Evidence is linked to findings and scan events.

### 4.8 Reports

- Generate JSON reports for automation.
- Generate Markdown reports for review.
- Generate PDF reports for delivery.
- Generate SARIF for whitebox/code findings.
- Reports must be generated from stored findings and evidence.

### 4.9 LiteLLM Settings

- Configure provider profiles with model, API base, key reference, timeout, retry, and budget.
- Test a profile before saving.
- Support default, cheap, reasoning, local/private, and fallback models.
- Log model, provider route, token use, cost estimate, latency, prompt hash, and redaction status.

## 5. Non-Functional Requirements

- Security: deny unsafe network targets by default; redact secrets before LLM calls; audit sensitive actions.
- Reliability: scans must resume or fail clearly after worker restart.
- Performance: UI updates should feel live within 1 second of new scan events.
- Scalability: workers must be horizontally scalable.
- Accessibility: all main workflows must be keyboard accessible and meet WCAG AA contrast.
- Usability: the UI should remain calm under scan noise by grouping events and surfacing decisions.

## 6. MVP Release Criteria

- Sign in with Google OAuth or configured enterprise SSO.
- View and update user profile/settings.
- Create or join a workspace with membership and role.
- Grant workspace credits and view the credit ledger.
- Create project and blackbox target.
- Configure LiteLLM profile and verify model call.
- Reserve one credit when starting a scan.
- Start autonomous blackbox pentest with guarded defaults.
- Stream Mission Control events.
- Run safe recon, crawl, and low-risk HTTP/browser tests.
- Gate risky actions with approval requests.
- Persist evidence-backed findings.
- Deduct one credit when the scan completes successfully or release it if the scan fails/cancels.
- Export JSON and Markdown report.
