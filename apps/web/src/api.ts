export type AuthProvider = "google" | "sso" | "development";
export type ScanType = "passive_blackbox" | "active_blackbox" | "autonomous_blackbox" | "whitebox" | "hybrid";

export type User = {
  id: string;
  email: string;
  display_name: string;
  provider: AuthProvider;
  avatar_url?: string | null;
};

export type UserSettings = {
  user_id: string;
  default_workspace_id?: string | null;
  theme: string;
  timezone: string;
  notifications_enabled: boolean;
};

export type Workspace = {
  id: string;
  name: string;
  allowed_domains?: string[];
};

export type CreditAccount = {
  workspace_id: string;
  available: number;
  reserved: number;
  consumed: number;
};

export type LedgerEntry = {
  id: string;
  workspace_id: string;
  entry_type: string;
  amount: number;
  balance_after: number;
  note: string;
  created_at?: string;
};

export type Project = {
  id: string;
  workspace_id: string;
  name: string;
};

export type Target = {
  id: string;
  workspace_id: string;
  project_id: string;
  name: string;
  url: string;
};

export type Scan = {
  id: string;
  workspace_id: string;
  project_id: string;
  target_id: string;
  scan_type: ScanType;
  status: string;
  model_profile_id: string;
  instructions: string;
  created_at?: string;
  completed_at?: string | null;
};

export type Approval = {
  id: string;
  workspace_id: string;
  scan_id: string;
  status: string;
  risk_category: string;
  target: string;
  proposed_tool: string;
  proposed_action: string;
  reason: string;
  expected_evidence: string;
  policy_reason: string;
};

export type BrowserAction = {
  id: string;
  action_type: string;
  selector: string;
  description: string;
  value?: string | null;
  requires_approval: boolean;
};

export type BrowserPlan = {
  id: string;
  scan_id: string;
  target_url: string;
  engine: string;
  actions: BrowserAction[];
};

export type ScanEvent = {
  id: string;
  scan_id: string;
  type: string;
  summary: string;
  payload?: Record<string, unknown>;
  created_at?: string;
};

export type Finding = {
  id: string;
  scan_id: string;
  severity: string;
  title: string;
  affected_asset: string;
  status: string;
  verification_status: string;
  evidence_refs: string[];
};

export type EvidenceArtifact = {
  id: string;
  scan_id: string;
  artifact_type: string;
  uri: string;
  summary: string;
  content_type: string;
  metadata: Record<string, unknown>;
};

export type ModelProfile = {
  id: string;
  workspace_id: string;
  name: string;
  model: string;
  api_base: string;
};

export type Report = {
  id: string;
  workspace_id: string;
  project_id: string;
  scan_id: string;
  title: string;
  format: string;
  content: Record<string, unknown>;
  created_at?: string;
};

export type HealthComponents = {
  status: string;
  worker_heartbeat: {
    status: string;
    active: number;
    total: number;
    workers: Array<{
      id: string;
      name: string;
      queue_name: string;
      processed_jobs: number;
      last_seen_at: string;
      status: string;
    }>;
  };
  queue: {
    queued: number;
    running: number;
    failed: number;
  };
};

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  token?: string;
  userId?: string;
};

export class KerisLabApi {
  constructor(private readonly baseUrl = import.meta.env.VITE_API_BASE_URL ?? "") {}

  googleLogin() {
    return this.request<{ authorization_url: string }>("/api/auth/google/login");
  }

  ssoLogin() {
    return this.request<{ authorization_url: string }>("/api/auth/sso/login");
  }

  devLogin() {
    return this.request<{ user: User; access_token: string; settings?: UserSettings }>("/api/auth/dev-login", {
      method: "POST",
      body: {
        email: "owner@kerislab.local",
        display_name: "KerisLab Owner",
        provider: "google"
      }
    });
  }

  me(token: string) {
    return this.request<{ user: User; settings: UserSettings; memberships: unknown[] }>("/api/auth/me", { token });
  }

  health() {
    return this.request<{ status: string; service: string }>("/api/health");
  }

  healthComponents() {
    return this.request<HealthComponents>("/api/health/components");
  }

  updateSettings(token: string, body: Partial<UserSettings>) {
    return this.request<{ settings: UserSettings }>("/api/users/me", { method: "PATCH", token, body });
  }

  listWorkspaces(token: string) {
    return this.request<{ workspaces: Workspace[] }>("/api/workspaces", { token });
  }

  createWorkspace(token: string, name = "KerisLab Lab", initialCredits = 5) {
    return this.request<{ workspace: Workspace; credits: CreditAccount }>("/api/workspaces", {
      method: "POST",
      token,
      body: { name, initial_credits: initialCredits }
    });
  }

  credits(token: string, workspaceId: string) {
    return this.request<{ credits: CreditAccount }>(`/api/workspaces/${workspaceId}/credits`, { token });
  }

  ledger(token: string, workspaceId: string) {
    return this.request<{ entries: LedgerEntry[] }>(`/api/workspaces/${workspaceId}/credit-ledger`, { token });
  }

  createProject(token: string, workspaceId: string, name = "Autonomous Web Assessment") {
    return this.request<{ project: Project }>("/api/projects", {
      method: "POST",
      token,
      body: { workspace_id: workspaceId, name }
    });
  }

  createTarget(token: string, workspaceId: string, projectId: string, url: string, name = "Primary Web App") {
    return this.request<{ target: Target }>("/api/targets", {
      method: "POST",
      token,
      body: { workspace_id: workspaceId, project_id: projectId, name, url }
    });
  }

  createModelProfile(token: string, workspaceId: string) {
    return this.request<{ profile: ModelProfile }>("/api/settings/llm/profiles", {
      method: "POST",
      token,
      body: {
        workspace_id: workspaceId,
        name: "Default LiteLLM",
        model: "openai/gpt-4o-mini",
        api_base: "http://litellm:4000"
      }
    });
  }

  createScan(
    token: string,
    payload: {
      workspace_id: string;
      project_id: string;
      target_id: string;
      scan_type: ScanType;
      model_profile_id: string;
      instructions: string;
    }
  ) {
    return this.request<{ scan: Scan; credits: CreditAccount }>("/api/scans", {
      method: "POST",
      token,
      body: payload
    });
  }

  startAutonomous(token: string, scanId: string) {
    return this.request<{ scan: Scan; plan: { current_phase: string; phases: string[] } }>(
      `/api/scans/${scanId}/start-autonomous`,
      { method: "POST", token }
    );
  }

  browserPlan(token: string, scanId: string) {
    return this.request<{ browser_plan: BrowserPlan }>(`/api/scans/${scanId}/browser-plan`, { token });
  }

  executeBrowserPlan(token: string, scanId: string) {
    return this.request<{ execution_id: string; evidence_refs?: string[] }>(`/api/scans/${scanId}/browser-plan/execute`, {
      method: "POST",
      token
    });
  }

  requestUploadApproval(token: string, scanId: string) {
    return this.request<{ approval: Approval; scan: Scan }>(
      `/api/scans/${scanId}/approvals/request-upload-verification`,
      { method: "POST", token }
    );
  }

  approvals(token: string, scanId: string) {
    return this.request<{ approvals: Approval[] }>(`/api/scans/${scanId}/approvals`, { token });
  }

  approve(token: string, approvalId: string, note = "Approved from Mission Control") {
    return this.request<{ approval: Approval }>(`/api/approvals/${approvalId}/approve`, {
      method: "POST",
      token,
      body: { note }
    });
  }

  reject(token: string, approvalId: string, note = "Rejected from Mission Control") {
    return this.request<{ approval: Approval }>(`/api/approvals/${approvalId}/reject`, {
      method: "POST",
      token,
      body: { note }
    });
  }

  completeScan(token: string, scanId: string) {
    return this.request<{ scan: Scan; credits: CreditAccount }>(`/api/scans/${scanId}/complete`, {
      method: "POST",
      token
    });
  }

  events(token: string, scanId: string) {
    return this.request<{ events: ScanEvent[] }>(`/api/scans/${scanId}/events`, { token });
  }

  findings(token: string, scanId?: string) {
    return this.request<{ findings: Finding[] }>(`/api/findings${scanId ? `?scan_id=${scanId}` : ""}`, { token });
  }

  evidence(token: string, scanId: string) {
    return this.request<{ evidence: EvidenceArtifact[] }>(`/api/scans/${scanId}/evidence`, { token });
  }

  executionJobs(token: string) {
    return this.request<{ jobs: unknown[]; pending: unknown[] }>("/api/execution/jobs", { token });
  }

  createReport(token: string, scanId: string, format = "json") {
    return this.request<{ report: Report }>("/api/reports", {
      method: "POST",
      token,
      body: { scan_id: scanId, format }
    });
  }

  reportDownloadUrl(reportId: string) {
    return `${this.baseUrl}/api/reports/${reportId}/download`;
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
        ...(options.userId ? { "X-KerisLab-User": options.userId } : {})
      },
      body: options.body ? JSON.stringify(options.body) : undefined
    });

    if (!response.ok) {
      const details = await response.text();
      throw new Error(`KerisLab API ${response.status}: ${details}`);
    }

    return response.json() as Promise<T>;
  }
}

export type MissionState = {
  user?: User;
  token?: string;
  settings?: UserSettings;
  workspace?: Workspace;
  credits?: CreditAccount;
  project?: Project;
  target?: Target;
  profile?: ModelProfile;
  browserPlan?: BrowserPlan;
  scan?: Scan;
  approval?: Approval;
  approvals: Approval[];
  events: ScanEvent[];
  findings: Finding[];
  evidence: EvidenceArtifact[];
  ledger: LedgerEntry[];
  health?: HealthComponents;
};

export async function bootstrapDemoWorkspace(api = new KerisLabApi()): Promise<MissionState> {
  const login = await api.devLogin();
  const token = login.access_token;
  const workspace = await api.createWorkspace(token);
  const project = await api.createProject(token, workspace.workspace.id);
  const target = await api.createTarget(token, workspace.workspace.id, project.project.id, "https://example.com");
  const profile = await api.createModelProfile(token, workspace.workspace.id);
  const settings = await api.updateSettings(token, { theme: "light", timezone: "Asia/Kuala_Lumpur" });
  const ledger = await api.ledger(token, workspace.workspace.id);
  const health = await api.healthComponents();

  return {
    user: login.user,
    token,
    settings: settings.settings,
    workspace: workspace.workspace,
    credits: workspace.credits,
    project: project.project,
    target: target.target,
    profile: profile.profile,
    approvals: [],
    events: [],
    findings: [],
    evidence: [],
    ledger: ledger.entries,
    health
  };
}
