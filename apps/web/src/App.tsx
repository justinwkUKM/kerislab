import { useState } from "react";
import { Finding, MissionState, ScanEvent, runMvpWorkflow } from "./api";

const asset = (path: string) => new URL(`../../../assets/${path}`, import.meta.url).href;

const fallbackScans = [
  { name: "Autonomous Pentest", target: "https://example.com", status: "Ready", phase: "Waiting for API run" },
  { name: "Passive Blackbox", target: "https://docs.example.com", status: "Queued", phase: "Scope validation" },
  { name: "Whitebox Review", target: "git@example.com/app.git", status: "Planned", phase: "Repository import" }
];

const fallbackFindings: Finding[] = [
  {
    id: "finding-preview-1",
    scan_id: "preview",
    severity: "Info",
    title: "Security header review ready",
    asset: "https://example.com",
    status: "Preview"
  },
  {
    id: "finding-preview-2",
    scan_id: "preview",
    severity: "Medium",
    title: "Session policy checks configured",
    asset: "/login",
    status: "Preview"
  },
  {
    id: "finding-preview-3",
    scan_id: "preview",
    severity: "High",
    title: "Upload endpoint requires gated verification",
    asset: "/api/upload",
    status: "Awaiting approval"
  }
];

export function App() {
  const [mission, setMission] = useState<MissionState>({
    events: [],
    findings: [],
    ledger: []
  });
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const findings = mission.findings.length ? mission.findings : fallbackFindings;
  const scanStatus = mission.scan?.status ?? "not_started";
  const creditLabel = mission.credits
    ? `${mission.credits.available} available / ${mission.credits.reserved} reserved / ${mission.credits.consumed} consumed`
    : "Run workflow to load credits";

  async function runWorkflow() {
    setIsRunning(true);
    setError(null);
    try {
      const nextMission = await runMvpWorkflow();
      setMission(nextMission);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to run KerisLab workflow");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main>
      <section className="login">
        <img className="brand" src={asset("brand/kerislab-wordmark.svg")} alt="KerisLab" />
        <div className="login-panel">
          <p className="eyebrow">Guarded autonomous security testing</p>
          <h1>Sign in to Mission Control.</h1>
          <p className="subtle">Google and enterprise SSO are first-class authentication paths from day one.</p>
          <div className="actions">
            <button onClick={runWorkflow} disabled={isRunning}>
              {isRunning ? "Running MVP flow..." : "Continue with Google"}
            </button>
            <button className="secondary">Continue with SSO</button>
          </div>
          {error ? <p className="error">API workflow failed: {error}</p> : null}
        </div>
      </section>

      <section className="shell">
        <nav className="topbar">
          <img src={asset("brand/kerislab-mark.svg")} alt="" />
          <strong>KerisLab</strong>
          <span>Workspace credits: {creditLabel}</span>
          <span className="pill">{mission.profileTest ?? "LiteLLM: not tested"}</span>
        </nav>

        <div className="grid">
          <aside>
            {["Dashboard", "Scans", "Findings", "Targets", "Reports", "Settings"].map((item) => (
              <a key={item}>{item}</a>
            ))}
          </aside>

          <section className="content">
            <header className="hero">
              <div>
                <p className="eyebrow">Scalable platform MVP</p>
                <h2>Autonomous testing with human approval gates.</h2>
              </div>
              <button onClick={runWorkflow} disabled={isRunning}>
                {isRunning ? "Running..." : "Run MVP Workflow"}
              </button>
            </header>

            <div className="stats">
              <Metric label="Signed-in user" value={mission.user?.display_name ?? "Preview"} />
              <Metric label="Scan status" value={formatStatus(scanStatus)} />
              <Metric label="Credits consumed" value={String(mission.credits?.consumed ?? 0)} />
              <Metric label="Browser actions" value={String(mission.browserPlan?.actions.length ?? 0)} />
            </div>

            <section className="mission">
              <div className="mission-head">
                <div>
                  <p className="eyebrow">Mission Control</p>
                  <h3>{mission.target?.url ?? "example.com"} autonomous pentest</h3>
                </div>
                <span className="status">{formatStatus(mission.approval?.status ?? scanStatus)}</span>
              </div>
              <div className="mission-grid">
                <div className="timeline">
                  {["Scope", "Recon", "Crawl", "Plan", "Test", "Verify", "Report"].map((phase, index) => (
                    <div className={mission.events.length > index ? "done" : ""} key={phase}>
                      {phase}
                    </div>
                  ))}
                </div>
                <div className="viewport">
                  <img src={asset("illustrations/mission-control-panel.svg")} alt="Mission Control illustration" />
                </div>
                <div className="approval">
                  <h4>{mission.approval?.title ?? "Approval request"}</h4>
                  <p>
                    {mission.approval?.requested_action ??
                      "Agent requests gated upload verification against `/api/upload`."}
                  </p>
                  <button onClick={runWorkflow} disabled={isRunning}>
                    Approve via workflow
                  </button>
                  <button className="secondary">Reject</button>
                </div>
              </div>
            </section>

            <section className="columns">
              <div className="panel">
                <h3>Scans</h3>
                {mission.scan ? (
                  <ScanRow
                    name="Autonomous Pentest"
                    target={mission.target?.url ?? mission.scan.target_id}
                    status={formatStatus(mission.scan.status)}
                    phase={mission.events.at(-1)?.summary ?? "Started"}
                  />
                ) : (
                  fallbackScans.map((scan) => <ScanRow key={scan.name} {...scan} />)
                )}
              </div>
              <div className="panel">
                <h3>Findings</h3>
                {findings.map((finding) => (
                  <article className="finding" key={finding.id}>
                    <span className={`severity ${finding.severity.toLowerCase()}`}>{finding.severity}</span>
                    <strong>{finding.title}</strong>
                    <small>
                      {finding.asset} - {finding.status}
                    </small>
                  </article>
                ))}
              </div>
            </section>

            <section className="columns lower">
              <EventPanel events={mission.events} />
              <div className="panel">
                <h3>Profile & Settings</h3>
                <dl className="details">
                  <div>
                    <dt>Workspace</dt>
                    <dd>{mission.workspace?.name ?? "Not created"}</dd>
                  </div>
                  <div>
                    <dt>Model Profile</dt>
                    <dd>{mission.profile?.model ?? "Not configured"}</dd>
                  </div>
                  <div>
                    <dt>Browser Engine</dt>
                    <dd>{mission.browserPlan?.engine ?? "Playwright planned"}</dd>
                  </div>
                  <div>
                    <dt>Timezone</dt>
                    <dd>{mission.settings?.timezone ?? "Asia/Kuala_Lumpur planned"}</dd>
                  </div>
                  <div>
                    <dt>Credit Ledger</dt>
                    <dd>{mission.ledger.length ? `${mission.ledger.length} entries` : "No entries loaded"}</dd>
                  </div>
                </dl>
              </div>
            </section>
          </section>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ScanRow({ name, target, status, phase }: { name: string; target: string; status: string; phase: string }) {
  return (
    <article className="row">
      <img src={asset("icons/autonomous-pentest.svg")} alt="" />
      <div>
        <strong>{name}</strong>
        <span>{target}</span>
        <small>{phase}</small>
      </div>
      <em>{status}</em>
    </article>
  );
}

function EventPanel({ events }: { events: ScanEvent[] }) {
  return (
    <div className="panel">
      <h3>Agent Events</h3>
      {events.length ? (
        events.slice(-6).map((event) => (
          <article className="event" key={event.id}>
            <strong>{event.type}</strong>
            <span>{event.summary}</span>
          </article>
        ))
      ) : (
        <p className="subtle">Run the MVP workflow to stream autonomous scan events from the API.</p>
      )}
    </div>
  );
}

function formatStatus(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
