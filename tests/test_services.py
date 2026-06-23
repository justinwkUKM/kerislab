import unittest
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from kerislab.models import (
    ApprovalStatus,
    AuthProvider,
    LedgerEntryType,
    Role,
    ScanJobType,
    ScanStatus,
    ScanType,
    WorkspaceMembership,
)
from kerislab.services import (
    AuthService,
    AuditService,
    ApprovalError,
    AuthorizationError,
    AuthorizationService,
    BillingService,
    AutonomousPentestService,
    BrowserExecutionService,
    CreditError,
    CreditService,
    EvidenceStorageService,
    ModelProfileService,
    ProjectService,
    ReportService,
    ScanService,
    ScanExecutionService,
    WorkerStatusService,
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

    def test_auth_service_creates_valid_and_revocable_sessions(self) -> None:
        auth = AuthService(self.store)
        session = auth.create_session(self.user, user_agent="pytest")
        resolved = auth.user_for_session_token(session.token)
        self.assertEqual(resolved.id, self.user.id)
        self.assertIsNotNone(session.last_seen_at)
        auth.revoke_session_token(session.token)
        with self.assertRaises(AuthorizationError):
            auth.user_for_session_token(session.token)

    def test_audit_log_records_workspace_creation_and_authorization_blocks_non_members(self) -> None:
        entries = AuditService(self.store).list(workspace_id=self.workspace.id)
        self.assertTrue(any(entry.action == "workspace_created" for entry in entries))

        outsider = AuthService(self.store).login_identity(
            email="outsider@example.com",
            display_name="Outsider",
            provider=AuthProvider.GOOGLE,
        )
        with self.assertRaises(AuthorizationError):
            AuthorizationService(self.store).require_workspace_member(outsider.id, self.workspace.id)

    def test_authorization_enforces_workspace_roles(self) -> None:
        developer = AuthService(self.store).login_identity(
            email="developer@example.com",
            display_name="Developer",
            provider=AuthProvider.GOOGLE,
        )
        self.store.add(
            self.store.memberships,
            WorkspaceMembership(workspace_id=self.workspace.id, user_id=developer.id, role=Role.DEVELOPER),
        )
        authz = AuthorizationService(self.store)
        self.assertEqual(authz.require_workspace_member(developer.id, self.workspace.id).role, Role.DEVELOPER)
        with self.assertRaises(AuthorizationError):
            authz.require_workspace_role(developer.id, self.workspace.id, {Role.OWNER, Role.ADMIN})
        self.assertEqual(authz.require_workspace_role(self.user.id, self.workspace.id, {Role.OWNER}).role, Role.OWNER)

    def test_allowed_domain_login_auto_joins_workspace_as_developer(self) -> None:
        WorkspaceService(self.store).update_sso_domains(
            workspace_id=self.workspace.id,
            allowed_domains=["Example.com"],
        )
        user = AuthService(self.store).login_identity(
            email="newhire@example.com",
            display_name="New Hire",
            provider=AuthProvider.SSO,
        )
        membership = AuthorizationService(self.store).require_workspace_member(user.id, self.workspace.id)
        self.assertEqual(membership.role, Role.DEVELOPER)
        self.assertEqual(self.store.user_settings[user.id].default_workspace_id, self.workspace.id)
        self.assertTrue(
            any(entry.action == "workspace_member_auto_joined" for entry in self.store.audit_logs)
        )

    def test_credit_grant_creates_available_balance_and_ledger(self) -> None:
        account = CreditService(self.store).account(self.workspace.id)
        self.assertEqual(account.available, 2)
        self.assertEqual(self.store.credit_ledger[0].entry_type, LedgerEntryType.GRANT)

    def test_billing_checkout_confirmation_grants_credits_once(self) -> None:
        billing = BillingService(self.store)
        session = billing.create_checkout_session(
            workspace_id=self.workspace.id,
            credit_amount=5,
            billing_email="billing@example.com",
            unit_amount_cents=700,
        )
        session, invoice, payment, ledger_entry = billing.confirm_checkout_session(
            checkout_session_id=session.id,
            provider_payment_id="pay_test",
        )
        repeated = billing.confirm_checkout_session(checkout_session_id=session.id)
        account = CreditService(self.store).account(self.workspace.id)
        self.assertEqual(session.status, "paid")
        self.assertEqual(invoice.amount_cents, 3500)
        self.assertEqual(payment.provider_payment_id, "pay_test")
        self.assertEqual(ledger_entry.amount, 5)
        self.assertEqual(repeated[3].id, ledger_entry.id)
        self.assertEqual(account.available, 7)

    def test_billing_webhook_processing_is_idempotent(self) -> None:
        billing = BillingService(self.store)
        session = billing.create_checkout_session(
            workspace_id=self.workspace.id,
            credit_amount=3,
            billing_email="billing@example.com",
        )
        event = billing.process_webhook_event(
            provider="stripe",
            provider_event_id="evt_1",
            event_type="checkout.session.completed",
            payload={"checkout_session_id": session.id, "provider_payment_id": "pay_1"},
        )
        repeated = billing.process_webhook_event(
            provider="stripe",
            provider_event_id="evt_1",
            event_type="checkout.session.completed",
            payload={"checkout_session_id": session.id, "provider_payment_id": "pay_1"},
        )
        account = CreditService(self.store).account(self.workspace.id)
        self.assertTrue(event.processed)
        self.assertEqual(repeated.id, event.id)
        self.assertEqual(account.available, 5)

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

    def test_scan_pause_resume_and_instructions(self) -> None:
        scans = ScanService(self.store)
        autonomous = AutonomousPentestService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.AUTONOMOUS_BLACKBOX,
            model_profile_id="default",
        )
        autonomous.start(scan.id)
        scans.update_instructions(scan.id, "Focus on auth flows")
        self.assertEqual(scan.instructions, "Focus on auth flows")
        paused = scans.pause_scan(scan.id)
        self.assertEqual(paused.status, ScanStatus.PAUSED)
        resumed = scans.resume_scan(scan.id)
        self.assertEqual(resumed.status, ScanStatus.RUNNING)

    def test_scan_execution_service_drains_queued_jobs(self) -> None:
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.PASSIVE_BLACKBOX,
            model_profile_id="default",
        )
        engine = ScanExecutionService(self.store)
        engine.enqueue(scan.id, ScanJobType.PASSIVE_SCAN)
        engine.drain()
        self.assertEqual(scan.status, ScanStatus.COMPLETED)
        self.assertTrue(all(job.status.name == "COMPLETED" for job in self.store.scan_jobs.values()))

    def test_scan_execution_service_uses_redis_queue_when_configured(self) -> None:
        pushed: list[str] = []

        class FakeRedisClient:
            def ping(self):
                return True

            def rpush(self, _queue_name, job_id):
                pushed.append(job_id)

            def lpop(self, _queue_name):
                if not pushed:
                    return None
                return pushed.pop(0)

        fake_redis = SimpleNamespace(Redis=SimpleNamespace(from_url=lambda *_args, **_kwargs: FakeRedisClient()))
        scans = ScanService(self.store)
        scan = scans.create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.PASSIVE_BLACKBOX,
            model_profile_id="default",
        )

        with patch.dict("os.environ", {"KERISLAB_REDIS_URL": "redis://redis:6379/0"}, clear=False):
            with patch.dict("sys.modules", {"redis": fake_redis}):
                engine = ScanExecutionService(self.store)
                job = engine.enqueue(scan.id, ScanJobType.PASSIVE_SCAN)
                self.assertEqual(pushed, [job.id])
                self.assertEqual(engine.drain_redis_jobs(), 1)

        self.assertEqual(scan.status, ScanStatus.COMPLETED)
        self.assertEqual(self.store.scan_jobs[job.id].status, "completed")

    def test_worker_status_service_reports_active_heartbeat(self) -> None:
        service = WorkerStatusService(self.store)
        heartbeat = service.heartbeat(
            worker_id="worker-1",
            name="kerislab-test-worker",
            queue_name="kerislab:scan-jobs",
            processed_jobs=3,
        )
        components = service.components()

        self.assertEqual(heartbeat.id, "worker-1")
        self.assertEqual(components["status"], "ok")
        self.assertEqual(components["worker_heartbeat"]["status"], "ok")
        self.assertEqual(components["worker_heartbeat"]["active"], 1)
        self.assertEqual(components["worker_heartbeat"]["workers"][0].processed_jobs, 3)

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

    def test_browser_execution_persists_result_and_events(self) -> None:
        scan = ScanService(self.store).create_scan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            target_id=self.target.id,
            scan_type=ScanType.AUTONOMOUS_BLACKBOX,
            model_profile_id="default",
        )

        def runner(plan):
            return {
                "engine": plan.engine,
                "visited": [plan.target_url],
                "title": "Example",
                "actions": len([action for action in plan.actions if not action.requires_approval]),
                "evidence": [
                    {
                        "artifact_type": "browser_dom_snapshot",
                        "summary": "Captured DOM",
                        "content_type": "text/html",
                        "content": "<html><title>Example</title></html>",
                        "metadata": {"url": plan.target_url},
                    }
                ],
            }

        result = BrowserExecutionService(self.store, runner=runner).execute(scan.id)
        executions = list(self.store.browser_executions.values())
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0].status, "completed")
        self.assertEqual(executions[0].result["title"], "Example")
        self.assertEqual(result["execution_id"], executions[0].id)
        self.assertEqual(len(self.store.evidence_artifacts), 1)
        artifact = next(iter(self.store.evidence_artifacts.values()))
        self.assertEqual(artifact.browser_execution_id, executions[0].id)
        self.assertEqual(artifact.content, "")
        self.assertIn("object_uri", artifact.metadata)
        self.assertEqual(result["evidence_refs"], [artifact.uri])
        self.assertTrue(any(e.type == "browser.execution.started" for e in self.store.events))
        self.assertTrue(any(e.type == "browser.execution.completed" for e in self.store.events))

    def test_evidence_storage_uses_local_filesystem_when_object_storage_is_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(
                "os.environ",
                {"KERISLAB_EVIDENCE_LOCAL_PATH": tmp},
                clear=True,
            ):
                uri = EvidenceStorageService().store(
                    key="scan/execution/artifact.html",
                    content="<html></html>",
                    content_type="text/html",
                )
            path = Path(uri.removeprefix("file://"))
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(), "<html></html>")

    def test_evidence_storage_uses_s3_compatible_object_storage_when_configured(self) -> None:
        captured: dict[str, object] = {}

        class FakeS3Client:
            def put_object(self, **kwargs):
                captured.update(kwargs)

        fake_boto3 = SimpleNamespace(client=lambda *_, **__: FakeS3Client())
        with patch.dict(
            "os.environ",
            {
                "KERISLAB_OBJECT_STORAGE_ENDPOINT": "http://minio:9000",
                "KERISLAB_OBJECT_STORAGE_BUCKET": "kerislab-evidence",
                "KERISLAB_OBJECT_STORAGE_ACCESS_KEY": "kerislab",
                "KERISLAB_OBJECT_STORAGE_SECRET_KEY": "secret",
            },
            clear=True,
        ):
            with patch.dict("sys.modules", {"boto3": fake_boto3}):
                uri = EvidenceStorageService().store(
                    key="scan/execution/artifact.html",
                    content="<html></html>",
                    content_type="text/html",
                )

        self.assertEqual(uri, "s3://kerislab-evidence/scan/execution/artifact.html")
        self.assertEqual(captured["Bucket"], "kerislab-evidence")
        self.assertEqual(captured["Key"], "scan/execution/artifact.html")
        self.assertEqual(captured["Body"], b"<html></html>")
        self.assertEqual(captured["ContentType"], "text/html")

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
