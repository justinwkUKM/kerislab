# KerisLab User Stories

## Epic 0: Identity, Profile, and Settings

- As a user, I can sign in with Google so I can access KerisLab without a separate password.
- As an enterprise user, I can sign in with my organization's SSO so access follows company identity controls.
- As a user, I can view and update my profile settings so KerisLab reflects my name, avatar, timezone, theme, and notification preferences.
- As an Owner, I can configure allowed domains, SSO, and workspace membership so only approved users can access the workspace.
- Acceptance: unauthenticated users cannot access the product dashboard; authenticated users can access `/me`, profile, workspace, and settings data.

## Epic 0.1: Workspace Credits

- As an Owner, I can grant credits to a workspace so the team can run scans.
- As a Pentester, I can see the workspace credit balance before starting a scan.
- As a Security Lead, I can see the credit ledger so every reserve, deduction, release, and adjustment is auditable.
- As a Pentester, I cannot start a scan when the workspace has no available credits.
- Acceptance: starting a scan reserves one credit, completing the scan deducts it, and failed/cancelled/blocked scans release it.

## Epic 1: Project and Target Management

- As a Security Lead, I can create a project so scans, findings, reports, and settings are grouped by assessment.
- As a Pentester, I can add a blackbox target with includes, excludes, ports, rate limits, and auth context so testing stays in scope.
- As a Developer, I can add a repository target so KerisLab can perform source-aware analysis.
- Acceptance: target validation blocks unsafe defaults and stores the approved scope snapshot on scan start.

## Epic 2: LiteLLM Provider Management

- As a Platform Owner, I can configure LiteLLM model profiles so KerisLab can use any OpenAI-compatible provider.
- As a Security Lead, I can choose a default model profile per project so scans use approved models.
- As a Platform Owner, I can set max spend and fallback models so autonomous scans do not run uncontrolled.
- Acceptance: profile testing confirms route, model response, latency, and redacted credential handling.

## Epic 3: Autonomous Blackbox Pentest

- As a Pentester, I can start an Autonomous Pentest from a blackbox target so KerisLab handles recon, crawling, testing, verification, and reporting.
- As a Pentester, I can provide initial instructions so the agent focuses on areas like auth, APIs, business logic, or file upload.
- As a Security Lead, I can set intensity, runtime, and budget so the scan fits the engagement.
- Acceptance: safe actions run automatically, risky actions create approval requests, and all actions are visible in Mission Control.

## Epic 4: Mission Control

- As a Pentester, I can watch the phase timeline, current plan, browser snapshot, tool stream, findings, and approvals in one screen.
- As a Pentester, I can pause, resume, cancel, approve, reject, or add instructions without leaving the scan.
- As a Security Lead, I can see why the agent wants to run a gated action before approving it.
- Acceptance: UI updates live from scan events and reconnects without losing historical events.

## Epic 5: Approval Gates

- As a Security Lead, I can approve or reject high-risk actions so autonomy remains controlled.
- As an Auditor, I can see who approved an action, when, and why.
- As a Pentester, I can reject an action and give replacement instructions.
- Acceptance: no gated action executes before approval; rejected actions are skipped and logged.

## Epic 6: Whitebox Scan

- As a Developer, I can scan source code so vulnerabilities are tied to files and remediation.
- As a Security Lead, I can combine deterministic scanner output with LLM triage so findings are prioritized.
- Acceptance: secrets are redacted before LLM use and large repositories are chunked/summarized.

## Epic 7: Findings and Evidence

- As a Pentester, I can review findings with evidence so I can distinguish verified issues from suspected ones.
- As a Developer, I can see reproduction steps and remediation so I can fix issues faster.
- As an Auditor, I can inspect immutable raw evidence linked to each finding.
- Acceptance: verified findings must have evidence references and verification status.

## Epic 8: Reporting

- As a Security Lead, I can generate a report from stored evidence so the output is defensible.
- As a Developer, I can export SARIF for code findings so issues can enter development workflows.
- Acceptance: reports can be regenerated from saved scan data without rerunning the scan.

## Epic 9: Operations and Scale

- As a Platform Owner, I can run multiple workers so scans scale horizontally.
- As a Platform Owner, I can configure retention and object storage so evidence is durable.
- Acceptance: concurrent scans do not mix events, artifacts, browser sessions, or findings.
