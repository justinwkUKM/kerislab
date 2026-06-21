import unittest

try:
    from kerislab import main
except RuntimeError as exc:
    main = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

from kerislab.models import AuthProvider, ScanType


@unittest.skipIf(main is None, f"FastAPI dependencies unavailable: {IMPORT_ERROR}")
class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        main.store = main.InMemoryStore()
        login = main.dev_login(
            main.LoginRequest(
                email="owner@example.com",
                display_name="Owner",
                provider=AuthProvider.GOOGLE,
            )
        )
        self.user_id = login["user"]["id"]
        workspace_result = main.create_workspace(
            main.WorkspaceCreate(name="Workspace", initial_credits=3),
            user_id=self.user_id,
        )
        self.workspace_id = workspace_result["workspace"]["id"]
        project_result = main.create_project(
            main.ProjectCreate(workspace_id=self.workspace_id, name="Project"),
            self.user_id,
        )
        self.project_id = project_result["project"]["id"]
        target_result = main.create_target(
            main.TargetCreate(
                workspace_id=self.workspace_id,
                project_id=self.project_id,
                name="Example",
                url="https://example.com",
            ),
            self.user_id,
        )
        self.target_id = target_result["target"]["id"]

    def test_auth_me_contract_includes_settings_and_memberships(self) -> None:
        result = main.auth_me(self.user_id)
        self.assertEqual(result["user"]["email"], "owner@example.com")
        self.assertIn("settings", result)
        self.assertEqual(len(result["memberships"]), 1)

    def test_scan_credit_and_autonomous_approval_contract(self) -> None:
        scan_result = main.create_scan(
            main.ScanCreate(
                workspace_id=self.workspace_id,
                project_id=self.project_id,
                target_id=self.target_id,
                scan_type=ScanType.AUTONOMOUS_BLACKBOX,
                model_profile_id="default",
            ),
            self.user_id,
        )
        scan_id = scan_result["scan"]["id"]
        self.assertEqual(scan_result["credits"]["available"], 2)

        plan_result = main.start_autonomous(scan_id, self.user_id)
        self.assertEqual(plan_result["scan"]["status"], "running")

        browser_plan = main.browser_plan(scan_id, self.user_id)
        self.assertEqual(browser_plan["browser_plan"]["engine"], "playwright")
        self.assertTrue(any(action["requires_approval"] for action in browser_plan["browser_plan"]["actions"]))

        approval_result = main.request_upload_verification(scan_id, self.user_id)
        approval_id = approval_result["approval"]["id"]
        self.assertEqual(approval_result["scan"]["status"], "awaiting_approval")

        resolved = main.approve_request(
            approval_id,
            main.ApprovalDecision(note="Approved"),
            self.user_id,
        )
        self.assertEqual(resolved["approval"]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
