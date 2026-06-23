CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  provider TEXT NOT NULL,
  avatar_url TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
  user_id TEXT PRIMARY KEY REFERENCES users(id),
  default_workspace_id TEXT,
  theme TEXT NOT NULL,
  timezone TEXT NOT NULL,
  notifications_enabled INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  token TEXT NOT NULL UNIQUE,
  auth_provider TEXT NOT NULL,
  user_agent TEXT,
  ip_address TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS oauth_states (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  state TEXT NOT NULL UNIQUE,
  nonce TEXT NOT NULL,
  redirect_uri TEXT NOT NULL,
  consumed_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  allowed_domains TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_memberships (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  user_id TEXT NOT NULL REFERENCES users(id),
  role TEXT NOT NULL,
  UNIQUE(workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS workspace_credit_accounts (
  workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id),
  available INTEGER NOT NULL,
  reserved INTEGER NOT NULL,
  consumed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_ledger_entries (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  entry_type TEXT NOT NULL,
  amount INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  scan_id TEXT,
  note TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS billing_customers (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  provider TEXT NOT NULL,
  provider_customer_id TEXT NOT NULL,
  billing_email TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(provider, provider_customer_id)
);

CREATE TABLE IF NOT EXISTS billing_checkout_sessions (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  provider TEXT NOT NULL,
  credit_amount INTEGER NOT NULL,
  unit_amount_cents INTEGER NOT NULL,
  currency TEXT NOT NULL,
  status TEXT NOT NULL,
  provider_session_id TEXT,
  checkout_url TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS billing_invoices (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  checkout_session_id TEXT NOT NULL REFERENCES billing_checkout_sessions(id),
  provider TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  currency TEXT NOT NULL,
  status TEXT NOT NULL,
  provider_invoice_id TEXT,
  created_at TEXT NOT NULL,
  paid_at TEXT
);

CREATE TABLE IF NOT EXISTS billing_payments (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  invoice_id TEXT NOT NULL REFERENCES billing_invoices(id),
  provider TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  currency TEXT NOT NULL,
  status TEXT NOT NULL,
  provider_payment_id TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS billing_webhook_events (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  provider_event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  processed INTEGER NOT NULL,
  error TEXT NOT NULL,
  received_at TEXT NOT NULL,
  processed_at TEXT,
  UNIQUE(provider, provider_event_id)
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS targets (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  includes TEXT NOT NULL,
  excludes TEXT NOT NULL,
  allow_private_networks INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_profiles (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  name TEXT NOT NULL,
  model TEXT NOT NULL,
  api_base TEXT NOT NULL,
  timeout_seconds INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scans (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  target_id TEXT NOT NULL REFERENCES targets(id),
  scan_type TEXT NOT NULL,
  model_profile_id TEXT NOT NULL,
  status TEXT NOT NULL,
  autonomy_level TEXT NOT NULL,
  instructions TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS scan_jobs (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scans(id),
  job_type TEXT NOT NULL,
  status TEXT NOT NULL,
  payload TEXT NOT NULL,
  attempts INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  error TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_events (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scans(id),
  type TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_plans (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scans(id),
  phases TEXT NOT NULL,
  current_phase TEXT NOT NULL,
  objective TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS browser_plans (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scans(id),
  target_url TEXT NOT NULL,
  engine TEXT NOT NULL,
  actions TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS browser_executions (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scans(id),
  browser_plan_id TEXT NOT NULL REFERENCES browser_plans(id),
  engine TEXT NOT NULL,
  status TEXT NOT NULL,
  result TEXT NOT NULL,
  error TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS evidence_artifacts (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scans(id),
  artifact_type TEXT NOT NULL,
  uri TEXT NOT NULL UNIQUE,
  summary TEXT NOT NULL,
  content_type TEXT NOT NULL,
  content TEXT NOT NULL,
  browser_execution_id TEXT REFERENCES browser_executions(id),
  finding_id TEXT,
  metadata TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_requests (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  scan_id TEXT NOT NULL REFERENCES scans(id),
  requested_by_agent TEXT NOT NULL,
  risk_category TEXT NOT NULL,
  target TEXT NOT NULL,
  proposed_tool TEXT NOT NULL,
  proposed_action TEXT NOT NULL,
  reason TEXT NOT NULL,
  expected_evidence TEXT NOT NULL,
  policy_reason TEXT NOT NULL,
  status TEXT NOT NULL,
  resolved_by TEXT,
  operator_note TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS findings (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scans(id),
  title TEXT NOT NULL,
  severity TEXT NOT NULL,
  affected_asset TEXT NOT NULL,
  evidence_refs TEXT NOT NULL,
  status TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  scan_id TEXT NOT NULL REFERENCES scans(id),
  title TEXT NOT NULL,
  format TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  actor_user_id TEXT,
  workspace_id TEXT,
  project_id TEXT,
  target_id TEXT,
  scan_id TEXT,
  approval_id TEXT,
  report_id TEXT,
  details TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS worker_heartbeats (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  queue_name TEXT NOT NULL,
  status TEXT NOT NULL,
  processed_jobs INTEGER NOT NULL,
  error TEXT NOT NULL,
  started_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
