# KerisLab Web MVP

React/Vite shell for the KerisLab MVP. The current screen set demonstrates:

- Apple-inspired Google/SSO login.
- Dashboard with workspace credits.
- Mission Control autonomous scan cockpit.
- Scan list and findings summary.
- API-backed MVP workflow for login, workspace bootstrap, model profile test, autonomous scan, approval, completion, settings, events, and credit ledger.
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
