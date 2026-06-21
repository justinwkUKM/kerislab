export type AuthProvider = "google" | "sso";
export type ScanType = "passive_blackbox" | "autonomous_blackbox" | "whitebox_review";

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
  owner_user_id: string;
};

export type CreditAccount = {
  workspace_id: string;
  available: number;
  reserved: number;
  consumed: number;
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
};

export type Approval = {
  id: string;
  scan_id: string;
  status: string;
  title: string;
  requested_action: string;
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
};

export type Finding = {
  id: string;
  scan_id: string;
  severity: string;
  title: string;
  asset: string;
  status: string;
};

export type ModelProfile = {
  id: string;
  workspace_id: string;
  name: string;
  model: string;
  api_base: string;
};

export type LedgerEntry = {
  id: string;
  workspace_id: string;
  entry_type: string;
  amount: number;
  note: string;
};

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  userId?: string;
};

export class KerisLabApi {
  constructor(private readonly baseUrl = import.meta.env.VITE_API_BASE_URL ?? "") {}

  async devLogin() {
    return this.request<{ user: User; session_header: { "X-KerisLab-User": string } }>("/api/auth/dev-login", {
      method: "POST",
      body: {
        email: "owner@kerislab.local",
        display_name: "KerisLab Owner",
        provider: "google"
      }
    });
  }

  async me(userId: string) {
    return this.request<{ user: User; settings: UserSettings; memberships: unknown[] }>("/api/auth/me", { userId });
  }

  async updateSettings(userId: string, body: Partial<UserSettings>) {
    return this.request<{ settings: UserSettings }>("/api/users/me", { method: "PATCH", userId, body });
  }

  async createWorkspace(userId: string) {
    return this.request<{ workspace: Workspace; credits: CreditAccount }>("/api/workspaces", {
      method: "POST",
      userId,
      body: { name: "KerisLab Lab", initial_credits: 5 }
    });
  }

  async createProject(userId: string, workspaceId: string) {
    return this.request<{ project: Project }>("/api/projects", {
      method: "POST",
      userId,
      body: { workspace_id: workspaceId, name: "Autonomous Web Assessment" }
    });
  }

  async createTarget(userId: string, workspaceId: string, projectId: string) {
    return this.request<{ target: Target }>("/api/targets", {
      method: "POST",
      userId,
      body: {
        workspace_id: workspaceId,
        project_id: projectId,
        name: "Example Web App",
        url: "https://example.com"
      }
    });
  }

  async createModelProfile(userId: string, workspaceId: string) {
    return this.request<{ profile: ModelProfile }>("/api/settings/llm/profiles", {
      method: "POST",
      userId,
      body: {
        workspace_id: workspaceId,
        name: "Default LiteLLM",
        model: "openai/gpt-4o-mini",
        api_base: "http://localhost:4000"
      }
    });
  }

  async testModelProfile(userId: string, profileId: string) {
    return this.request<{ ok: boolean; profile_id: string; model: string; route: string }>(
      `/api/settings/llm/profiles/${profileId}/test`,
      { method: "POST", userId }
    );
  }

  async createScan(userId: string, workspaceId: string, projectId: string, targetId: string, profileId: string) {
    return this.request<{ scan: Scan; credits: CreditAccount }>("/api/scans", {
      method: "POST",
      userId,
      body: {
        workspace_id: workspaceId,
        project_id: projectId,
        target_id: targetId,
        scan_type: "autonomous_blackbox",
        model_profile_id: profileId,
        instructions: "Focus on auth, upload handling, and UI-driven crawl paths."
      }
    });
  }

  async startAutonomous(userId: string, scanId: string) {
    return this.request<{ scan: Scan; plan: { current_phase: string; phases: string[] } }>(
      `/api/scans/${scanId}/start-autonomous`,
      { method: "POST", userId }
    );
  }

  async browserPlan(userId: string, scanId: string) {
    return this.request<{ browser_plan: BrowserPlan }>(`/api/scans/${scanId}/browser-plan`, { userId });
  }

  async requestUploadApproval(userId: string, scanId: string) {
    return this.request<{ approval: Approval; scan: Scan }>(
      `/api/scans/${scanId}/approvals/request-upload-verification`,
      { method: "POST", userId }
    );
  }

  async approve(userId: string, approvalId: string) {
    return this.request<{ approval: Approval }>(`/api/approvals/${approvalId}/approve`, {
      method: "POST",
      userId,
      body: { note: "Approved from Mission Control" }
    });
  }

  async completeScan(userId: string, scanId: string) {
    return this.request<{ scan: Scan; credits: CreditAccount }>(`/api/scans/${scanId}/complete`, {
      method: "POST",
      userId
    });
  }

  async events(userId: string, scanId: string) {
    return this.request<{ events: ScanEvent[] }>(`/api/scans/${scanId}/events`, { userId });
  }

  async findings(userId: string, scanId: string) {
    return this.request<{ findings: Finding[] }>(`/api/findings?scan_id=${scanId}`, { userId });
  }

  async ledger(userId: string, workspaceId: string) {
    return this.request<{ entries: LedgerEntry[] }>(`/api/workspaces/${workspaceId}/credit-ledger`, { userId });
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
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
  settings?: UserSettings;
  workspace?: Workspace;
  credits?: CreditAccount;
  project?: Project;
  target?: Target;
  profile?: ModelProfile;
  profileTest?: string;
  browserPlan?: BrowserPlan;
  scan?: Scan;
  approval?: Approval;
  events: ScanEvent[];
  findings: Finding[];
  ledger: LedgerEntry[];
};

export async function runMvpWorkflow(api = new KerisLabApi()): Promise<MissionState> {
  const login = await api.devLogin();
  const userId = login.user.id;
  const workspace = await api.createWorkspace(userId);
  const project = await api.createProject(userId, workspace.workspace.id);
  const target = await api.createTarget(userId, workspace.workspace.id, project.project.id);
  const profile = await api.createModelProfile(userId, workspace.workspace.id);
  const profileTest = await api.testModelProfile(userId, profile.profile.id);
  const createdScan = await api.createScan(
    userId,
    workspace.workspace.id,
    project.project.id,
    target.target.id,
    profile.profile.id
  );
  const started = await api.startAutonomous(userId, createdScan.scan.id);
  const browserPlan = await api.browserPlan(userId, started.scan.id);
  const approval = await api.requestUploadApproval(userId, started.scan.id);
  const approved = await api.approve(userId, approval.approval.id);
  const completed = await api.completeScan(userId, approval.scan.id);
  const settings = await api.updateSettings(userId, { theme: "light", timezone: "Asia/Kuala_Lumpur" });
  const events = await api.events(userId, completed.scan.id);
  const findings = await api.findings(userId, completed.scan.id);
  const ledger = await api.ledger(userId, workspace.workspace.id);

  return {
    user: login.user,
    settings: settings.settings,
    workspace: workspace.workspace,
    credits: completed.credits,
    project: project.project,
    target: target.target,
    profile: profile.profile,
    profileTest: `${profileTest.model} via ${profileTest.route}`,
    browserPlan: browserPlan.browser_plan,
    scan: completed.scan,
    approval: approved.approval,
    events: events.events,
    findings: findings.findings,
    ledger: ledger.entries
  };
}
