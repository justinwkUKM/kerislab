# KerisLab UI/UX Design System

## 1. Design Direction

KerisLab should feel like a premium Apple-inspired professional tool: quiet, precise, polished, spacious, and confident. The interface should use sleek surfaces, excellent typography, subtle translucency, high-quality motion, and restrained color. It should not copy Apple assets, logos, product names, imagery, or exact page layouts.

The UI must remain an operational security platform, not a marketing site. The first screen after login is the product dashboard, not a landing page.

## 2. Visual Principles

- Light-first interface with optional dark mode later.
- Near-white background, black typography, cool gray dividers, and selective accent colors.
- Large open areas for top-level screens, denser layouts inside scan and finding workspaces.
- Rounded corners are modest: 8px for tool surfaces, 12px for major panels, 16px for modals.
- Use layered translucency sparingly for navigation, sidebars, and Mission Control headers.
- Motion should clarify state changes: scan phase transitions, approvals, panel reveals, and finding creation.

## 3. Color Tokens

Core:

- `background`: `#F5F5F7`
- `surface`: `#FFFFFF`
- `surface-elevated`: `rgba(255,255,255,0.78)`
- `text-primary`: `#1D1D1F`
- `text-secondary`: `#6E6E73`
- `border`: `#D2D2D7`
- `hairline`: `rgba(0,0,0,0.08)`

Accents:

- `accent-blue`: `#0071E3`
- `accent-cyan`: `#00A7D1`
- `accent-green`: `#34C759`
- `accent-yellow`: `#FFCC00`
- `accent-red`: `#FF3B30`
- `accent-indigo`: `#5856D6`

Severity:

- Info: blue.
- Low: green.
- Medium: yellow.
- High: red-orange.
- Critical: red with dark text treatment and strong border.

## 4. Typography

- Use `SF Pro` when available through system font stack: `-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif`.
- Do not use huge marketing hero typography inside dashboards.
- Dashboard page title: 32px, 40px line height, 600 weight.
- Section title: 20px, 28px line height, 600 weight.
- Table text: 13px or 14px, 20px line height.
- Labels and metadata: 12px, 16px line height.
- Letter spacing: 0.

## 5. Layout System

Global shell:

- Top translucent command bar with product name, global search, project switcher, active model profile, and user menu.
- Left navigation rail for Projects, Scans, Findings, Targets, Reports, Settings.
- Main content uses 24px page padding on desktop and 16px on tablet/mobile.
- Use max-width only for settings and forms; operational screens can use full width.

Mission Control layout:

- Top strip: scan name, status, phase, elapsed time, spend, controls.
- Left rail: phase timeline and current agent plan.
- Center: browser viewport/snapshot and event stream tabs.
- Right rail: approvals, findings, evidence summary.
- Bottom drawer: selected tool run, HTTP transcript, source snippet, or screenshot details.

## 6. Core Screens

Login:

- Apple-inspired light-first sign-in screen.
- Primary action: Continue with Google.
- Secondary action: Continue with SSO when workspace SSO is configured.
- Minimal copy, centered composition, no marketing hero, no password form in MVP.
- Error states for blocked domain, missing invite, disabled workspace, and SSO failure.

Dashboard:

- Active autonomous scans.
- Recent findings by severity.
- Queue and worker health.
- Model spend and token usage.
- Workspace credit balance and reserved credits.
- Recent reports.

New Scan:

- Segmented scan type selector: Passive Blackbox, Active Blackbox, Autonomous Pentest, Whitebox, Hybrid.
- Target picker.
- Intensity selector.
- Model profile.
- Max runtime and max spend.
- Required credits and current workspace balance.
- Guarded autonomy policy preview.
- Optional operator instructions.
- Disabled start state when credits are unavailable.

Mission Control:

- Built for live autonomous scan supervision.
- Must show what the agent is doing, why it is doing it, and what needs approval.
- Avoid noisy raw logs as the primary UI; raw logs live behind selected events.

Findings:

- Dense table with severity, confidence, status, affected asset, title, scan, owner, and updated time.
- Detail panel shows evidence, reproduction, remediation, source refs, and verification history.

Settings:

- Profile and sessions.
- Workspace members and roles.
- Google/SSO identity configuration.
- Workspace credits and ledger.
- LiteLLM profiles.
- Policies.
- Auth.
- Retention.
- Notifications.
- Worker/runtime limits.

## 7. Components

- Segmented controls for scan type, intensity, and finding status.
- Icon buttons for pause, resume, cancel, approve, reject, export, and expand.
- Tables for findings, tool runs, scans, and audit logs.
- Timeline for scan phases and events.
- Drawer for evidence details.
- Modal for approval decisions.
- Toasts for short system confirmations only.
- Empty states with concise action buttons.

## 8. Motion

- Page transition: 120-180ms ease-out opacity and vertical offset.
- Mission Control event arrival: subtle fade/slide, no bouncing.
- Approval request: soft highlight pulse until acknowledged.
- Phase completion: progress rail animates once.
- Respect reduced-motion settings.

## 9. Accessibility

- WCAG AA contrast minimum.
- Full keyboard navigation for scan controls and approval decisions.
- Visible focus rings using `accent-blue`.
- Screen-reader labels for icon-only controls.
- Tables must support sorting and clear column labels.

## 10. Implementation Guidance

- Use `assets/` as the canonical source for KerisLab brand marks, backgrounds, feature icons, and illustrations.
- Use CSS variables for tokens.
- Use Radix/shadcn primitives where possible.
- Use lucide icons for tool buttons.
- Keep data-dense screens clean through spacing, grouping, and typography rather than decorative cards.
- Do not use Apple trademarks, assets, wallpapers, device imagery, or exact copied compositions.
