# KerisLab Asset Manifest

## Brand

- `brand/kerislab-mark.svg`: primary symbol for navigation, favicon source, app shell, docs, and compact lockups.
- `brand/kerislab-wordmark.svg`: horizontal brand lockup for login, reports, and presentations.
- `brand/kerislab-app-icon.svg`: rounded app icon for launchers, PWA, docs, and social previews.

## Backgrounds

- `backgrounds/login-atmosphere.svg`: login screen background.
- `backgrounds/aurora-light.svg`: dashboard and settings ambient background.
- `backgrounds/mission-control-grid.svg`: scan cockpit and evidence workspace background.

## Icons

All feature icons use a 64x64 grid, rounded 2px stroke caps, and consistent visual weight.

- `icons/autonomous-pentest.svg`
- `icons/blackbox-scan.svg`
- `icons/whitebox-review.svg`
- `icons/hybrid-assessment.svg`
- `icons/approval-gate.svg`
- `icons/evidence-locker.svg`
- `icons/workspace-credits.svg`
- `icons/litellm-router.svg`
- `icons/report-export.svg`
- `icons/identity-sso.svg`

## Illustrations

- `illustrations/mission-control-panel.svg`: high-level product illustration for docs, onboarding, and empty dashboard states.

## Implementation Notes

- Use the mark and icons as inline SVG when theme-aware coloring is needed.
- Use backgrounds as CSS `background-image` assets on full-width surfaces.
- Do not use Apple logos, Apple device imagery, or exact Apple compositions with this asset set.
- Keep UI icons from a product icon library such as lucide for operational buttons; these assets are for brand, feature, navigation, empty states, and presentation surfaces.

