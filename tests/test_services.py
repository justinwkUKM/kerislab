import unittest

from kerislab.models import ApprovalStatus, AuthProvider, LedgerEntryType, ScanStatus, ScanType
from kerislab.services import (
    AuthService,
    ApprovalError,
    AutonomousPentestService,
    CreditError,
    CreditService,
    ModelProfileService,
    ProjectService,
    ReportService,
    ScanService,
    WorkspaceService,
)
from kerislab.store import InMemoryStore


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryStore()
        self.user = AuthService(self.store).login_identity(
            email="owner@example.com",
            display_name="Owner",
            provider=AuthProvider.GOOGLE,
        )
        self.workspace = WorkspaceService(self.store).create_workspace(
            name="KerisLab Workspace",
            owner=self.user,
            initial_credits=2,
        )
        self.project = ProjectService(self.store).create_project(
            workspace_id=self.workspace.id,
            name="Example Assessment",
        )
        self.target = ProjectService(self.store).create_target(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            name="Example",
            url="https://example.com",
        )

    def test_google_identity_gets_profile_settings_and_workspace(self) -> None:
        self.assertEqual(self.user.provider, AuthProvider.GOOGLE)
        self.assertIn(self.user.id, self.store.user_settings)
        self.assertEqual(self.store.user_settings[self.user.id].default_workspace_id, self.workspace.id)
        memberships = [m for m in self.store.memberships.values() if m.user_id == self.user.id]
        self.assertEqual(len(memberships), 1)

    def test_credit_grant_creates_available_balance_and_ledger(self) -> None:
        account = CreditService(self.store).account(self.workspace.id)
        self.assertEqual(account.available, 2)
        self.assertEqual(self.store.credit_ledger[0].entry_type, LedgerEntryType.GRANT)

    def test_create_scan_reserves_one_credit(self) -> None:
        scan = ScanService(self.store).create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.PASSIVE_BLACKBOX,
            model_profile_id="default",
        )
        account = CreditService(self.store).account(self.workspace.id)
        self.assertEqual(scan.status, ScanStatus.QUEUED)
        self.assertEqual(account.available, 1)
        self.assertEqual(account.reserved, 1)

    def test_completed_scan_deducts_reserved_credit_once(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.PASSIVE_BLACKBOX,
            model_profile_id="default",
        )
        scans.complete_scan(scan.id)
        scans.complete_scan(scan.id)
        account = CreditService(self.store).account(self.workspace.id)
        self.assertEqual(account.available, 1)
        self.assertEqual(account.reserved, 0)
        self.assertEqual(account.consumed, 1)
        deducts = [e for e in self.store.credit_ledger if e.entry_type == LedgerEntryType.DEDUCT]
        self.assertEqual(len(deducts), 1)

    def test_failed_scan_releases_reserved_credit(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.PASSIVE_BLACKBOX,
            model_profile_id="default",
        )
        scans.fail_scan(scan.id)
        account = CreditService(self.store).account(self.workspace.id)
        self.assertEqual(account.available, 2)
        self.assertEqual(account.reserved, 0)
        self.assertEqual(account.consumed, 0)

    def test_scan_creation_fails_without_available_credit(self) -> None:
        account = CreditService(self.store).account(self.workspace.id)
        account.available = 0
        with self.assertRaises(CreditError):
            ScanService(self.store).create_scan(
                workspace_id=self.workspace.id,
                project_id=self.project.id,
                target_id=self.target.id,
                scan_type=ScanType.PASSIVE_BLACKBOX,
                model_profile_id="default",
            )

    def test_run_passive_scan_creates_verified_evidence_backed_finding(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.PASSIVE_BLACKBOX,
            model_profile_id="default",
        )
        scans.run_passive_scan(scan.id)
        findings = list(self.store.findings.values())
        self.assertEqual(scan.status, ScanStatus.COMPLETED)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].evidence_refs)
        self.assertTrue(any(e.type == "scan.completed" for e in self.store.events))

    def test_litellm_profile_shape_can_be_configured_and_tested(self) -> None:
        profiles = ModelProfileService(self.store)
        profile = profiles.create_profile(
            workspace_id=self.workspace.id,
            name="Default LiteLLM",
            model="openai/gpt-4o-mini",
            api_base="http://localhost:4000",
        )
        result = profiles.test_profile(profile.id)
        self.assertTrue(result["ok"])
        self.assertEqual(result["model"], "openai/gpt-4o-mini")

    def test_json_report_is_generated_from_stored_scan_data(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.PASSIVE_BLACKBOX,
            model_profile_id="default",
        )
        scans.run_passive_scan(scan.id)
        report = ReportService(self.store).generate_json_report(scan.id)
        self.assertEqual(report.format, "json")
        self.assertEqual(report.content["scan"]["status"], ScanStatus.COMPLETED)
        self.assertEqual(len(report.content["findings"]), 1)

    def test_autonomous_scan_creates_agent_plan_and_safe_events(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.AUTONOMOUS_BLACKBOX,
            model_profile_id="default",
            instructions="Focus on auth and upload handling",
        )
        plan = AutonomousPentestService(self.store).start(scan.id)
        self.assertEqual(scan.status, ScanStatus.RUNNING)
        self.assertEqual(plan.current_phase, "recon")
        self.assertIn("safe_testing", plan.phases)
        browser_plan = self.store.browser_plans[scan.id]
        self.assertEqual(browser_plan.engine, "playwright")
        self.assertTrue(any(action.action_type == "crawl" for action in browser_plan.actions))
        self.assertTrue(any(action.requires_approval for action in browser_plan.actions))
        self.assertTrue(any(e.type == "agent.plan.updated" for e in self.store.events))
        self.assertTrue(any(e.type == "browser.plan.created" for e in self.store.events))
        self.assertTrue(any(e.type == "tool.completed" for e in self.store.events))

    def test_autonomous_gated_action_creates_pending_approval_and_preserves_credit(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.AUTONOMOUS_BLACKBOX,
            model_profile_id="default",
        )
        AutonomousPentestService(self.store).start(scan.id)
        approval = AutonomousPentestService(self.store).request_gated_upload_verification(scan.id)
        account = CreditService(self.store).account(self.workspace.id)
        self.assertEqual(scan.status, ScanStatus.AWAITING_APPROVAL)
        self.assertEqual(approval.status, ApprovalStatus.PENDING)
        self.assertEqual(account.available, 1)
        self.assertEqual(account.reserved, 1)
        self.assertTrue(any(e.type == "approval.requested" for e in self.store.events))

    def test_approval_allows_gated_action_to_continue(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.AUTONOMOUS_BLACKBOX,
            model_profile_id="default",
        )
        autonomous = AutonomousPentestService(self.store)
        autonomous.start(scan.id)
        approval = autonomous.request_gated_upload_verification(scan.id)
        resolved = autonomous.approve(approval.id, user_id=self.user.id, note="Approved for staging")
        self.assertEqual(resolved.status, ApprovalStatus.APPROVED)
        self.assertEqual(scan.status, ScanStatus.RUNNING)
        self.assertTrue(any(e.type == "approval.resolved" for e in self.store.events))
        self.assertTrue(any(e.summary == "Gated upload verification completed" for e in self.store.events))

    def test_rejected_approval_replans_without_gated_action(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.AUTONOMOUS_BLACKBOX,
            model_profile_id="default",
        )
        autonomous = AutonomousPentestService(self.store)
        autonomous.start(scan.id)
        approval = autonomous.request_gated_upload_verification(scan.id)
        resolved = autonomous.reject(approval.id, user_id=self.user.id, note="Skip upload checks")
        self.assertEqual(resolved.status, ApprovalStatus.REJECTED)
        self.assertEqual(scan.status, ScanStatus.RUNNING)
        self.assertTrue(any(e.summary == "Agent replanned without rejected gated action" for e in self.store.events))

    def test_resolved_approval_cannot_be_resolved_again(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.AUTONOMOUS_BLACKBOX,
            model_profile_id="default",
        )
        autonomous = AutonomousPentestService(self.store)
        autonomous.start(scan.id)
        approval = autonomous.request_gated_upload_verification(scan.id)
        autonomous.approve(approval.id, user_id=self.user.id)
        with self.assertRaises(ApprovalError):
            autonomous.reject(approval.id, user_id=self.user.id)


if __name__ == "__main__":
    unittest.main()
