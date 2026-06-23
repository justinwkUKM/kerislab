import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kerislab.models import AuthProvider, ScanJobType, ScanType
from kerislab.services import AuthService, ProjectService, ScanExecutionService, ScanService, WorkerStatusService, WorkspaceService
from kerislab.store import InMemoryStore, SQLiteStore, create_store


class SQLiteStoreTests(unittest.TestCase):
    def test_state_survives_store_recreation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "kerislab.db"

            store = SQLiteStore(db_path)
            user = AuthService(store).login_identity(
                email="owner@example.com",
                display_name="Owner",
                provider=AuthProvider.GOOGLE,
            )
            workspace = WorkspaceService(store).create_workspace(
                name="Workspace",
                owner=user,
                initial_credits=3,
            )
            WorkerStatusService(store).heartbeat(
                worker_id="worker-1",
                name="kerislab-test-worker",
                queue_name="kerislab:scan-jobs",
                processed_jobs=2,
            )

            restored = SQLiteStore(db_path)
            self.assertIn(user.id, restored.users)
            self.assertEqual(restored.user_settings[user.id].default_workspace_id, workspace.id)
            self.assertEqual(restored.credit_accounts[workspace.id].available, 3)
            self.assertEqual(restored.worker_heartbeats["worker-1"].processed_jobs, 2)

    def test_create_store_uses_sqlite_without_postgres_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "kerislab.db"
            with patch.dict("os.environ", {"KERISLAB_SQLITE_PATH": str(db_path)}, clear=True):
                store = create_store()
        self.assertIsInstance(store, SQLiteStore)

    def test_create_store_applies_sqlite_migrations_before_opening_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "kerislab.db"
            store = create_store(sqlite_path=db_path)
            store.sync()

            import sqlite3

            connection = sqlite3.connect(db_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            finally:
                connection.close()

        self.assertIn("schema_migrations", tables)
        self.assertIn("users", tables)
        self.assertIn("store_entities", tables)

    def test_create_store_falls_back_to_sqlite_when_postgres_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "kerislab.db"
            with patch("os.getenv", side_effect=lambda key, default=None: {"KERISLAB_SQLITE_PATH": str(db_path)}.get(key, default)):
                store = create_store(database_url="postgresql://invalid")
        self.assertIsInstance(store, SQLiteStore)

    def test_create_store_falls_back_to_memory_if_sqlite_fails(self) -> None:
        with patch("kerislab.store.SQLiteStore", side_effect=RuntimeError("sqlite down")):
            store = create_store(database_url=None, sqlite_path="/tmp/kerislab.db")
        self.assertIsInstance(store, InMemoryStore)

    def test_persisted_scan_job_can_be_drained_by_fresh_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "kerislab.db"
            store = SQLiteStore(db_path)
            user = AuthService(store).login_identity(
                email="owner@example.com",
                display_name="Owner",
                provider=AuthProvider.GOOGLE,
            )
            workspace = WorkspaceService(store).create_workspace(
                name="Workspace",
                owner=user,
                initial_credits=1,
            )
            project = ProjectService(store).create_project(workspace_id=workspace.id, name="Project")
            target = ProjectService(store).create_target(
                workspace_id=workspace.id,
                project_id=project.id,
                name="Example",
                url="https://example.com",
            )
            scan = ScanService(store).create_scan(
                workspace_id=workspace.id,
                project_id=project.id,
                target_id=target.id,
                scan_type=ScanType.PASSIVE_BLACKBOX,
                model_profile_id="default",
            )
            ScanExecutionService(store).enqueue(scan.id, ScanJobType.PASSIVE_SCAN)

            worker_store = SQLiteStore(db_path)
            drained = ScanExecutionService(worker_store).drain_persisted_jobs()

        self.assertEqual(drained, 1)
        self.assertEqual(worker_store.scans[scan.id].status, "completed")


if __name__ == "__main__":
    unittest.main()
