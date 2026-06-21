import unittest

from fastapi.testclient import TestClient

from kerislab import main
from kerislab.store import InMemoryStore


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

        me = self.client.get("/api/auth/me", headers=self.headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], "owner@example.com")
        self.assertIn("settings", me.json())

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

        browser_plan = self.client.get(f"/api/scans/{scan_id}/browser-plan", headers=self.headers)
        self.assertEqual(browser_plan.status_code, 200)
        self.assertEqual(browser_plan.json()["browser_plan"]["engine"], "playwright")
        self.assertTrue(
            any(action["requires_approval"] for action in browser_plan.json()["browser_plan"]["actions"])
        )

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


if __name__ == "__main__":
    unittest.main()
