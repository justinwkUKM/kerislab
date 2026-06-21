# KerisLab Personas

## 1. Security Lead

Profile:

- Owns application security outcomes across multiple teams.
- Needs repeatable assessments and defensible evidence.
- Reviews reports before they go to engineering or leadership.

Goals:

- Standardize blackbox, whitebox, and autonomous scan workflows.
- Keep scans within legal and technical scope.
- Reduce false positives before developers see findings.
- Track risk over time.

Pain Points:

- Autonomous tools can be noisy or unsafe.
- Findings without evidence waste review time.
- Reports often lack clear reproduction and remediation.

Product Implications:

- Strong scope controls and guarded autonomy.
- Evidence-first findings.
- Approval queue for high-risk actions.
- Clear report generation from verified evidence.

## 2. Pentester

Profile:

- Runs assessments and bug bounty-style testing.
- Understands tools, payloads, browser behavior, and test strategy.
- Wants the AI to accelerate work without hiding important details.

Goals:

- Start scans quickly.
- Watch what the agent is doing.
- Intervene with instructions.
- Approve or reject risky actions.
- Capture evidence cleanly.

Pain Points:

- Blackbox testing involves repetitive recon and crawling.
- Autonomous agents can run irrelevant steps.
- Tool logs are hard to correlate with findings.

Product Implications:

- Mission Control UI with live plan, browser, tool stream, and findings.
- Pause, resume, cancel, approve, reject, and add-instruction controls.
- Tool output linked directly to evidence and findings.

## 3. Application Developer

Profile:

- Receives findings and fixes vulnerabilities.
- May not be a security specialist.
- Needs source references and practical remediation.

Goals:

- Understand whether a finding is real.
- Find the affected code quickly.
- Reproduce the issue safely.
- Confirm the fix with a retest.

Pain Points:

- Security reports can be vague or overly broad.
- Dynamic findings often lack code context.
- Remediation can be generic.

Product Implications:

- Whitebox findings with file references.
- Hybrid findings that connect runtime evidence to source.
- Clear reproduction steps and remediation guidance.
- Retest workflow.

## 4. Platform Owner

Profile:

- Deploys and operates KerisLab.
- Manages identity providers, workspace access, credits, model providers, costs, credentials, and infrastructure.

Goals:

- Connect LiteLLM providers securely.
- Configure Google OAuth and enterprise SSO.
- Control workspace membership and roles.
- Keep workspace scan credits predictable and auditable.
- Keep usage costs predictable.
- Scale workers for scan volume.
- Maintain audit logs and retention policies.

Pain Points:

- LLM credentials are sensitive.
- Login and workspace access must satisfy enterprise identity requirements.
- Credit usage needs to be explainable when scans fail, pause, or complete.
- Model cost can spike during autonomous workflows.
- Workers can consume unexpected resources.

Product Implications:

- Provider profiles with budgets and key references.
- Google OAuth plus enterprise SSO from the first release.
- Workspace membership, user profile, and settings management.
- Workspace credit account and immutable credit ledger.
- Per-scan max spend and max runtime.
- Worker resource limits.
- Retention settings and audit log.

## 5. Auditor or Compliance Reviewer

Profile:

- Reviews evidence and process rather than running scans.
- Needs proof that testing stayed in scope and findings are justified.

Goals:

- See who approved what.
- Confirm scan policy and target scope.
- Export reports and audit logs.

Pain Points:

- Autonomous systems can be hard to explain.
- Missing logs weaken evidence.

Product Implications:

- Immutable scope snapshots.
- Append-only scan events.
- Approval audit trail.
- Report and audit export.
