# KerisLab Spec Index

## Purpose

This directory turns KerisLab from a concept into a spec-driven product plan. The documents are designed to guide implementation by humans or coding agents without requiring major product decisions during build.

## Product Thesis

KerisLab is an Apple-inspired AI security testing platform for guarded autonomous pentesting, blackbox testing, whitebox testing, and hybrid assessments. It uses LiteLLM as the model gateway so any OpenAI-compatible provider can be used without provider-specific application code.

## Document Set

1. `01-functional-specification.md`: what the product must do.
2. `02-personas.md`: who the product is for and how that shapes decisions.
3. `03-user-stories.md`: user-facing behavior and acceptance criteria.
4. `04-autonomous-pentesting-engine.md`: autonomous engine design, policies, agents, approvals, and event model.
5. `05-ui-ux-design-system.md`: Apple-inspired interface direction, screens, components, colors, typography, motion, and accessibility.
6. `06-technical-architecture.md`: services, data model, API shape, queues, storage, LiteLLM, and deployment.
7. `07-acceptance-test-plan.md`: validation strategy and release gates.
8. `08-docker-compose-deployment.md`: local/container deployment, persistence, health checks, backup, restore, and operations.

## Implementation Order

1. Platform foundations: API, database, queue, worker, web shell, LiteLLM connectivity.
2. Identity foundations: Google OAuth, enterprise SSO, user profile, workspace membership, user/workspace settings.
3. Credit foundations: workspace credit accounts, credit ledger, scan credit reservations, completion deduction.
4. Scope and policy: targets, scope rules, network blocking, audit log.
5. Scan core: create scan, reserve credit, run worker, persist events, persist findings and evidence.
6. Autonomous blackbox foundation: guarded agent loop, Playwright tools, safe HTTP tools, Mission Control UI.
7. Approval gates: approval requests, pause/resume, operator instructions, audit trail.
8. Whitebox foundation: repository ingestion, Semgrep, dependency scanning, secret scanning, code-aware findings.
9. Reporting: JSON, Markdown, PDF, SARIF, retest workflow.
10. Scale and hardening: worker isolation, object-storage lifecycle, Kubernetes, budget enforcement.

## Decision Defaults

- Autonomy default: guarded.
- First autonomous feature: blackbox web pentest.
- UI model: Mission Control cockpit.
- Visual direction: Apple-inspired, light-first, polished, restrained, and operational.
- LLM gateway: LiteLLM only.
- Authentication: Google OAuth plus enterprise SSO from the first platform release.
- Credit owner: workspace-level credits.
- Credit rule: reserve one credit at scan start and deduct it only when the scan reaches `completed`.
- Browser automation: Playwright.
- Backend: FastAPI.
- Worker queue: Redis-backed worker queue.
- Database: PostgreSQL.
- Frontend: React, TypeScript, Vite.
