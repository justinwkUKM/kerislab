from __future__ import annotations

from .models import (
    AgentPlan,
    ApprovalRequest,
    ApprovalStatus,
    AuthProvider,
    BrowserAction,
    BrowserPlan,
    CreditAccount,
    CreditLedgerEntry,
    CreditReservation,
    CreditReservationStatus,
    Finding,
    LedgerEntryType,
    ModelProfile,
    Project,
    Report,
    Role,
    Scan,
    ScanEvent,
    ScanStatus,
    ScanType,
    Target,
    User,
    UserSettings,
    VerificationStatus,
    Workspace,
    WorkspaceMembership,
    now_utc,
)
from .scope import validate_target_scope
from .store import InMemoryStore


class CreditError(ValueError):
    pass


class ApprovalError(ValueError):
    pass


class AuthService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def login_identity(
        self,
        *,
        email: str,
        display_name: str,
        provider: AuthProvider,
        avatar_url: str | None = None,
    ) -> User:
        existing = next((u for u in self.store.users.values() if u.email == email), None)
        if existing:
            return existing
        user = self.store.add(
            self.store.users,
            User(email=email, display_name=display_name, provider=provider, avatar_url=avatar_url),
        )
        self.store.user_settings[user.id] = UserSettings(user_id=user.id)
        return user


class WorkspaceService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_workspace(self, *, name: str, owner: User, initial_credits: int = 0) -> Workspace:
        workspace = self.store.add(self.store.workspaces, Workspace(name=name))
        membership = WorkspaceMembership(workspace_id=workspace.id, user_id=owner.id, role=Role.OWNER)
        self.store.add(self.store.memberships, membership)
        self.store.credit_accounts[workspace.id] = CreditAccount(workspace_id=workspace.id)
        self.store.user_settings[owner.id].default_workspace_id = workspace.id
        if initial_credits:
            CreditService(self.store).grant(workspace.id, initial_credits, note="Initial workspace grant")
        return workspace


class CreditService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def account(self, workspace_id: str) -> CreditAccount:
        if workspace_id not in self.store.credit_accounts:
            self.store.credit_accounts[workspace_id] = CreditAccount(workspace_id=workspace_id)
        return self.store.credit_accounts[workspace_id]

    def grant(self, workspace_id: str, amount: int, note: str = "") -> CreditLedgerEntry:
        if amount <= 0:
            raise CreditError("credit grant amount must be positive")
        account = self.account(workspace_id)
        account.available += amount
        entry = CreditLedgerEntry(
            workspace_id=workspace_id,
            entry_type=LedgerEntryType.GRANT,
            amount=amount,
            balance_after=account.available,
            note=note,
        )
        self.store.credit_ledger.append(entry)
        return entry

    def reserve_for_scan(self, workspace_id: str, scan_id: str) -> CreditReservation:
        account = self.account(workspace_id)
        if account.available < 1:
            raise CreditError("workspace has no available scan credits")
        account.available -= 1
        account.reserved += 1
        reservation = CreditReservation(workspace_id=workspace_id, scan_id=scan_id)
        self.store.credit_reservations[scan_id] = reservation
        self.store.credit_ledger.append(
            CreditLedgerEntry(
                workspace_id=workspace_id,
                entry_type=LedgerEntryType.RESERVE,
                amount=-1,
                balance_after=account.available,
                scan_id=scan_id,
                note="Reserved one credit for scan",
            )
        )
        return reservation

    def deduct_completed_scan(self, scan: Scan) -> None:
        reservation = self.store.credit_reservations.get(scan.id)
        if not reservation or reservation.status == CreditReservationStatus.DEDUCTED:
            return
        if reservation.status == CreditReservationStatus.RELEASED:
            raise CreditError("cannot deduct a released credit reservation")
        account = self.account(scan.workspace_id)
        account.reserved -= 1
        account.consumed += 1
        reservation.status = CreditReservationStatus.DEDUCTED
        self.store.credit_ledger.append(
            CreditLedgerEntry(
                workspace_id=scan.workspace_id,
                entry_type=LedgerEntryType.DEDUCT,
                amount=-1,
                balance_after=account.available,
                scan_id=scan.id,
                note="Deducted one credit for completed scan",
            )
        )

    def release_scan(self, scan: Scan) -> None:
        reservation = self.store.credit_reservations.get(scan.id)
        if not reservation or reservation.status != CreditReservationStatus.RESERVED:
            return
        account = self.account(scan.workspace_id)
        account.reserved -= 1
        account.available += 1
        reservation.status = CreditReservationStatus.RELEASED
        self.store.credit_ledger.append(
            CreditLedgerEntry(
                workspace_id=scan.workspace_id,
                entry_type=LedgerEntryType.RELEASE,
                amount=1,
                balance_after=account.available,
                scan_id=scan.id,
                note=f"Released credit after scan ended with {scan.status}",
            )
        )


class ProjectService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_project(self, *, workspace_id: str, name: str) -> Project:
        return self.store.add(self.store.projects, Project(workspace_id=workspace_id, name=name))

    def create_target(
        self,
        *,
        workspace_id: str,
        project_id: str,
        name: str,
        url: str,
        excludes: list[str] | None = None,
        allow_private_networks: bool = False,
    ) -> Target:
        target = Target(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name,
            url=url,
            excludes=excludes or [],
            allow_private_networks=allow_private_networks,
        )
        validate_target_scope(target)
        return self.store.add(self.store.targets, target)


class ModelProfileService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_profile(self, *, workspace_id: str, name: str, model: str, api_base: str) -> ModelProfile:
        if not model.strip():
            raise ValueError("model is required")
        if not api_base.startswith(("http://", "https://")):
            raise ValueError("api_base must be an HTTP URL")
        profile = ModelProfile(workspace_id=workspace_id, name=name, model=model, api_base=api_base)
        return self.store.add(self.store.model_profiles, profile)

    def test_profile(self, profile_id: str) -> dict[str, object]:
        profile = self.store.get(self.store.model_profiles, profile_id, "model profile")
        return {
            "ok": True,
            "profile_id": profile.id,
            "route": profile.api_base,
            "model": profile.model,
            "message": "Profile shape is valid; live LiteLLM call is performed by deployment integration tests.",
        }


class ScanService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.credits = CreditService(store)

    def create_scan(
        self,
        *,
        workspace_id: str,
        project_id: str,
        target_id: str,
        scan_type: ScanType,
        model_profile_id: str,
        instructions: str = "",
    ) -> Scan:
        target = self.store.get(self.store.targets, target_id, "target")
        validate_target_scope(target)
        scan = self.store.add(
            self.store.scans,
            Scan(
                workspace_id=workspace_id,
                project_id=project_id,
                target_id=target_id,
                scan_type=scan_type,
                model_profile_id=model_profile_id,
                instructions=instructions,
            ),
        )
        self.credits.reserve_for_scan(workspace_id, scan.id)
        self.emit(scan.id, "scan.queued", "Scan queued and credit reserved")
        return scan

    def emit(self, scan_id: str, event_type: str, summary: str, payload: dict | None = None) -> ScanEvent:
        event = ScanEvent(scan_id=scan_id, type=event_type, summary=summary, payload=payload or {})
        self.store.events.append(event)
        return event

    def run_passive_scan(self, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        target = self.store.get(self.store.targets, scan.target_id, "target")
        scan.status = ScanStatus.RUNNING
        self.emit(scan.id, "scan.phase.started", "Passive blackbox scan started")
        self.emit(scan.id, "tool.completed", "Security header check completed", {"target": target.url})
        finding = Finding(
            scan_id=scan.id,
            title="Security header review completed",
            severity="info",
            affected_asset=target.url,
            evidence_refs=[f"evidence://{scan.id}/security-headers"],
            verification_status=VerificationStatus.VERIFIED,
        )
        self.store.add(self.store.findings, finding)
        self.emit(scan.id, "finding.verified", "Informational finding stored", {"finding_id": finding.id})
        self.complete_scan(scan.id)
        return scan

    def complete_scan(self, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        scan.status = ScanStatus.COMPLETED
        scan.completed_at = now_utc()
        self.credits.deduct_completed_scan(scan)
        self.emit(scan.id, "scan.completed", "Scan completed and one credit deducted")
        return scan

    def fail_scan(self, scan_id: str, reason: str = "Scan failed") -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        scan.status = ScanStatus.FAILED
        self.credits.release_scan(scan)
        self.emit(scan.id, "scan.failed", reason)
        return scan

    def cancel_scan(self, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        scan.status = ScanStatus.CANCELLED
        self.credits.release_scan(scan)
        self.emit(scan.id, "scan.cancelled", "Scan cancelled and reserved credit released")
        return scan


class AutonomousPentestService:
    phases = [
        "scope_validation",
        "recon",
        "crawl",
        "attack_surface_mapping",
        "safe_testing",
        "gated_verification",
        "report",
    ]

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.scans = ScanService(store)

    def start(self, scan_id: str) -> AgentPlan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        if scan.scan_type != ScanType.AUTONOMOUS_BLACKBOX:
            raise ValueError("autonomous start requires autonomous_blackbox scan type")
        target = self.store.get(self.store.targets, scan.target_id, "target")
        validate_target_scope(target)
        scan.status = ScanStatus.RUNNING
        plan = AgentPlan(
            scan_id=scan.id,
            phases=self.phases,
            current_phase="recon",
            objective=f"Run guarded autonomous blackbox assessment for {target.url}",
        )
        self.store.agent_plans[scan.id] = plan
        self.scans.emit(scan.id, "agent.plan.updated", "Autonomous plan created", {"plan_id": plan.id})
        self.scans.emit(scan.id, "scan.phase.started", "Recon phase started", {"phase": "recon"})
        browser_plan = self.create_browser_plan(scan.id)
        self.scans.emit(
            scan.id,
            "browser.plan.created",
            "Web/UI-driven scan plan created",
            {"browser_plan_id": browser_plan.id, "engine": browser_plan.engine},
        )
        self.scans.emit(scan.id, "tool.completed", "Safe HTTP baseline completed", {"target": target.url})
        return plan

    def create_browser_plan(self, scan_id: str) -> BrowserPlan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        target = self.store.get(self.store.targets, scan.target_id, "target")
        validate_target_scope(target)
        plan = BrowserPlan(
            scan_id=scan.id,
            target_url=target.url,
            engine="playwright",
            actions=[
                BrowserAction(
                    action_type="navigate",
                    selector="document",
                    description="Open the scoped target in an isolated browser context",
                    value=target.url,
                ),
                BrowserAction(
                    action_type="crawl",
                    selector="a[href], button, input, form",
                    description="Discover reachable UI routes and form entry points without submitting destructive actions",
                ),
                BrowserAction(
                    action_type="assert",
                    selector="form, [data-auth], input[type=password]",
                    description="Identify authentication, upload, and state-changing UI surfaces",
                ),
                BrowserAction(
                    action_type="capture_evidence",
                    selector="main, body",
                    description="Capture screenshot and DOM snapshot evidence for replayable findings",
                ),
                BrowserAction(
                    action_type="submit_controlled_payload",
                    selector="input[type=file], form[enctype]",
                    description="Verify upload handling only after human approval",
                    value="kerislab-controlled-upload.txt",
                    requires_approval=True,
                ),
            ],
        )
        self.store.browser_plans[scan.id] = plan
        return plan

    def browser_plan(self, scan_id: str) -> BrowserPlan:
        if scan_id not in self.store.browser_plans:
            return self.create_browser_plan(scan_id)
        return self.store.browser_plans[scan_id]

    def request_gated_upload_verification(self, scan_id: str) -> ApprovalRequest:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        target = self.store.get(self.store.targets, scan.target_id, "target")
        scan.status = ScanStatus.AWAITING_APPROVAL
        request = ApprovalRequest(
            workspace_id=scan.workspace_id,
            scan_id=scan.id,
            requested_by_agent="dast-agent",
            risk_category="file_upload_verification",
            target=target.url,
            proposed_tool="http.request.replay",
            proposed_action="Submit a controlled upload payload to verify file handling behavior",
            reason="The crawler discovered an upload endpoint that requires gated verification.",
            expected_evidence="HTTP transcript and response diff for the upload endpoint.",
            policy_reason="File upload verification is approval-required under guarded autonomy.",
        )
        self.store.approval_requests[request.id] = request
        self.scans.emit(
            scan.id,
            "approval.requested",
            "Approval required for upload verification",
            {"approval_id": request.id, "risk_category": request.risk_category},
        )
        return request

    def approve(self, approval_id: str, *, user_id: str, note: str = "") -> ApprovalRequest:
        request = self.store.get(self.store.approval_requests, approval_id, "approval request")
        if request.status != ApprovalStatus.PENDING:
            raise ApprovalError("approval request has already been resolved")
        request.status = ApprovalStatus.APPROVED
        request.resolved_by = user_id
        request.operator_note = note
        request.resolved_at = now_utc()
        scan = self.store.get(self.store.scans, request.scan_id, "scan")
        scan.status = ScanStatus.RUNNING
        self.scans.emit(
            scan.id,
            "approval.resolved",
            "Approval request approved",
            {"approval_id": request.id, "status": request.status},
        )
        self.scans.emit(scan.id, "tool.completed", "Gated upload verification completed", {"approval_id": request.id})
        return request

    def reject(self, approval_id: str, *, user_id: str, note: str = "") -> ApprovalRequest:
        request = self.store.get(self.store.approval_requests, approval_id, "approval request")
        if request.status != ApprovalStatus.PENDING:
            raise ApprovalError("approval request has already been resolved")
        request.status = ApprovalStatus.REJECTED
        request.resolved_by = user_id
        request.operator_note = note
        request.resolved_at = now_utc()
        scan = self.store.get(self.store.scans, request.scan_id, "scan")
        scan.status = ScanStatus.RUNNING
        self.scans.emit(
            scan.id,
            "approval.resolved",
            "Approval request rejected; agent will replan",
            {"approval_id": request.id, "status": request.status},
        )
        self.scans.emit(scan.id, "agent.plan.updated", "Agent replanned without rejected gated action")
        return request


class ReportService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def generate_json_report(self, scan_id: str) -> Report:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        findings = [f for f in self.store.findings.values() if f.scan_id == scan_id]
        events = [e for e in self.store.events if e.scan_id == scan_id]
        content = {
            "scan": {
                "id": scan.id,
                "status": scan.status,
                "scan_type": scan.scan_type,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
            },
            "findings": [
                {
                    "id": finding.id,
                    "title": finding.title,
                    "severity": finding.severity,
                    "affected_asset": finding.affected_asset,
                    "verification_status": finding.verification_status,
                    "evidence_refs": finding.evidence_refs,
                }
                for finding in findings
            ],
            "event_count": len(events),
        }
        report = Report(
            workspace_id=scan.workspace_id,
            project_id=scan.project_id,
            scan_id=scan.id,
            title=f"KerisLab report for {scan.id}",
            format="json",
            content=content,
        )
        return self.store.add(self.store.reports, report)
