import os
import unittest
import hmac
import json
from hashlib import sha256
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from kerislab import main
from kerislab.models import EvidenceArtifact, Role, WorkspaceMembership
from kerislab.services import WorkerStatusService
from kerislab.store import InMemoryStore


def billing_signature(secret: str, payload: dict[str, object]) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret.encode(), body, sha256).hexdigest()


class ApiHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        main.store = InMemoryStore()
        self.client = TestClient(main.app)
        login = self.client.post(
            "/api/auth/dev-login",
            json={
                "email": "owner@example.com",
                "display_name": "Owner",
                "provider": "google",
            },
        )
        self.assertEqual(login.status_code, 200)
        self.headers = {"X-KerisLab-User": login.json()["user"]["id"]}
        self.bearer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        workspace = self.client.post(
            "/api/workspaces",
            json={"name": "Workspace", "initial_credits": 2},
            headers=self.headers,
        )
        self.assertEqual(workspace.status_code, 200)
        self.workspace_id = workspace.json()["workspace"]["id"]

        project = self.client.post(
            "/api/projects",
            json={"workspace_id": self.workspace_id, "name": "Project"},
            headers=self.headers,
        )
        self.assertEqual(project.status_code, 200)
        self.project_id = project.json()["project"]["id"]

        target = self.client.post(
            "/api/targets",
            json={
                "workspace_id": self.workspace_id,
                "project_id": self.project_id,
                "name": "Example",
                "url": "https://example.com",
            },
            headers=self.headers,
        )
        self.assertEqual(target.status_code, 200)
        self.target_id = target.json()["target"]["id"]

    def test_health_and_auth_me(self) -> None:
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        WorkerStatusService(main.store).heartbeat(
            worker_id="worker-1",
            name="kerislab-test-worker",
            queue_name="kerislab:scan-jobs",
        )
        components = self.client.get("/api/health/components")
        self.assertEqual(components.status_code, 200)
        self.assertEqual(components.json()["status"], "ok")
        self.assertEqual(components.json()["worker_heartbeat"]["active"], 1)

        me = self.client.get("/api/auth/me", headers=self.headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], "owner@example.com")
        self.assertIn("settings", me.json())

        bearer_me = self.client.get("/api/auth/me", headers=self.bearer_headers)
        self.assertEqual(bearer_me.status_code, 200)
        self.assertEqual(bearer_me.json()["user"]["email"], "owner@example.com")

    def test_logout_revokes_bearer_session_over_http(self) -> None:
        before = self.client.get("/api/auth/me", headers=self.bearer_headers)
        self.assertEqual(before.status_code, 200)

        logout = self.client.post("/api/auth/logout", headers=self.bearer_headers)
        self.assertEqual(logout.status_code, 200)
        self.assertIsNotNone(logout.json()["session"]["revoked_at"])

        after = self.client.get("/api/auth/me", headers=self.bearer_headers)
        self.assertEqual(after.status_code, 401)

    def test_google_oauth_login_creates_and_consumes_state_once(self) -> None:
        env = {
            "KERISLAB_GOOGLE_CLIENT_ID": "client-id",
            "KERISLAB_GOOGLE_CLIENT_SECRET": "client-secret",
            "KERISLAB_GOOGLE_REDIRECT_URI": "https://kerislab.example.com/api/auth/oidc/callback",
        }
        with patch.dict(os.environ, env, clear=False):
            login = self.client.get("/api/auth/google/login")
            self.assertEqual(login.status_code, 200)
            parsed = urlparse(login.json()["authorization_url"])
            state = parse_qs(parsed.query)["state"][0]
            self.assertIn(state, main.store.oauth_states)

            with patch.object(
                main.OAuthService,
                "exchange_code",
                return_value={"email": "oauth@example.com", "name": "OAuth User"},
            ):
                callback = self.client.post(
                    "/api/auth/oidc/callback",
                    json={"provider": "google", "code": "auth-code", "state": state},
                )
                self.assertEqual(callback.status_code, 200)
                self.assertEqual(callback.json()["user"]["email"], "oauth@example.com")
                self.assertEqual(callback.json()["token_type"], "bearer")
                self.assertTrue(callback.json()["access_token"])

                replay = self.client.post(
                    "/api/auth/oidc/callback",
                    json={"provider": "google", "code": "auth-code", "state": state},
                )
                self.assertEqual(replay.status_code, 400)
                self.assertIn("already been used", replay.json()["detail"])

    def test_google_oauth_get_callback_supports_provider_redirect(self) -> None:
        env = {
            "KERISLAB_GOOGLE_CLIENT_ID": "client-id",
            "KERISLAB_GOOGLE_CLIENT_SECRET": "client-secret",
            "KERISLAB_GOOGLE_REDIRECT_URI": "https://kerislab.example.com/api/auth/oidc/callback",
        }
        with patch.dict(os.environ, env, clear=False):
            login = self.client.get("/api/auth/google/login")
            self.assertEqual(login.status_code, 200)
            state = parse_qs(urlparse(login.json()["authorization_url"]).query)["state"][0]

            with patch.object(
                main.OAuthService,
                "exchange_code",
                return_value={"email": "redirect@example.com", "name": "Redirect User"},
            ):
                callback = self.client.get(f"/api/auth/oidc/callback?code=auth-code&state={state}")

        self.assertEqual(callback.status_code, 200)
        self.assertEqual(callback.json()["user"]["email"], "redirect@example.com")
        self.assertEqual(callback.json()["token_type"], "bearer")
        self.assertTrue(callback.json()["access_token"])

    def test_workspace_project_and_scan_list_views_over_http(self) -> None:
        workspaces = self.client.get("/api/workspaces", headers=self.headers)
        self.assertEqual(workspaces.status_code, 200)
        self.assertEqual(len(workspaces.json()["workspaces"]), 1)

        workspace = self.client.get(f"/api/workspaces/{self.workspace_id}", headers=self.headers)
        self.assertEqual(workspace.status_code, 200)
        self.assertEqual(workspace.json()["workspace"]["id"], self.workspace_id)

        projects = self.client.get("/api/projects?workspace_id={}".format(self.workspace_id), headers=self.headers)
        self.assertEqual(projects.status_code, 200)
        self.assertEqual(len(projects.json()["projects"]), 1)

        targets = self.client.get(f"/api/projects/{self.project_id}/targets", headers=self.headers)
        self.assertEqual(targets.status_code, 200)
        self.assertEqual(len(targets.json()["targets"]), 1)

    def test_workspace_sso_domains_auto_join_matching_login_over_http(self) -> None:
        updated = self.client.patch(
            f"/api/workspaces/{self.workspace_id}/sso",
            json={"allowed_domains": ["Example.com"]},
            headers=self.headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["workspace"]["allowed_domains"], ["example.com"])

        login = self.client.post(
            "/api/auth/dev-login",
            json={"email": "teammate@example.com", "display_name": "Teammate", "provider": "sso"},
        )
        self.assertEqual(login.status_code, 200)
        memberships = login.json()["session_header"]
        teammate_headers = {"X-KerisLab-User": memberships["X-KerisLab-User"]}
        workspace = self.client.get(f"/api/workspaces/{self.workspace_id}", headers=teammate_headers)
        self.assertEqual(workspace.status_code, 200)
        roles = {member["role"] for member in workspace.json()["memberships"]}
        self.assertIn("developer", roles)

    def test_audit_logs_and_workspace_tenancy_over_http(self) -> None:
        grant = self.client.post(
            f"/api/workspaces/{self.workspace_id}/credits/grant",
            json={"amount": 1, "note": "manual top-up"},
            headers=self.headers,
        )
        self.assertEqual(grant.status_code, 200)

        audit = self.client.get(f"/api/audit-logs?workspace_id={self.workspace_id}", headers=self.headers)
        self.assertEqual(audit.status_code, 200)
        actions = {entry["action"] for entry in audit.json()["entries"]}
        self.assertIn("workspace_created", actions)
        self.assertIn("credits_granted", actions)

        other_login = self.client.post(
            "/api/auth/dev-login",
            json={"email": "other@example.com", "display_name": "Other", "provider": "google"},
        )
        self.assertEqual(other_login.status_code, 200)
        other_headers = {"X-KerisLab-User": other_login.json()["user"]["id"]}

        denied = self.client.get(f"/api/workspaces/{self.workspace_id}", headers=other_headers)
        self.assertEqual(denied.status_code, 403)

        hidden = self.client.get("/api/workspaces", headers=other_headers)
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(hidden.json()["workspaces"], [])

    def test_billing_checkout_confirmation_adds_credits_over_http(self) -> None:
        checkout = self.client.post(
            f"/api/workspaces/{self.workspace_id}/billing/checkout-sessions",
            json={
                "credit_amount": 4,
                "billing_email": "billing@example.com",
                "unit_amount_cents": 600,
            },
            headers=self.headers,
        )
        self.assertEqual(checkout.status_code, 200)
        checkout_id = checkout.json()["checkout_session"]["id"]
        self.assertEqual(checkout.json()["checkout_session"]["status"], "created")

        confirmed = self.client.post(
            f"/api/billing/checkout-sessions/{checkout_id}/confirm",
            json={"provider_payment_id": "pay_test"},
            headers=self.headers,
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["checkout_session"]["status"], "paid")
        self.assertEqual(confirmed.json()["invoice"]["amount_cents"], 2400)
        self.assertEqual(confirmed.json()["payment"]["status"], "succeeded")
        self.assertEqual(confirmed.json()["credits"]["available"], 6)

        repeated = self.client.post(
            f"/api/billing/checkout-sessions/{checkout_id}/confirm",
            json={},
            headers=self.headers,
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["credits"]["available"], 6)

    def test_signed_billing_webhook_confirms_checkout_once_over_http(self) -> None:
        checkout = self.client.post(
            f"/api/workspaces/{self.workspace_id}/billing/checkout-sessions",
            json={
                "credit_amount": 2,
                "billing_email": "billing@example.com",
                "unit_amount_cents": 600,
                "provider": "stripe",
            },
            headers=self.headers,
        )
        self.assertEqual(checkout.status_code, 200)
        checkout_id = checkout.json()["checkout_session"]["id"]
        payload = {
            "provider": "stripe",
            "provider_event_id": "evt_paid_1",
            "event_type": "checkout.session.completed",
            "data": {
                "checkout_session_id": checkout_id,
                "provider_payment_id": "pay_webhook",
                "workspace_id": self.workspace_id,
            },
        }
        headers = {"X-KerisLab-Signature": billing_signature("secret", payload)}
        with patch.dict(os.environ, {"KERISLAB_BILLING_WEBHOOK_SECRET": "secret"}, clear=False):
            confirmed = self.client.post("/api/billing/webhooks", json=payload, headers=headers)
            repeated = self.client.post("/api/billing/webhooks", json=payload, headers=headers)
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["event"]["processed"], True)
        self.assertEqual(repeated.status_code, 200)

        credits = self.client.get(f"/api/workspaces/{self.workspace_id}/credits", headers=self.headers)
        self.assertEqual(credits.status_code, 200)
        self.assertEqual(credits.json()["credits"]["available"], 4)

    def test_billing_webhook_rejects_invalid_signature(self) -> None:
        payload = {
            "provider": "stripe",
            "provider_event_id": "evt_bad",
            "event_type": "checkout.session.completed",
            "data": {"checkout_session_id": "missing"},
        }
        with patch.dict(os.environ, {"KERISLAB_BILLING_WEBHOOK_SECRET": "secret"}, clear=False):
            response = self.client.post(
                "/api/billing/webhooks",
                json=payload,
                headers={"X-KerisLab-Signature": "bad"},
            )
        self.assertEqual(response.status_code, 401)

    def test_non_admin_workspace_member_cannot_manage_admin_billing_or_model_settings(self) -> None:
        developer_login = self.client.post(
            "/api/auth/dev-login",
            json={"email": "developer@example.com", "display_name": "Developer", "provider": "google"},
        )
        self.assertEqual(developer_login.status_code, 200)
        developer_id = developer_login.json()["user"]["id"]
        main.store.add(
            main.store.memberships,
            WorkspaceMembership(workspace_id=self.workspace_id, user_id=developer_id, role=Role.DEVELOPER),
        )
        developer_headers = {"X-KerisLab-User": developer_id}

        workspace = self.client.get(f"/api/workspaces/{self.workspace_id}", headers=developer_headers)
        self.assertEqual(workspace.status_code, 200)

        grant = self.client.post(
            f"/api/workspaces/{self.workspace_id}/credits/grant",
            json={"amount": 1, "note": "blocked"},
            headers=developer_headers,
        )
        self.assertEqual(grant.status_code, 403)

        checkout = self.client.post(
            f"/api/workspaces/{self.workspace_id}/billing/checkout-sessions",
            json={"credit_amount": 1, "billing_email": "developer@example.com"},
            headers=developer_headers,
        )
        self.assertEqual(checkout.status_code, 403)

        sso = self.client.patch(
            f"/api/workspaces/{self.workspace_id}/sso",
            json={"allowed_domains": ["example.com"]},
            headers=developer_headers,
        )
        self.assertEqual(sso.status_code, 403)

        profile = self.client.post(
            "/api/settings/llm/profiles",
            json={
                "workspace_id": self.workspace_id,
                "name": "Blocked",
                "model": "openai/gpt-4o-mini",
                "api_base": "http://localhost:4000",
            },
            headers=developer_headers,
        )
        self.assertEqual(profile.status_code, 403)

    def test_user_settings_and_model_profile_flow_over_http(self) -> None:
        settings = self.client.patch(
            "/api/users/me",
            json={"theme": "light", "timezone": "Asia/Kuala_Lumpur", "notifications_enabled": False},
            headers=self.headers,
        )
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(settings.json()["settings"]["timezone"], "Asia/Kuala_Lumpur")
        self.assertFalse(settings.json()["settings"]["notifications_enabled"])

        profile = self.client.post(
            "/api/settings/llm/profiles",
            json={
                "workspace_id": self.workspace_id,
                "name": "Default LiteLLM",
                "model": "openai/gpt-4o-mini",
                "api_base": "http://localhost:4000",
            },
            headers=self.headers,
        )
        self.assertEqual(profile.status_code, 200)
        profile_id = profile.json()["profile"]["id"]

        tested = self.client.post(f"/api/settings/llm/profiles/{profile_id}/test", headers=self.headers)
        self.assertEqual(tested.status_code, 200)
        self.assertTrue(tested.json()["ok"])
        self.assertEqual(tested.json()["model"], "openai/gpt-4o-mini")

    def test_private_target_is_rejected(self) -> None:
        response = self.client.post(
            "/api/targets",
            json={
                "workspace_id": self.workspace_id,
                "project_id": self.project_id,
                "name": "Local",
                "url": "http://127.0.0.1:8000",
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_autonomous_scan_approval_flow_over_http(self) -> None:
        scan = self.client.post(
            "/api/scans",
            json={
                "workspace_id": self.workspace_id,
                "project_id": self.project_id,
                "target_id": self.target_id,
                "scan_type": "autonomous_blackbox",
                "model_profile_id": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(scan.status_code, 200)
        scan_id = scan.json()["scan"]["id"]
        self.assertEqual(scan.json()["credits"]["available"], 1)

        started = self.client.post(f"/api/scans/{scan_id}/start-autonomous", headers=self.headers)
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["scan"]["status"], "running")

        detail = self.client.get(f"/api/scans/{scan_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["scan"]["id"], scan_id)

        browser_plan = self.client.get(f"/api/scans/{scan_id}/browser-plan", headers=self.headers)
        self.assertEqual(browser_plan.status_code, 200)
        self.assertEqual(browser_plan.json()["browser_plan"]["engine"], "playwright")
        self.assertTrue(
            any(action["requires_approval"] for action in browser_plan.json()["browser_plan"]["actions"])
        )

        updated = self.client.post(
            f"/api/scans/{scan_id}/instructions",
            json={"instructions": "Prioritize login and upload flow"},
            headers=self.headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["scan"]["instructions"], "Prioritize login and upload flow")

        paused = self.client.post(f"/api/scans/{scan_id}/pause", headers=self.headers)
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json()["scan"]["status"], "paused")

        resumed = self.client.post(f"/api/scans/{scan_id}/resume", headers=self.headers)
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["scan"]["status"], "running")

        approval = self.client.post(
            f"/api/scans/{scan_id}/approvals/request-upload-verification",
            headers=self.headers,
        )
        self.assertEqual(approval.status_code, 200)
        approval_id = approval.json()["approval"]["id"]
        self.assertEqual(approval.json()["scan"]["status"], "awaiting_approval")

        approved = self.client.post(
            f"/api/approvals/{approval_id}/approve",
            json={"note": "Approved for staging"},
            headers=self.headers,
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["approval"]["status"], "approved")

        completed = self.client.post(f"/api/scans/{scan_id}/complete", headers=self.headers)
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["scan"]["status"], "completed")
        self.assertEqual(completed.json()["credits"]["available"], 1)
        self.assertEqual(completed.json()["credits"]["reserved"], 0)
        self.assertEqual(completed.json()["credits"]["consumed"], 1)

        completed_again = self.client.post(f"/api/scans/{scan_id}/complete", headers=self.headers)
        self.assertEqual(completed_again.status_code, 200)
        self.assertEqual(completed_again.json()["credits"]["consumed"], 1)

    def test_execution_queue_drains_passive_scan_over_http(self) -> None:
        scan = self.client.post(
            "/api/scans",
            json={
                "workspace_id": self.workspace_id,
                "project_id": self.project_id,
                "target_id": self.target_id,
                "scan_type": "passive_blackbox",
                "model_profile_id": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(scan.status_code, 200)
        scan_id = scan.json()["scan"]["id"]

        jobs = self.client.get("/api/execution/jobs", headers=self.headers)
        self.assertEqual(jobs.status_code, 200)
        self.assertTrue(any(job["scan_id"] == scan_id for job in jobs.json()["jobs"]))

        drained = self.client.post("/api/execution/drain", headers=self.headers)
        self.assertEqual(drained.status_code, 200)

        detail = self.client.get(f"/api/scans/{scan_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["scan"]["status"], "completed")

    def test_scan_evidence_is_available_to_workspace_members_over_http(self) -> None:
        scan = self.client.post(
            "/api/scans",
            json={
                "workspace_id": self.workspace_id,
                "project_id": self.project_id,
                "target_id": self.target_id,
                "scan_type": "autonomous_blackbox",
                "model_profile_id": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(scan.status_code, 200)
        scan_id = scan.json()["scan"]["id"]
        artifact = EvidenceArtifact(
            scan_id=scan_id,
            artifact_type="browser_dom_snapshot",
            uri=f"evidence://{scan_id}/manual/1",
            summary="Captured DOM",
            content_type="text/html",
            content="<html></html>",
        )
        main.store.add(main.store.evidence_artifacts, artifact)

        evidence = self.client.get(f"/api/scans/{scan_id}/evidence", headers=self.headers)
        self.assertEqual(evidence.status_code, 200)
        self.assertEqual(evidence.json()["evidence"][0]["uri"], artifact.uri)

    def test_failed_scan_releases_reserved_credit_over_http(self) -> None:
        scan = self.client.post(
            "/api/scans",
            json={
                "workspace_id": self.workspace_id,
                "project_id": self.project_id,
                "target_id": self.target_id,
                "scan_type": "autonomous_blackbox",
                "model_profile_id": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(scan.status_code, 200)
        scan_id = scan.json()["scan"]["id"]

        failed = self.client.post(f"/api/scans/{scan_id}/fail", headers=self.headers)
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(failed.json()["scan"]["status"], "failed")
        self.assertEqual(failed.json()["credits"]["available"], 2)
        self.assertEqual(failed.json()["credits"]["reserved"], 0)
        self.assertEqual(failed.json()["credits"]["consumed"], 0)

    def test_passive_scan_report_flow_over_http(self) -> None:
        scan = self.client.post(
            "/api/scans",
            json={
                "workspace_id": self.workspace_id,
                "project_id": self.project_id,
                "target_id": self.target_id,
                "scan_type": "passive_blackbox",
                "model_profile_id": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(scan.status_code, 200)
        scan_id = scan.json()["scan"]["id"]

        run = self.client.post(f"/api/scans/{scan_id}/run-passive", headers=self.headers)
        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["scan"]["status"], "completed")

        findings = self.client.get(f"/api/findings?scan_id={scan_id}", headers=self.headers)
        self.assertEqual(findings.status_code, 200)
        self.assertEqual(len(findings.json()["findings"]), 1)

        report = self.client.post("/api/reports", json={"scan_id": scan_id}, headers=self.headers)
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()["report"]["format"], "json")

        download = self.client.get(f"/api/reports/{report.json()['report']['id']}/download", headers=self.headers)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.json()["scan"]["id"], scan_id)


if __name__ == "__main__":
    unittest.main()
