import sqlite3
import tempfile
import unittest
from pathlib import Path

from kerislab.migrations import apply_sqlite_migrations


class MigrationTests(unittest.TestCase):
    def test_initial_schema_applies_to_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "kerislab.db"
            applied = apply_sqlite_migrations(db_path)
            self.assertEqual(applied, ["001_initial_platform_schema"])

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

        self.assertIn("users", tables)
        self.assertIn("user_sessions", tables)
        self.assertIn("oauth_states", tables)
        self.assertIn("workspaces", tables)
        self.assertIn("billing_checkout_sessions", tables)
        self.assertIn("billing_invoices", tables)
        self.assertIn("billing_payments", tables)
        self.assertIn("billing_webhook_events", tables)
        self.assertIn("scans", tables)
        self.assertIn("browser_executions", tables)
        self.assertIn("evidence_artifacts", tables)
        self.assertIn("audit_logs", tables)
        self.assertIn("worker_heartbeats", tables)
        self.assertIn("schema_migrations", tables)


if __name__ == "__main__":
    unittest.main()
