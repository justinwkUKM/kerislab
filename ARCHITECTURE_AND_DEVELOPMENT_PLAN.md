# KerisLab

## 1. Product Direction

Build a self-hosted platform for AI-assisted application security testing with two primary modes:

- Blackbox testing: test externally reachable applications without source access.
- Whitebox testing: test source repositories, local folders, containers, and application artifacts with code-aware analysis.
- Autonomous pentesting: Web/UI-driven guarded autonomy for approved blackbox targets, with approval gates for high-risk actions.

The platform should offer functionality similar in spirit to Xalgorix: autonomous scan orchestration, LLM-driven reasoning, browser and terminal tools, live progress, findings, reports, and notifications. KerisLab differentiates through guarded autonomy, explicit blackbox/whitebox/hybrid modes, a mission-control scan cockpit, and an Apple-inspired interface with generous spacing, polished motion, glass-like surfaces, and restrained color.

All LLM access should go through LiteLLM so the platform can use OpenAI-compatible APIs and route across OpenAI, Anthropic, Gemini, DeepSeek, local models, vLLM, Ollama, and enterprise gateways.

## 2. Core Goals

1. Run authorized blackbox and whitebox security tests from one dashboard.
2. Support any LiteLLM-compatible model provider.
3. Keep tools sandboxed, auditable, and scoped to approved targets.
4. Stream agent progress, tool calls, logs, findings, and evidence in real time.
5. Store reproducible scan artifacts and generate concise reports.
6. Scale from single-machine local use to multi-worker deployments.
7. Keep the UI minimal, dense, and operational rather than decorative.
8. Provide Web/UI-driven autonomous scans through a mission-control experience with phase timeline, agent plan, browser view, tool stream, approvals, findings, and evidence.
9. Treat Google login and enterprise SSO as first-class MVP authentication paths.
10. Enforce workspace-level scan credits, deducting one credit only after a scan completes successfully.

## 3. Non-Goals for the First Version

1. Fully autonomous exploitation against arbitrary infrastructure.
2. Payment processing, subscription billing, marketplace, or external commerce.
3. Heavy SIEM/SOAR integrations beyond webhooks and export APIs.
4. Replacing professional pentesters; the platform should assist, queue, verify, and document.
5. Running unsafe actions outside explicit scope and policy controls.

## 4. User Workflows

### 4.1 Blackbox Scan

1. Operator creates a target scope: domains, URLs, IP ranges, exclusions, allowed ports, and rate limits.
2. Operator chooses scan mode: passive recon, active DAST, auth-aware web test, API test, or deep assessment.
3. Platform validates scope and blocks private/local targets unless explicitly allowed.
4. Agent runs recon, crawling, browser interaction, HTTP probing, vulnerability checks, and verification.
5. Findings appear live with severity, evidence, request/response samples, screenshots, and reproduction notes.
6. Operator exports report or resumes the scan with additional instructions.

### 4.2 Whitebox Scan

1. Operator connects a Git repository, uploads source, or points to a local path.
2. Platform indexes files, dependencies, manifests, routes, API schemas, IaC, secrets patterns, and test configuration.
3. Agent performs static analysis, code-aware threat modeling, dependency review, and targeted proof checks.
4. Optional dynamic phase builds/runs the app in an isolated workspace and tests discovered attack surfaces.
5. Findings include source references, data-flow notes, exploitability reasoning, remediation guidance, and confidence.

### 4.3 Hybrid Assessment

1. Operator supplies source plus staging URL.
2. Platform maps routes/endpoints from code to live behavior.
3. Agent prioritizes tests based on auth flows, risky sinks, exposed APIs, dependency CVEs, and business logic paths.
4. Report links runtime evidence to source code locations.

### 4.4 Autonomous Blackbox Pentest

1. Operator selects an approved target and chooses Autonomous Pentest.
2. Platform applies guarded autonomy defaults: safe recon and DAST actions run automatically; high-risk actions create approval requests.
3. Mission Control shows the current phase, agent plan, browser viewport, tool stream, approval queue, findings, and evidence.
4. Operator can pause, resume, cancel, approve, reject, or add instructions during the scan.
5. Agent verifies findings before report generation and marks each item as verified, suspected, or unverified.

## 5. High-Level Architecture

Use a modular service architecture that can start as a single deployable app and later split into services.

```text
Browser UI
  |
  | REST + WebSocket/SSE
  v
API Server
  |
  | creates jobs / reads state
  v
PostgreSQL + Object Storage
  |
  | queues scans
  v
Job Queue
  |
  v
Worker Pool
  |
  | calls tools through policy gates
  v
Autonomous Orchestrator + Agent Runtime
  |
  | LLM requests
  v
LiteLLM Gateway
  |
  v
OpenAI-compatible Providers
```

## 6. Recommended Stack

### Backend

- Language: Python with FastAPI for rapid agent/tool development, or Go if the priority is a single static binary.
- Recommended first build: Python/FastAPI because LiteLLM, browser automation, code indexing, and security tooling integrate faster.
- API: FastAPI REST endpoints plus WebSocket or Server-Sent Events for scan streams.
- Queue: Redis Queue, Dramatiq, Celery, or Arq for MVP; Temporal for larger deployments.
- Database: PostgreSQL.
- Object storage: local filesystem for MVP, S3-compatible storage for scale.
- Auth: Google OAuth and enterprise SSO from MVP, backed by server-side sessions.

### Frontend

- Framework: React + TypeScript + Vite.
- UI style: minimal dashboard, compact tables, split panes, findings timeline, terminal/log panes.
- Component approach: shadcn/ui or Radix primitives with a restrained design system.
- State: TanStack Query for API data and a small event store for live scan updates.

### LLM Layer

- LiteLLM as the only model gateway.
- Support provider profiles: `provider`, `model`, `api_base`, `api_key_ref`, `budget`, `timeout`, `retries`.
- Add routing policies: default model, cheap model, reasoning model, local/offline model.
- Record every LLM call: prompt hash, model, latency, tokens, cost estimate, scan id, and redaction status.

### Tooling

- Browser automation: Playwright.
- HTTP testing: httpx/aiohttp, custom request runner, optional proxy integration.
- Recon: httpx, dnsx, subfinder/amass, naabu/nmap where explicitly installed.
- Web scanning: nuclei templates, custom checks, API schema fuzzing.
- Code analysis: tree-sitter, Semgrep, dependency scanners, secret scanners.
- Container execution: Docker or rootless Podman for isolated dynamic tests.

## 7. Service Breakdown

### 7.1 API Server

Responsibilities:

- Authentication and authorization.
- Google OAuth, enterprise SSO, sessions, user profile, workspace membership, and roles.
- Project, target, scan, finding, and report APIs.
- Workspace credit account and credit ledger APIs.
- Scope validation before scan creation.
- WebSocket/SSE event fanout.
- Settings management for LiteLLM provider profiles.
- Audit log and export endpoints.

Key endpoints:

- `POST /api/projects`
- `POST /api/targets`
- `POST /api/scans`
- `GET /api/scans/{id}`
- `GET /api/scans/{id}/events`
- `POST /api/scans/{id}/pause`
- `POST /api/scans/{id}/resume`
- `POST /api/scans/{id}/cancel`
- `GET /api/findings`
- `PATCH /api/findings/{id}`
- `POST /api/reports`
- `GET /api/settings/llm/providers`
- `GET /api/auth/providers`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/users/me`
- `PATCH /api/users/me`
- `GET /api/workspaces/{workspace_id}/credits`
- `GET /api/workspaces/{workspace_id}/credit-ledger`
- `PATCH /api/workspaces/{workspace_id}/sso`

### 7.2 Scan Orchestrator

Responsibilities:

- Convert a scan request into a directed execution plan.
- Select blackbox, whitebox, or hybrid playbooks.
- Enforce max runtime, budget, rate limits, and allowed tool classes.
- Reserve one workspace credit before queueing a scan and deduct it only when the scan completes.
- Persist phase transitions and resumable state.
- Retry failed safe steps and stop unsafe steps.
- Route autonomous blackbox scans into the autonomous pentesting engine.

Phases:

1. Scope validation.
2. Asset discovery or source indexing.
3. Attack surface mapping.
4. Test planning.
5. Tool execution.
6. Finding verification.
7. Deduplication and severity normalization.
8. Report generation.

### 7.3 Agent Runtime

Responsibilities:

- Execute guarded autonomous pentest plans through specialized agents.
- Maintain conversation state and compressed memory per scan.
- Choose tools through a policy-aware function calling layer.
- Ask LiteLLM for reasoning, planning, summarization, and verification.
- Emit structured events after every thought, action, result, and finding.
- Avoid direct shell access; all tool execution goes through registered tools.

Agent types:

- Recon agent: assets, technologies, URLs, APIs.
- Web test agent: crawling, browser actions, HTTP tests, DAST checks.
- Code review agent: static analysis, data-flow review, dependency review.
- Verification agent: validates findings and reduces false positives.
- Report agent: writes concise remediation-focused reports.

### 7.3.1 Autonomous Pentesting Engine

Responsibilities:

- Decompose an operator goal into phases, objectives, and proposed actions.
- Run approved safe actions automatically under the scan policy.
- Create approval requests for exploit-like, destructive, brute-force, high-volume, credential-sensitive, or private-network actions.
- Maintain a live agent plan and publish mission-control events.
- Pause, resume, cancel, and recover autonomous scan state.

Default autonomy level: guarded.

First implementation scope: autonomous blackbox web scans.

### 7.4 Tool Gateway

Responsibilities:

- Own all calls to shell, browser, network, filesystem, Git, and scanners.
- Apply scope policy before execution.
- Normalize tool outputs into structured JSON.
- Redact secrets before storing outputs or sending to LLMs.
- Track timeouts, stdout/stderr limits, and resource consumption.

Tool categories:

- `network.read`: DNS, HTTP GET, passive recon.
- `network.active`: crawling, fuzzing, nuclei, active probes.
- `browser`: Playwright sessions, screenshots, DOM extraction.
- `filesystem.read`: repository and artifact reads.
- `filesystem.write`: scan workspace writes only.
- `code.analysis`: Semgrep, tree-sitter, dependency audit.
- `reporting`: markdown, PDF, SARIF, JSON export.

### 7.5 LiteLLM Gateway

Responsibilities:

- Centralize model credentials.
- Provide OpenAI-compatible API to the platform.
- Route model names to providers.
- Enforce per-scan or per-project budgets.
- Enable caching, retries, fallback models, and observability.

Deployment options:

- Embedded development mode: app calls a local LiteLLM process.
- Production mode: LiteLLM runs as a separate service behind the API network.
- Enterprise mode: LiteLLM connects to internal model gateways and audit stores.

### 7.6 Evidence Store

Responsibilities:

- Store screenshots, HTTP transcripts, terminal logs, source snippets, generated files, and reports.
- Keep immutable raw evidence and separate operator-edited finding notes.
- Support retention policies.
- Use object storage keys like `projects/{project_id}/scans/{scan_id}/evidence/{artifact_id}`.

## 8. Data Model

Core tables:

- `users`: operator accounts.
- `user_profiles`: display name, avatar URL, timezone, theme, notification preferences.
- `user_settings`: per-user defaults such as default workspace and preferred model profile.
- `auth_identities`: Google and enterprise SSO identity links.
- `sessions`: server-side authenticated sessions.
- `workspaces`: team/account boundary for members, credits, projects, and settings.
- `workspace_memberships`: user roles within workspaces.
- `sso_configurations`: workspace enterprise SSO configuration.
- `workspace_credit_accounts`: available, reserved, and consumed workspace credits.
- `credit_ledger_entries`: immutable grant, reserve, deduct, release, adjustment, and refund records.
- `scan_credit_reservations`: scan-to-credit reservation state.
- `projects`: assessment workspaces.
- `targets`: approved blackbox targets and source targets.
- `target_scope_rules`: includes, excludes, allowed ports, allowed hosts, private-network permissions.
- `llm_profiles`: provider, model, LiteLLM route, encrypted key reference.
- `scans`: scan metadata, mode, status, budget, timestamps.
- `scan_phases`: phase status and timing.
- `scan_events`: append-only event stream.
- `agent_plans`: current and historical agent objectives, phases, and planned actions.
- `approval_requests`: gated actions pending operator approval.
- `agent_memory`: compressed phase summaries and scan memory.
- `browser_sessions`: Playwright state, snapshots, visited URLs, forms, and network metadata.
- `tool_runs`: normalized record of every tool execution.
- `llm_calls`: model calls, tokens, cost, latency, purpose.
- `findings`: normalized vulnerabilities and confidence.
- `finding_evidence`: links to artifacts, requests, screenshots, source refs.
- `reports`: generated report metadata.
- `audit_logs`: settings changes, scan actions, auth events.

Finding fields:

- `title`
- `severity`
- `confidence`
- `status`
- `category`
- `cwe`
- `owasp`
- `affected_asset`
- `description`
- `impact`
- `reproduction_steps`
- `evidence_refs`
- `remediation`
- `source_refs`
- `verification_status`

## 9. Security Boundaries

### 9.1 Scope Enforcement

- Block private, loopback, link-local, metadata, and platform control-plane addresses by default.
- Resolve DNS before each network action and re-check after redirects.
- Require explicit allow-list for private network testing.
- Enforce scheme, host, port, and path exclusions.
- Persist the exact approved scope snapshot with each scan.

### 9.2 Sandbox

- Run every scan in an isolated workspace.
- Run active tools in containers or restricted subprocesses.
- Use network egress controls where possible.
- Limit CPU, memory, runtime, file output, and subprocess depth.
- Keep tool secrets out of the scan workspace.

### 9.3 Prompt and Data Controls

- Redact API keys, cookies, JWTs, SSH keys, cloud credentials, and `.env` values before LLM calls.
- Do not send full repositories to the LLM by default; send selected snippets and summaries.
- Keep a prompt audit trail with hashes and redaction metadata.
- Add configurable no-cloud mode for local LLM-only whitebox reviews.

### 9.4 Human Control

- Require approval gates for exploit-like actions, destructive tests, auth brute force, or high-volume fuzzing.
- Mark findings as unverified, suspected, or verified.
- Let operators pause, cancel, and constrain scans at any point.

## 10. Minimal UI Design

Navigation:

- Projects
- Scans
- Findings
- Targets
- Reports
- Settings

Primary screens:

- Login: Apple-inspired sign-in with Continue with Google and enterprise SSO where configured.
- Dashboard: active scans, recent findings, queue health, model spend.
- New Scan: target picker, blackbox/whitebox mode, intensity, model profile, policy toggles.
- Scan Detail: phase rail, event stream, tool runs, findings, evidence viewer.
- Findings: table with severity, confidence, status, affected asset, source refs.
- Evidence Viewer: request/response, screenshot, terminal log, source snippet.
- User Profile: identity, avatar, timezone, theme, notifications, sessions.
- Workspace Settings: members, roles, SSO, credits, LiteLLM provider profiles, retention, notification webhooks.

Design principles:

- Apple-inspired light-first theme with near-white surfaces, black typography, subtle translucency, precision spacing, restrained gradients, and smooth but purposeful motion.
- Compact tables and split panes.
- No marketing hero screen.
- No decorative dashboards that hide operational state.
- Keyboard-friendly workflows for triage and finding review.
- Mission Control scan cockpit for autonomous runs: phase rail, agent plan, browser view, tool stream, approval queue, findings, and evidence.

## 11. Deployment Architecture

### 11.1 Local Single-Node

```text
docker compose up
  - api
  - worker
  - postgres
  - redis
  - litellm
```

Use local filesystem storage mounted as `./data`.

### 11.2 Team Deployment

```text
Load Balancer
  -> API replicas
  -> Worker replicas
  -> PostgreSQL
  -> Redis
  -> S3-compatible object storage
  -> LiteLLM
```

### 11.3 Scaled Deployment

- Kubernetes.
- Separate blackbox and whitebox worker pools.
- Per-scan isolated Kubernetes jobs.
- NetworkPolicies for scan egress.
- Centralized logs and metrics.
- Dedicated LiteLLM deployment with budget controls.

## 12. Observability

Metrics:

- Scan duration by mode and phase.
- Queue wait time.
- Tool failure rate.
- LLM latency, tokens, and cost.
- Finding counts by severity and verification status.
- Worker CPU, memory, and timeout counts.

Logs:

- Structured JSON logs.
- Per-scan event logs.
- Redacted tool output logs.
- Audit logs for operator and settings actions.

Tracing:

- Trace scan phase execution.
- Trace LLM calls and tool calls.
- Correlate API request id, scan id, worker id, and event id.

## 13. Development Plan

### Phase 0: Specification and Foundations

Deliverables:

- Architecture document.
- Threat model.
- Data model migrations.
- API contract draft.
- Docker Compose skeleton.
- LiteLLM configuration template.
- Google OAuth and enterprise SSO configuration model.
- Workspace credit account and ledger model.

Acceptance criteria:

- A developer can start Postgres, Redis, LiteLLM, API, and one worker locally.
- API exposes health checks and settings endpoints.
- LLM profile can be configured and tested through LiteLLM.
- Google login and enterprise SSO configuration are represented in the API/data model from the first milestone.
- Workspace credit balance can be granted, reserved, deducted, released, and audited.

### Phase 1: MVP Blackbox Scanner

Deliverables:

- Project and target CRUD.
- Scope validation.
- Scan creation and queueing.
- Worker executes passive recon and basic HTTP checks.
- Live scan event stream.
- Basic findings table.
- JSON report export.

Suggested checks:

- Technology fingerprinting.
- Security headers.
- TLS metadata.
- Directory discovery with strict rate limits.
- Basic reflected input checks.
- Login page and form detection.

Acceptance criteria:

- Operator can create a blackbox scan for an allowed URL.
- Events stream live to the UI.
- Findings are persisted with evidence.
- Scope blocks unsafe targets by default.

### Phase 2: LLM Agent Loop

Deliverables:

- Agent runtime with tool registry.
- LiteLLM-backed planning and summarization.
- Tool policy enforcement.
- Event schema for agent messages and tool calls.
- Finding verification pass.

Acceptance criteria:

- Agent can plan a test sequence from target metadata.
- Every tool call is recorded.
- LLM calls are logged with model, tokens, and scan id.
- Agent cannot call tools outside allowed scope.

### Phase 2.5: Autonomous Blackbox Pentest

Deliverables:

- Autonomous Pentest scan type.
- Guarded autonomy policy engine.
- Mission Control UI.
- Approval requests for gated actions.
- Playwright browser tools and safe HTTP testing tools.
- Agent plan persistence and event streaming.

Acceptance criteria:

- Operator can start an autonomous blackbox scan from the UI.
- Safe actions run without manual approval inside approved scope.
- Gated actions pause and request approval before execution.
- Mission Control shows phase, plan, browser snapshots, tool stream, findings, evidence, and approvals.
- Every agent decision, LLM call, tool run, approval, and finding is auditable.

### Phase 3: Whitebox Scanner

Deliverables:

- Git/local source ingestion.
- Repository indexing.
- Semgrep integration.
- Dependency scanning.
- Secret scanning.
- Code-aware finding format with file references.

Acceptance criteria:

- Operator can scan a repository.
- Findings include source references and remediation.
- Secrets are redacted before LLM use.
- Large repositories are summarized and chunked rather than sent wholesale.

### Phase 4: Hybrid Testing

Deliverables:

- Link source target to live URL target.
- Route and endpoint discovery from code.
- API schema parsing.
- Playwright authenticated crawl.
- Runtime evidence linked to source references.

Acceptance criteria:

- Platform maps discovered code routes to live endpoints.
- Agent prioritizes tests based on code risk.
- Findings can include both request evidence and source evidence.

### Phase 5: Reporting and Collaboration

Deliverables:

- Markdown and PDF reports.
- Finding status workflow.
- Commenting or notes.
- Retest scans.
- Webhook notifications.
- SARIF export for code findings.

Acceptance criteria:

- Operator can mark findings verified, false positive, accepted risk, or fixed.
- Report generation is repeatable from stored evidence.
- Whitebox findings can export to SARIF.

### Phase 6: Scale and Hardening

Deliverables:

- Worker autoscaling.
- Per-scan container isolation.
- Budget enforcement.
- Enterprise SSO hardening for Google OAuth plus OIDC/SAML providers.
- Retention policies.
- Admin audit views.
- Kubernetes manifests.

Acceptance criteria:

- Multiple scans run concurrently without event or artifact collisions.
- Resource limits are enforced.
- LiteLLM spend can be capped per scan and project.
- Audit logs capture sensitive actions.

## 14. Suggested Repository Structure

```text
kerislab/
  apps/
    api/
    worker/
    web/
  packages/
    agent/
    tools/
    policy/
    schemas/
    reporting/
  infra/
    docker-compose.yml
    litellm.config.yaml
    postgres/
    k8s/
  docs/
    architecture.md
    threat-model.md
    api.md
    development-plan.md
  tests/
    fixtures/
    integration/
```

## 15. First Implementation Slice

Build this first:

1. Docker Compose with Postgres, Redis, LiteLLM, API, worker, and web.
2. API health check and LiteLLM test endpoint.
3. Google OAuth/SSO auth foundation, user profile, workspace, membership, and settings models.
4. Workspace credit account, credit ledger, and scan credit reservation flow.
5. Project and target models.
6. Scope validator with DNS/IP blocking.
7. Scan queue and worker loop.
8. Passive blackbox scan playbook.
9. Event stream into minimal scan detail UI.
10. Findings persistence and JSON export.

This slice proves the hardest architectural paths early: model routing, scan orchestration, policy enforcement, event streaming, and evidence persistence.

## 16. Key Risks and Mitigations

Risk: LLM hallucinated findings.
Mitigation: require evidence, verification status, and deterministic scanner support where possible.

Risk: unsafe network activity.
Mitigation: scope snapshots, DNS re-resolution, egress controls, rate limits, and approval gates.

Risk: leaking sensitive source or secrets to cloud models.
Mitigation: redaction, local model profiles, no-cloud mode, and snippet-level context.

Risk: workers becoming hard to scale.
Mitigation: stateless workers, queue-based jobs, object storage artifacts, and append-only events.

Risk: UI becoming too complex.
Mitigation: center the product on scans, findings, evidence, and reports; keep advanced controls in settings.

Risk: credit accounting becomes inconsistent during scan failure or worker restart.
Mitigation: use explicit reservation state, idempotent completion handlers, ledger entries, and transactional credit updates.

Risk: social login blocks local development.
Mitigation: keep a development-only auth bypass while production defaults require Google OAuth or configured SSO.

## 17. Recommended MVP Technology Choices

Use these unless there is a strong reason to optimize differently:

- API: FastAPI.
- Worker: Python async worker with Dramatiq or Arq.
- Queue: Redis.
- Database: PostgreSQL with SQLAlchemy or SQLModel.
- Migrations: Alembic.
- UI: React, TypeScript, Vite, TanStack Query, Radix/shadcn.
- Browser: Playwright.
- LLM: LiteLLM proxy.
- Static analysis: Semgrep and tree-sitter.
- Reports: Markdown first, PDF second.
- Packaging: Docker Compose first, Kubernetes later.

## 18. Milestone Timeline

Week 1:

- Repository scaffold, Compose, health checks, database migrations, Google/SSO auth model, workspace model, credit ledger, LiteLLM profile test.

Week 2:

- Projects, targets, scope policy, scan queue, worker loop, event stream.

Week 3:

- Passive blackbox checks, findings persistence, scan detail UI.

Week 4:

- Agent runtime, tool registry, LiteLLM planning, finding verification.

Week 5:

- Autonomous blackbox pentest, guarded approval gates, Mission Control UI.

Week 6:

- Source ingestion, Semgrep, dependency and secret scanning.

Week 7:

- Report generation, findings workflow, webhook notifications.

Week 8 and later:

- Hybrid scans, authenticated browser flows, scaling, enterprise hardening.

## 19. Spec-Driven Development Documents

Use the documents under `docs/` as the implementation source of truth:

- `00-spec-index.md`: document map and build order.
- `01-functional-specification.md`: detailed FSD.
- `02-personas.md`: target users, goals, pains, and product implications.
- `03-user-stories.md`: epics, stories, and acceptance criteria.
- `04-autonomous-pentesting-engine.md`: autonomy, agents, policies, events, and approval gates.
- `05-ui-ux-design-system.md`: Apple-inspired visual language, layouts, components, motion, and accessibility.
- `06-technical-architecture.md`: deployable architecture, services, data flows, APIs, and schemas.
- `07-acceptance-test-plan.md`: acceptance, security, UI, and integration test plan.
