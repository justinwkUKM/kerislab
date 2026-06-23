import { useEffect, useState } from "react";
import {
  Approval,
  BrowserAction,
  EvidenceArtifact,
  Finding,
  HealthComponents,
  KerisLabApi,
  MissionState,
  Report,
  ScanEvent,
  ScanType,
  bootstrapDemoWorkspace
} from "./api";

type Screen = "dashboard" | "new-scan" | "mission" | "findings" | "targets" | "reports" | "settings";
type Toast = { tone: "info" | "success" | "warning" | "danger"; message: string };
type CommandResult = { id: string; label: string; detail: string; screen: Screen };
type FindingFilters = { query: string; severity: string; status: string };

const api = new KerisLabApi();
const STORAGE_KEY = "kerislab.mission.v1";
const asset = (path: string) => new URL(`../../../assets/${path}`, import.meta.url).href;

const initialMission: MissionState = {
  approvals: [],
  events: [],
  findings: [],
  evidence: [],
  ledger: []
};

const previewFindings: Finding[] = [
  {
    id: "preview-1",
    scan_id: "preview",
    severity: "info",
    title: "Security header review ready",
    affected_asset: "https://example.com",
    status: "new",
    verification_status: "verified",
    evidence_refs: ["evidence://preview/security-headers"]
  },
  {
    id: "preview-2",
    scan_id: "preview",
    severity: "medium",
    title: "Session policy checks configured",
    affected_asset: "/login",
    status: "triaged",
    verification_status: "suspected",
    evidence_refs: ["evidence://preview/session-policy"]
  },
  {
    id: "preview-3",
    scan_id: "preview",
    severity: "high",
    title: "Upload endpoint requires gated verification",
    affected_asset: "/api/upload",
    status: "new",
    verification_status: "unverified",
    evidence_refs: ["evidence://preview/upload"]
  }
];

const defaultHealth: HealthComponents = {
  status: "degraded",
  worker_heartbeat: { status: "missing", active: 0, total: 0, workers: [] },
  queue: { queued: 0, running: 0, failed: 0 }
};

export function App() {
  const [mission, setMission] = useState<MissionState>(() => loadStoredMission());
  const [screen, setScreen] = useState<Screen>(() => screenFromHash());
  const [isBusy, setIsBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [commandQuery, setCommandQuery] = useState("");
  const [findingFilters, setFindingFilters] = useState<FindingFilters>({ query: "", severity: "all", status: "all" });
  const [settingsDraft, setSettingsDraft] = useState({ timezone: "Asia/Kuala_Lumpur", notifications_enabled: true });
  const [scanDraft, setScanDraft] = useState({
    targetUrl: "https://example.com",
    scanType: "autonomous_blackbox" as ScanType,
    intensity: "Guarded",
    maxRuntime: "45",
    maxSpend: "8",
    instructions: "Focus on authentication, upload handling, and UI-driven crawl paths."
  });

  const health = mission.health ?? defaultHealth;
  const findings = mission.findings.length ? mission.findings : previewFindings;
  const selectedFinding = findings.find((finding) => finding.id === selectedFindingId) ?? findings[0];
  const selectedEvidence =
    mission.evidence.find((evidence) => evidence.id === selectedEvidenceId) ?? mission.evidence[0];
  const pendingApproval = mission.approvals.find((approval) => approval.status === "pending") ?? mission.approval;
  const token = mission.token;
  const commandResults = buildCommandResults(commandQuery, mission, findings);

  useEffect(() => {
    let isMounted = true;
    restoreSession().then((restored) => {
      if (isMounted && restored) {
        setMission((current) => ({ ...current, ...restored }));
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (mission.token) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(mission));
    }
  }, [mission]);

  useEffect(() => {
    if (mission.settings) {
      setSettingsDraft({
        timezone: mission.settings.timezone,
        notifications_enabled: mission.settings.notifications_enabled
      });
    }
  }, [mission.settings]);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      if (!cancelled) {
        await refreshMission({ quiet: true });
      }
    }
    tick();
    const interval = window.setInterval(tick, token ? 7000 : 12000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [token, mission.scan?.id, mission.workspace?.id]);

  useEffect(() => {
    function onHashChange() {
      setScreen(screenFromHash());
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function navigate(nextScreen: Screen) {
    setScreen(nextScreen);
    window.history.replaceState(null, "", `#${nextScreen}`);
  }

  function runCommand(result: CommandResult) {
    if (result.id.startsWith("finding:")) {
      setSelectedFindingId(result.id.replace("finding:", ""));
    }
    if (result.id.startsWith("evidence:")) {
      setSelectedEvidenceId(result.id.replace("evidence:", ""));
    }
    navigate(result.screen);
    setCommandQuery("");
  }

  async function restoreSession(): Promise<Partial<MissionState> | null> {
    if (!mission.token) {
      try {
        return { health: await api.healthComponents() };
      } catch {
        return null;
      }
    }
    try {
      const [me, health] = await Promise.all([api.me(mission.token), api.healthComponents()]);
      return { user: me.user, settings: me.settings, health };
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      setToast({ tone: "warning", message: "Saved session expired. Sign in again." });
      return { ...initialMission, health: await api.healthComponents().catch(() => defaultHealth) };
    }
  }

  async function refreshMission({ quiet = false }: { quiet?: boolean } = {}) {
    try {
      const nextHealth = await api.healthComponents();
      if (!token) {
        setMission((current) => ({ ...current, health: nextHealth }));
        return;
      }
      const updates: Partial<MissionState> = { health: nextHealth };
      if (mission.workspace) {
        const [credits, ledger] = await Promise.all([
          api.credits(token, mission.workspace.id),
          api.ledger(token, mission.workspace.id)
        ]);
        updates.credits = credits.credits;
        updates.ledger = ledger.entries;
      }
      if (mission.scan) {
        const [events, approvals, findings, evidence] = await Promise.all([
          api.events(token, mission.scan.id),
          api.approvals(token, mission.scan.id),
          api.findings(token, mission.scan.id),
          api.evidence(token, mission.scan.id)
        ]);
        updates.events = events.events;
        updates.approvals = approvals.approvals;
        updates.approval = approvals.approvals.find((approval) => approval.status === "pending") ?? mission.approval;
        updates.findings = findings.findings;
        updates.evidence = evidence.evidence;
      }
      setMission((current) => ({ ...current, ...updates }));
    } catch (error) {
      if (!quiet) setToast({ tone: "danger", message: readableError(error) });
    }
  }

  async function startGoogleLogin() {
    setIsBusy(true);
    try {
      const response = await api.googleLogin();
      window.location.assign(response.authorization_url);
    } catch (error) {
      setToast({ tone: "danger", message: readableError(error) });
    } finally {
      setIsBusy(false);
    }
  }

  async function startSsoLogin() {
    setIsBusy(true);
    try {
      const response = await api.ssoLogin();
      window.location.assign(response.authorization_url);
    } catch (error) {
      setToast({ tone: "danger", message: readableError(error) });
    } finally {
      setIsBusy(false);
    }
  }

  async function bootstrapDemo() {
    setIsBusy(true);
    try {
      const nextMission = await bootstrapDemoWorkspace(api);
      setMission(nextMission);
      navigate("new-scan");
      setToast({ tone: "success", message: "Demo workspace created with credits, target, and model profile." });
    } catch (error) {
      setToast({ tone: "danger", message: readableError(error) });
    } finally {
      setIsBusy(false);
    }
  }

  async function createAndStartScan() {
    if (!token || !mission.workspace || !mission.project || !mission.target || !mission.profile) {
      setToast({ tone: "warning", message: "Sign in or bootstrap a workspace before creating a scan." });
      return;
    }
    setIsBusy(true);
    try {
      const target =
        scanDraft.targetUrl && scanDraft.targetUrl !== mission.target.url
          ? (await api.createTarget(token, mission.workspace.id, mission.project.id, scanDraft.targetUrl, "Operator Target")).target
          : mission.target;
      const created = await api.createScan(token, {
        workspace_id: mission.workspace.id,
        project_id: mission.project.id,
        target_id: target.id,
        scan_type: scanDraft.scanType,
        model_profile_id: mission.profile.id,
        instructions: scanDraft.instructions
      });
      const started =
        scanDraft.scanType === "autonomous_blackbox"
          ? await api.startAutonomous(token, created.scan.id)
          : { scan: created.scan };
      const browserPlan =
        scanDraft.scanType === "autonomous_blackbox"
          ? (await api.browserPlan(token, created.scan.id)).browser_plan
          : undefined;
      const approval =
        scanDraft.scanType === "autonomous_blackbox"
          ? (await api.requestUploadApproval(token, created.scan.id)).approval
          : undefined;
      const [events, findings, evidence, ledger, health] = await Promise.all([
        api.events(token, created.scan.id),
        api.findings(token, created.scan.id),
        api.evidence(token, created.scan.id),
        api.ledger(token, mission.workspace.id),
        api.healthComponents()
      ]);
      setMission((current) => ({
        ...current,
        target,
        scan: started.scan,
        credits: created.credits,
        browserPlan,
        approval,
        approvals: approval ? [approval] : [],
        events: events.events,
        findings: findings.findings,
        evidence: evidence.evidence,
        ledger: ledger.entries,
        health
      }));
      navigate("mission");
      setToast({ tone: "success", message: "Scan created. One credit is reserved until completion." });
    } catch (error) {
      setToast({ tone: "danger", message: readableError(error) });
    } finally {
      setIsBusy(false);
    }
  }

  async function resolveApproval(approval: Approval, decision: "approve" | "reject") {
    if (!token) return;
    setIsBusy(true);
    try {
      const response =
        decision === "approve"
          ? await api.approve(token, approval.id, "Approved after reviewing scope and expected evidence.")
          : await api.reject(token, approval.id, "Rejected because the operator requested replanning.");
      const scanId = approval.scan_id;
      const [approvals, events] = await Promise.all([api.approvals(token, scanId), api.events(token, scanId)]);
      setMission((current) => ({
        ...current,
        approval: response.approval,
        approvals: approvals.approvals,
        events: events.events
      }));
      setToast({ tone: decision === "approve" ? "success" : "warning", message: `Approval ${decision}d.` });
    } catch (error) {
      setToast({ tone: "danger", message: readableError(error) });
    } finally {
      setIsBusy(false);
    }
  }

  async function completeScan() {
    if (!token || !mission.scan || !mission.workspace) return;
    setIsBusy(true);
    try {
      const completed = await api.completeScan(token, mission.scan.id);
      const [events, findings, evidence, ledger] = await Promise.all([
        api.events(token, mission.scan.id),
        api.findings(token, mission.scan.id),
        api.evidence(token, mission.scan.id),
        api.ledger(token, mission.workspace.id)
      ]);
      setMission((current) => ({
        ...current,
        scan: completed.scan,
        credits: completed.credits,
        events: events.events,
        findings: findings.findings,
        evidence: evidence.evidence,
        ledger: ledger.entries
      }));
      setToast({ tone: "success", message: "Scan completed and one credit was deducted." });
    } catch (error) {
      setToast({ tone: "danger", message: readableError(error) });
    } finally {
      setIsBusy(false);
    }
  }

  async function saveSettings() {
    if (!token) {
      setToast({ tone: "warning", message: "Sign in before updating settings." });
      return;
    }
    setIsBusy(true);
    try {
      const updated = await api.updateSettings(token, settingsDraft);
      setMission((current) => ({ ...current, settings: updated.settings }));
      setToast({ tone: "success", message: "Settings updated." });
    } catch (error) {
      setToast({ tone: "danger", message: readableError(error) });
    } finally {
      setIsBusy(false);
    }
  }

  async function generateReport() {
    if (!token || !mission.scan) return;
    setIsBusy(true);
    try {
      const response = await api.createReport(token, mission.scan.id);
      setReport(response.report);
      setToast({ tone: "success", message: "Report generated from current scan evidence." });
    } catch (error) {
      setToast({ tone: "danger", message: readableError(error) });
    } finally {
      setIsBusy(false);
    }
  }

  async function copyEvidenceReference(evidence: EvidenceArtifact) {
    const reference = evidenceReference(evidence);
    try {
      await navigator.clipboard.writeText(reference);
      setToast({ tone: "success", message: "Evidence reference copied." });
    } catch {
      setToast({ tone: "warning", message: reference });
    }
  }

  return (
    <main className="app-shell">
      <LoginHero
        isBusy={isBusy}
        user={mission.user}
        onGoogle={startGoogleLogin}
        onSso={startSsoLogin}
        onDemo={bootstrapDemo}
      />

      <section className="workspace-shell" aria-label="KerisLab workspace">
        <Topbar
          mission={mission}
          health={health}
          query={commandQuery}
          results={commandResults}
          onQueryChange={setCommandQuery}
          onRunCommand={runCommand}
        />
        <div className="workspace-grid">
          <SideNav active={screen} onNavigate={navigate} pendingApprovals={mission.approvals.length} />
          <section className="workspace-content">
            {screen === "dashboard" ? (
              <Dashboard
                mission={mission}
                health={health}
                findings={findings}
                onNavigate={navigate}
                onBootstrap={bootstrapDemo}
                isBusy={isBusy}
              />
            ) : null}
            {screen === "new-scan" ? (
              <NewScan
                draft={scanDraft}
                onDraftChange={setScanDraft}
                credits={mission.credits}
                hasWorkspace={Boolean(mission.workspace && mission.profile && mission.target)}
                isBusy={isBusy}
                onStart={createAndStartScan}
              />
            ) : null}
            {screen === "mission" ? (
              <MissionControl
                mission={mission}
                pendingApproval={pendingApproval}
                selectedEvidence={selectedEvidence}
                onSelectEvidence={setSelectedEvidenceId}
                onResolveApproval={resolveApproval}
                onComplete={completeScan}
                onCopyEvidence={copyEvidenceReference}
                isBusy={isBusy}
              />
            ) : null}
            {screen === "findings" ? (
              <FindingsWorkspace
                findings={findings}
                selectedFinding={selectedFinding}
                onSelectFinding={setSelectedFindingId}
                filters={findingFilters}
                onFiltersChange={setFindingFilters}
              />
            ) : null}
            {screen === "targets" ? <TargetsWorkspace mission={mission} /> : null}
            {screen === "reports" ? (
              <ReportsWorkspace
                mission={mission}
                report={report}
                isBusy={isBusy}
                onGenerate={generateReport}
                downloadUrl={report ? api.reportDownloadUrl(report.id) : undefined}
              />
            ) : null}
            {screen === "settings" ? (
              <SettingsWorkspace
                mission={mission}
                health={health}
                draft={settingsDraft}
                isBusy={isBusy}
                onDraftChange={setSettingsDraft}
                onSave={saveSettings}
              />
            ) : null}
          </section>
        </div>
      </section>

      {toast ? (
        <div className={`toast ${toast.tone}`} role="status">
          <span>{toast.message}</span>
          <button type="button" onClick={() => setToast(null)} aria-label="Dismiss notification">
            Dismiss
          </button>
        </div>
      ) : null}
    </main>
  );
}

function LoginHero({
  isBusy,
  user,
  onGoogle,
  onSso,
  onDemo
}: {
  isBusy: boolean;
  user?: { display_name: string; email: string };
  onGoogle: () => void;
  onSso: () => void;
  onDemo: () => void;
}) {
  return (
    <section className="login-screen" aria-label="Sign in">
      <div className="brand-lockup">
        <img src={asset("brand/kerislab-wordmark.svg")} alt="KerisLab" />
        <p>Guarded autonomous security testing for teams that need speed without losing control.</p>
      </div>
      <div className="signin-card">
        <p className="eyebrow">Identity first</p>
        <h1>{user ? `Welcome, ${user.display_name}.` : "Sign in to Mission Control."}</h1>
        <p className="muted">
          Google and enterprise SSO are the primary entry points. Local demo mode is available for development only.
        </p>
        <div className="button-row">
          <button type="button" onClick={onGoogle} disabled={isBusy}>
            Continue with Google
          </button>
          <button type="button" className="secondary" onClick={onSso} disabled={isBusy}>
            Continue with SSO
          </button>
          <button type="button" className="ghost" onClick={onDemo} disabled={isBusy}>
            Bootstrap local demo
          </button>
        </div>
        <div className="signin-note">
          <span>Domain-gated access</span>
          <span>Bearer sessions</span>
          <span>Workspace roles</span>
        </div>
      </div>
    </section>
  );
}

function Topbar({
  mission,
  health,
  query,
  results,
  onQueryChange,
  onRunCommand
}: {
  mission: MissionState;
  health: HealthComponents;
  query: string;
  results: CommandResult[];
  onQueryChange: (query: string) => void;
  onRunCommand: (result: CommandResult) => void;
}) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <img src={asset("brand/kerislab-mark.svg")} alt="" />
        <strong>KerisLab</strong>
      </div>
      <label className="command-search">
        <span className="sr-only">Search</span>
        <input
          placeholder="Search scans, findings, targets, evidence..."
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
        />
        {query.trim() ? (
          <div className="command-menu" role="listbox" aria-label="Search results">
            {results.length ? (
              results.map((result) => (
                <button type="button" key={result.id} onClick={() => onRunCommand(result)}>
                  <strong>{result.label}</strong>
                  <span>{result.detail}</span>
                </button>
              ))
            ) : (
              <div className="command-empty">No matching scans, findings, targets, or evidence.</div>
            )}
          </div>
        ) : null}
      </label>
      <div className="topbar-meta">
        <StatusPill tone={health.status === "ok" ? "good" : "warn"} label={`Workers ${health.worker_heartbeat.active}`} />
        <StatusPill tone="info" label={mission.profile?.model ?? "No model profile"} />
        <StatusPill
          tone={(mission.credits?.available ?? 0) > 0 ? "good" : "warn"}
          label={`${mission.credits?.available ?? 0} credits`}
        />
        <span className="avatar" aria-label={mission.user?.email ?? "Not signed in"}>
          {mission.user?.display_name?.slice(0, 1) ?? "K"}
        </span>
      </div>
    </header>
  );
}

function SideNav({
  active,
  onNavigate,
  pendingApprovals
}: {
  active: Screen;
  onNavigate: (screen: Screen) => void;
  pendingApprovals: number;
}) {
  const items: Array<{ id: Screen; label: string; detail: string }> = [
    { id: "dashboard", label: "Dashboard", detail: "Operations overview" },
    { id: "new-scan", label: "New Scan", detail: "Scope, policy, credits" },
    { id: "mission", label: "Mission Control", detail: `${pendingApprovals} approvals` },
    { id: "findings", label: "Findings", detail: "Triage queue" },
    { id: "targets", label: "Targets", detail: "Assets and scope" },
    { id: "reports", label: "Reports", detail: "Exports and evidence" },
    { id: "settings", label: "Settings", detail: "Identity and runtime" }
  ];
  return (
    <nav className="side-nav" aria-label="Primary navigation">
      {items.map((item) => (
        <button
          type="button"
          key={item.id}
          className={active === item.id ? "active" : ""}
          onClick={() => onNavigate(item.id)}
          aria-current={active === item.id ? "page" : undefined}
        >
          <strong>{item.label}</strong>
          <span>{item.detail}</span>
        </button>
      ))}
    </nav>
  );
}

function Dashboard({
  mission,
  health,
  findings,
  onNavigate,
  onBootstrap,
  isBusy
}: {
  mission: MissionState;
  health: HealthComponents;
  findings: Finding[];
  onNavigate: (screen: Screen) => void;
  onBootstrap: () => void;
  isBusy: boolean;
}) {
  return (
    <div className="screen-stack">
      <PageHeader
        eyebrow="Workspace dashboard"
        title="Security operations, credits, runtime, and approvals in one place."
        description="Start from the health of the platform, then move into scans, findings, approvals, and evidence."
        action={
          <div className="button-row compact">
            <button type="button" onClick={() => onNavigate("new-scan")}>
              New scan
            </button>
            <button type="button" className="secondary" onClick={onBootstrap} disabled={isBusy}>
              Bootstrap demo
            </button>
          </div>
        }
      />
      <div className="metric-grid">
        <Metric label="Available credits" value={String(mission.credits?.available ?? 0)} detail="Reserved on scan start" />
        <Metric label="Active workers" value={String(health.worker_heartbeat.active)} detail={health.worker_heartbeat.status} />
        <Metric label="Queue depth" value={String(health.queue.queued + health.queue.running)} detail="Queued and running jobs" />
        <Metric label="Open findings" value={String(findings.length)} detail="Across current workspace" />
      </div>
      <div className="dashboard-grid">
        <Panel title="Active Scan">
          <ScanSummary mission={mission} />
        </Panel>
        <Panel title="Pending Approvals">
          {mission.approvals.length ? (
            mission.approvals.map((approval) => <ApprovalCard key={approval.id} approval={approval} compact />)
          ) : (
            <EmptyState title="No pending approvals" body="Approval requests appear here when an autonomous agent reaches a gated action." />
          )}
        </Panel>
        <Panel title="Recent Findings">
          <FindingTable findings={findings.slice(0, 4)} compact />
        </Panel>
        <Panel title="Runtime Health">
          <HealthList health={health} />
        </Panel>
      </div>
    </div>
  );
}

function NewScan({
  draft,
  credits,
  hasWorkspace,
  isBusy,
  onDraftChange,
  onStart
}: {
  draft: { targetUrl: string; scanType: ScanType; intensity: string; maxRuntime: string; maxSpend: string; instructions: string };
  credits?: { available: number; reserved: number; consumed: number };
  hasWorkspace: boolean;
  isBusy: boolean;
  onDraftChange: (draft: {
    targetUrl: string;
    scanType: ScanType;
    intensity: string;
    maxRuntime: string;
    maxSpend: string;
    instructions: string;
  }) => void;
  onStart: () => void;
}) {
  const hasCredits = (credits?.available ?? 0) > 0;
  return (
    <div className="screen-stack">
      <PageHeader
        eyebrow="New scan"
        title="Define scope, autonomy, spend, and approval policy before launch."
        description="KerisLab reserves one credit when the scan starts and deducts it only after successful completion."
      />
      <div className="scan-wizard">
        <Panel title="Scope">
          <label className="field">
            <span>Target URL</span>
            <input
              value={draft.targetUrl}
              onChange={(event) => onDraftChange({ ...draft, targetUrl: event.target.value })}
            />
          </label>
          <div className="segmented" role="group" aria-label="Scan type">
            {[
              ["passive_blackbox", "Passive"],
              ["autonomous_blackbox", "Autonomous"],
              ["active_blackbox", "Active"],
              ["whitebox", "Whitebox"],
              ["hybrid", "Hybrid"]
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={draft.scanType === id ? "active" : ""}
                onClick={() => onDraftChange({ ...draft, scanType: id as ScanType })}
              >
                {label}
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="Policy and Budget">
          <div className="form-grid">
            <label className="field">
              <span>Intensity</span>
              <select value={draft.intensity} onChange={(event) => onDraftChange({ ...draft, intensity: event.target.value })}>
                <option>Guarded</option>
                <option>Conservative</option>
                <option>Expanded</option>
              </select>
            </label>
            <label className="field">
              <span>Max runtime</span>
              <input value={draft.maxRuntime} onChange={(event) => onDraftChange({ ...draft, maxRuntime: event.target.value })} />
            </label>
            <label className="field">
              <span>Max model spend</span>
              <input value={draft.maxSpend} onChange={(event) => onDraftChange({ ...draft, maxSpend: event.target.value })} />
            </label>
            <div className="credit-box">
              <span>Required credits</span>
              <strong>1</strong>
              <small>{credits ? `${credits.available} available / ${credits.reserved} reserved` : "No workspace loaded"}</small>
            </div>
          </div>
          <label className="field">
            <span>Operator instructions</span>
            <textarea value={draft.instructions} onChange={(event) => onDraftChange({ ...draft, instructions: event.target.value })} />
          </label>
        </Panel>
        <Panel title="Guarded Autonomy Preview">
          <PolicyList />
          <button type="button" onClick={onStart} disabled={!hasWorkspace || !hasCredits || isBusy}>
            {isBusy ? "Starting scan..." : "Reserve credit and start scan"}
          </button>
          {!hasWorkspace ? <p className="form-warning">Bootstrap or sign into a workspace before launching scans.</p> : null}
          {hasWorkspace && !hasCredits ? <p className="form-warning">No available credits. Add credits before starting.</p> : null}
        </Panel>
      </div>
    </div>
  );
}

function MissionControl({
  mission,
  pendingApproval,
  selectedEvidence,
  isBusy,
  onSelectEvidence,
  onResolveApproval,
  onComplete,
  onCopyEvidence
}: {
  mission: MissionState;
  pendingApproval?: Approval;
  selectedEvidence?: EvidenceArtifact;
  isBusy: boolean;
  onSelectEvidence: (id: string) => void;
  onResolveApproval: (approval: Approval, decision: "approve" | "reject") => void;
  onComplete: () => void;
  onCopyEvidence: (evidence: EvidenceArtifact) => void;
}) {
  const phases = ["Scope", "Recon", "Crawl", "Plan", "Test", "Verify", "Report"];
  return (
    <div className="screen-stack mission-screen">
      <div className="mission-strip">
        <div>
          <p className="eyebrow">Mission Control</p>
          <h2>{mission.target?.url ?? "No active target"}</h2>
        </div>
        <StatusPill tone={mission.scan?.status === "completed" ? "good" : "warn"} label={formatStatus(mission.scan?.status ?? "not_started")} />
        <StatusPill tone="info" label={`${mission.credits?.reserved ?? 0} credits reserved`} />
        <button type="button" className="secondary" onClick={onComplete} disabled={!mission.scan || isBusy}>
          Complete scan
        </button>
      </div>
      <div className="mission-layout">
        <Panel title="Plan Timeline" className="phase-panel">
          <div className="phase-rail">
            {phases.map((phase, index) => (
              <div key={phase} className={mission.events.length > index ? "done" : index === mission.events.length ? "active" : ""}>
                <strong>{phase}</strong>
                <span>{index === mission.events.length ? "Current" : mission.events.length > index ? "Complete" : "Pending"}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Browser and Evidence" className="browser-panel">
          <div className="browser-frame">
            <div className="browser-chrome">
              <span />
              <span />
              <span />
              <strong>{mission.browserPlan?.target_url ?? "about:blank"}</strong>
            </div>
            <img src={asset("illustrations/mission-control-panel.svg")} alt="Browser evidence preview" />
          </div>
          <div className="tool-drawer">
            <strong>{selectedEvidence?.summary ?? "No evidence selected"}</strong>
            <span>{selectedEvidence?.metadata?.object_uri ? String(selectedEvidence.metadata.object_uri) : "Evidence artifacts appear here after browser execution."}</span>
            {selectedEvidence ? (
              <div className="button-row compact">
                <button type="button" className="secondary" onClick={() => onCopyEvidence(selectedEvidence)}>
                  Copy reference
                </button>
                <a className="link-button" href={evidenceReference(selectedEvidence)} target="_blank" rel="noreferrer">
                  Open artifact
                </a>
              </div>
            ) : null}
          </div>
        </Panel>
        <Panel title="Approvals and Risk" className="approval-panel">
          {pendingApproval ? (
            <ApprovalCard approval={pendingApproval} onResolve={onResolveApproval} isBusy={isBusy} />
          ) : (
            <EmptyState title="No gated action pending" body="The agent will pause here when it needs approval for risky actions." />
          )}
        </Panel>
      </div>
      <div className="mission-lower">
        <Panel title="Event Stream">
          <EventStream events={mission.events} />
        </Panel>
        <Panel title="Evidence">
          <EvidenceList evidence={mission.evidence} selectedId={selectedEvidence?.id} onSelect={onSelectEvidence} />
        </Panel>
        <Panel title="Agent Plan">
          <ActionList actions={mission.browserPlan?.actions ?? []} />
        </Panel>
      </div>
    </div>
  );
}

function FindingsWorkspace({
  findings,
  selectedFinding,
  onSelectFinding,
  filters,
  onFiltersChange
}: {
  findings: Finding[];
  selectedFinding?: Finding;
  onSelectFinding: (id: string) => void;
  filters: FindingFilters;
  onFiltersChange: (filters: FindingFilters) => void;
}) {
  const filteredFindings = filterFindings(findings, filters);
  const severityCounts = countBy(findings, (finding) => finding.severity);
  return (
    <div className="screen-stack">
      <PageHeader
        eyebrow="Findings"
        title="Triage, verify, assign, and export security evidence."
        description="Dense tables and detail drawers keep security leads fast without hiding the proof."
      />
      <div className="findings-layout">
        <Panel title="Finding Queue">
          <div className="filter-bar">
            <label>
              <span className="sr-only">Search findings</span>
              <input
                value={filters.query}
                placeholder="Search title, asset, evidence..."
                onChange={(event) => onFiltersChange({ ...filters, query: event.target.value })}
              />
            </label>
            <select value={filters.severity} onChange={(event) => onFiltersChange({ ...filters, severity: event.target.value })}>
              <option value="all">All severities</option>
              <option value="critical">Critical ({severityCounts.critical ?? 0})</option>
              <option value="high">High ({severityCounts.high ?? 0})</option>
              <option value="medium">Medium ({severityCounts.medium ?? 0})</option>
              <option value="low">Low ({severityCounts.low ?? 0})</option>
              <option value="info">Info ({severityCounts.info ?? 0})</option>
            </select>
            <select value={filters.status} onChange={(event) => onFiltersChange({ ...filters, status: event.target.value })}>
              <option value="all">All statuses</option>
              <option value="new">New</option>
              <option value="triaged">Triaged</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
          <FindingTable findings={filteredFindings} onSelect={onSelectFinding} selectedId={selectedFinding?.id} />
        </Panel>
        <Panel title="Finding Detail" className="detail-panel">
          {selectedFinding ? (
            <div className="finding-detail">
              <Severity severity={selectedFinding.severity} />
              <h3>{selectedFinding.title}</h3>
              <dl className="details">
                <div>
                  <dt>Affected asset</dt>
                  <dd>{selectedFinding.affected_asset}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{formatStatus(selectedFinding.status)}</dd>
                </div>
                <div>
                  <dt>Verification</dt>
                  <dd>{formatStatus(selectedFinding.verification_status)}</dd>
                </div>
                <div>
                  <dt>Evidence</dt>
                  <dd>{selectedFinding.evidence_refs.join(", ")}</dd>
                </div>
              </dl>
              <div className="remediation">
                <strong>Remediation draft</strong>
                <p>Confirm exploitability, capture reproduction evidence, assign an owner, and export the finding into the final report.</p>
              </div>
            </div>
          ) : (
            <EmptyState title="Select a finding" body="Finding details, evidence, and remediation steps will appear here." />
          )}
        </Panel>
      </div>
    </div>
  );
}

function TargetsWorkspace({ mission }: { mission: MissionState }) {
  return (
    <div className="screen-stack">
      <PageHeader eyebrow="Targets" title="Scope control for every assessment." description="Keep target ownership, includes, excludes, and private-network policy explicit." />
      <Panel title="Scoped Assets">
        {mission.target ? (
          <div className="target-card">
            <strong>{mission.target.name}</strong>
            <span>{mission.target.url}</span>
            <small>Workspace: {mission.workspace?.name ?? mission.target.workspace_id}</small>
          </div>
        ) : (
          <EmptyState title="No target loaded" body="Create or bootstrap a workspace to add scoped targets." />
        )}
      </Panel>
    </div>
  );
}

function ReportsWorkspace({
  mission,
  report,
  isBusy,
  onGenerate,
  downloadUrl
}: {
  mission: MissionState;
  report: Report | null;
  isBusy: boolean;
  onGenerate: () => void;
  downloadUrl?: string;
}) {
  return (
    <div className="screen-stack">
      <PageHeader eyebrow="Reports" title="Evidence-backed reporting." description="Reports should export scan state, verified findings, and evidence references." />
      <Panel title="Report Builder">
        <div className="report-card">
          <strong>{mission.scan ? `KerisLab report for ${mission.scan.id}` : "No scan selected"}</strong>
          <span>{mission.findings.length} findings, {mission.evidence.length} evidence artifacts, {mission.events.length} timeline events</span>
          <button type="button" disabled={!mission.scan || isBusy} onClick={onGenerate}>
            {isBusy ? "Generating..." : "Generate report"}
          </button>
          {report ? (
            <div className="report-output">
              <strong>{report.title}</strong>
              <span>Format: {report.format}</span>
              <span>Report ID: {report.id}</span>
              {downloadUrl ? (
                <a className="link-button" href={downloadUrl} target="_blank" rel="noreferrer">
                  Download JSON report
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      </Panel>
    </div>
  );
}

function SettingsWorkspace({
  mission,
  health,
  draft,
  isBusy,
  onDraftChange,
  onSave
}: {
  mission: MissionState;
  health: HealthComponents;
  draft: { timezone: string; notifications_enabled: boolean };
  isBusy: boolean;
  onDraftChange: (draft: { timezone: string; notifications_enabled: boolean }) => void;
  onSave: () => void;
}) {
  return (
    <div className="screen-stack">
      <PageHeader eyebrow="Settings" title="Identity, credits, model routing, and runtime controls." description="Operational settings are grouped by account, workspace, and platform runtime." />
      <div className="settings-grid">
        <Panel title="Profile">
          <div className="settings-form">
            <Details
              rows={[
                ["User", mission.user?.display_name ?? "Not signed in"],
                ["Email", mission.user?.email ?? "Not signed in"]
              ]}
            />
            <label className="field">
              <span>Timezone</span>
              <input value={draft.timezone} onChange={(event) => onDraftChange({ ...draft, timezone: event.target.value })} />
            </label>
            <label className="check-field">
              <input
                type="checkbox"
                checked={draft.notifications_enabled}
                onChange={(event) => onDraftChange({ ...draft, notifications_enabled: event.target.checked })}
              />
              <span>Enable operational notifications</span>
            </label>
            <button type="button" onClick={onSave} disabled={isBusy || !mission.token}>
              Save profile settings
            </button>
          </div>
        </Panel>
        <Panel title="Workspace and Credits">
          <Details
            rows={[
              ["Workspace", mission.workspace?.name ?? "No workspace"],
              ["Available", String(mission.credits?.available ?? 0)],
              ["Reserved", String(mission.credits?.reserved ?? 0)],
              ["Consumed", String(mission.credits?.consumed ?? 0)]
            ]}
          />
        </Panel>
        <Panel title="SSO and Access">
          <Details rows={[["Google OAuth", "Primary"], ["Enterprise SSO", "Configured by workspace"], ["Roles", "Owner, Admin, Security Lead, Pentester"], ["Sessions", "Bearer token sessions"]]} />
        </Panel>
        <Panel title="Runtime">
          <Details
            rows={[
              ["Worker heartbeat", health.worker_heartbeat.status],
              ["Queue", `${health.queue.queued} queued / ${health.queue.running} running`],
              ["Model profile", mission.profile?.model ?? "No model"],
              ["Evidence storage", "MinIO via S3-compatible object storage"]
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}

function PageHeader({
  eyebrow,
  title,
  description,
  action
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}

function Panel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function ScanSummary({ mission }: { mission: MissionState }) {
  if (!mission.scan) {
    return <EmptyState title="No active scan" body="Create a new scan to start guarded autonomous testing." />;
  }
  return (
    <div className="scan-summary">
      <div>
        <strong>{formatStatus(mission.scan.scan_type)}</strong>
        <span>{mission.target?.url ?? mission.scan.target_id}</span>
      </div>
      <StatusPill tone={mission.scan.status === "completed" ? "good" : "warn"} label={formatStatus(mission.scan.status)} />
      <p>{mission.events.at(-1)?.summary ?? mission.scan.instructions}</p>
    </div>
  );
}

function ApprovalCard({
  approval,
  compact = false,
  isBusy,
  onResolve
}: {
  approval: Approval;
  compact?: boolean;
  isBusy?: boolean;
  onResolve?: (approval: Approval, decision: "approve" | "reject") => void;
}) {
  return (
    <article className={`approval-card ${compact ? "compact" : ""}`}>
      <StatusPill tone={approval.status === "pending" ? "warn" : "info"} label={formatStatus(approval.status)} />
      <h4>{formatStatus(approval.risk_category)}</h4>
      <p>{approval.proposed_action}</p>
      {!compact ? (
        <dl className="approval-facts">
          <div>
            <dt>Target</dt>
            <dd>{approval.target}</dd>
          </div>
          <div>
            <dt>Tool</dt>
            <dd>{approval.proposed_tool}</dd>
          </div>
          <div>
            <dt>Policy reason</dt>
            <dd>{approval.policy_reason}</dd>
          </div>
          <div>
            <dt>Expected evidence</dt>
            <dd>{approval.expected_evidence}</dd>
          </div>
        </dl>
      ) : null}
      {onResolve && approval.status === "pending" ? (
        <div className="button-row compact">
          <button type="button" onClick={() => onResolve(approval, "approve")} disabled={isBusy}>
            Approve
          </button>
          <button type="button" className="secondary" onClick={() => onResolve(approval, "reject")} disabled={isBusy}>
            Reject
          </button>
        </div>
      ) : null}
    </article>
  );
}

function FindingTable({
  findings,
  compact = false,
  onSelect,
  selectedId
}: {
  findings: Finding[];
  compact?: boolean;
  onSelect?: (id: string) => void;
  selectedId?: string;
}) {
  if (!findings.length) return <EmptyState title="No matching findings" body="Adjust filters or wait for the current scan to produce verified results." />;
  return (
    <div className="data-table" role="table" aria-label="Findings">
      <div className="table-row table-head" role="row">
        <span>Severity</span>
        <span>Finding</span>
        {!compact ? <span>Asset</span> : null}
        <span>Status</span>
      </div>
      {findings.map((finding) => (
        <button
          key={finding.id}
          type="button"
          className={`table-row ${selectedId === finding.id ? "selected" : ""}`}
          onClick={() => onSelect?.(finding.id)}
          role="row"
        >
          <span>
            <Severity severity={finding.severity} />
          </span>
          <strong>{finding.title}</strong>
          {!compact ? <span>{finding.affected_asset}</span> : null}
          <span>{formatStatus(finding.status)}</span>
        </button>
      ))}
    </div>
  );
}

function HealthList({ health }: { health: HealthComponents }) {
  return (
    <div className="health-list">
      <HealthItem label="API" status="ok" detail="Responding" />
      <HealthItem label="Worker" status={health.worker_heartbeat.status} detail={`${health.worker_heartbeat.active} active`} />
      <HealthItem label="Queue" status={health.queue.failed ? "degraded" : "ok"} detail={`${health.queue.queued} queued`} />
      <HealthItem label="Evidence" status="ok" detail="MinIO configured" />
    </div>
  );
}

function HealthItem({ label, status, detail }: { label: string; status: string; detail: string }) {
  return (
    <div className="health-item">
      <span className={`dot ${status === "ok" ? "good" : "warn"}`} />
      <strong>{label}</strong>
      <small>{detail}</small>
    </div>
  );
}

function EventStream({ events }: { events: ScanEvent[] }) {
  if (!events.length) return <EmptyState title="No events yet" body="Scan events stream here when the agent starts working." />;
  return (
    <div className="event-stream">
      {events.slice(-8).map((event) => (
        <article key={event.id}>
          <strong>{event.type}</strong>
          <span>{event.summary}</span>
        </article>
      ))}
    </div>
  );
}

function EvidenceList({
  evidence,
  selectedId,
  onSelect
}: {
  evidence: EvidenceArtifact[];
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  if (!evidence.length) return <EmptyState title="No evidence yet" body="Screenshots, DOM snapshots, transcripts, and scanner artifacts appear here." />;
  return (
    <div className="evidence-list">
      {evidence.map((artifact) => (
        <button type="button" key={artifact.id} className={selectedId === artifact.id ? "selected" : ""} onClick={() => onSelect(artifact.id)}>
          <strong>{artifact.summary}</strong>
          <span>{artifact.artifact_type}</span>
        </button>
      ))}
    </div>
  );
}

function ActionList({ actions }: { actions: BrowserAction[] }) {
  if (!actions.length) return <EmptyState title="No browser plan" body="The browser plan appears after an autonomous scan starts." />;
  return (
    <div className="action-list">
      {actions.map((action) => (
        <article key={action.id}>
          <StatusPill tone={action.requires_approval ? "warn" : "good"} label={action.requires_approval ? "Approval" : "Safe"} />
          <strong>{formatStatus(action.action_type)}</strong>
          <span>{action.description}</span>
        </article>
      ))}
    </div>
  );
}

function PolicyList() {
  return (
    <ul className="policy-list">
      <li>Only scoped targets are allowed.</li>
      <li>State-changing browser actions require approval.</li>
      <li>Every scan reserves one workspace credit.</li>
      <li>Evidence is persisted with replayable references.</li>
      <li>Failed or cancelled scans release reserved credits.</li>
    </ul>
  );
}

function Details({ rows }: { rows: Array<[string, string]> }) {
  return (
    <dl className="details">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function StatusPill({ label, tone }: { label: string; tone: "good" | "warn" | "danger" | "info" }) {
  return <span className={`status-pill ${tone}`}>{label}</span>;
}

function Severity({ severity }: { severity: string }) {
  return <span className={`severity ${severity.toLowerCase()}`}>{formatStatus(severity)}</span>;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

function buildCommandResults(query: string, mission: MissionState, findings: Finding[]): CommandResult[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  const staticResults: CommandResult[] = [
    { id: "nav:dashboard", label: "Dashboard", detail: "Operations overview", screen: "dashboard" },
    { id: "nav:new-scan", label: "New scan", detail: "Create a guarded autonomous scan", screen: "new-scan" },
    { id: "nav:mission", label: "Mission Control", detail: mission.target?.url ?? "Live scan cockpit", screen: "mission" },
    { id: "nav:reports", label: "Reports", detail: "Generate and download evidence-backed reports", screen: "reports" },
    { id: "nav:settings", label: "Settings", detail: "Identity, SSO, credits, and runtime", screen: "settings" }
  ];
  const targetResults: CommandResult[] = mission.target
    ? [{ id: `target:${mission.target.id}`, label: mission.target.name, detail: mission.target.url, screen: "targets" }]
    : [];
  const findingResults = findings.map((finding) => ({
    id: `finding:${finding.id}`,
    label: finding.title,
    detail: `${formatStatus(finding.severity)} · ${finding.affected_asset}`,
    screen: "findings" as Screen
  }));
  const evidenceResults = mission.evidence.map((artifact) => ({
    id: `evidence:${artifact.id}`,
    label: artifact.summary,
    detail: `${formatStatus(artifact.artifact_type)} · ${evidenceReference(artifact)}`,
    screen: "mission" as Screen
  }));

  return [...staticResults, ...targetResults, ...findingResults, ...evidenceResults]
    .filter((result) => `${result.label} ${result.detail}`.toLowerCase().includes(needle))
    .slice(0, 8);
}

function filterFindings(findings: Finding[], filters: FindingFilters) {
  const needle = filters.query.trim().toLowerCase();
  return findings
    .filter((finding) => filters.severity === "all" || finding.severity.toLowerCase() === filters.severity)
    .filter((finding) => filters.status === "all" || finding.status.toLowerCase() === filters.status)
    .filter((finding) => {
      if (!needle) return true;
      return `${finding.title} ${finding.affected_asset} ${finding.evidence_refs.join(" ")}`.toLowerCase().includes(needle);
    })
    .sort((left, right) => severityRank(right.severity) - severityRank(left.severity));
}

function countBy<T>(items: T[], getKey: (item: T) => string) {
  return items.reduce<Record<string, number>>((counts, item) => {
    const key = getKey(item).toLowerCase();
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
}

function severityRank(severity: string) {
  const ranks: Record<string, number> = { info: 0, low: 1, medium: 2, high: 3, critical: 4 };
  return ranks[severity.toLowerCase()] ?? 0;
}

function evidenceReference(evidence: EvidenceArtifact) {
  return String(evidence.metadata?.object_uri ?? evidence.uri);
}

function readableError(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong";
}

function loadStoredMission(): MissionState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return initialMission;
    const parsed = JSON.parse(raw) as MissionState;
    return {
      ...initialMission,
      ...parsed,
      approvals: parsed.approvals ?? [],
      events: parsed.events ?? [],
      findings: parsed.findings ?? [],
      evidence: parsed.evidence ?? [],
      ledger: parsed.ledger ?? []
    };
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return initialMission;
  }
}

function screenFromHash(): Screen {
  const candidate = window.location.hash.replace("#", "");
  const screens: Screen[] = ["dashboard", "new-scan", "mission", "findings", "targets", "reports", "settings"];
  return screens.includes(candidate as Screen) ? (candidate as Screen) : "dashboard";
}

function formatStatus(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
