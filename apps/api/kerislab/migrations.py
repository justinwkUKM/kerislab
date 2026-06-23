from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Protocol


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


class MigrationConnection(Protocol):
    def execute(self, sql: str, parameters: tuple = ()) -> object:
        ...

    def executescript(self, sql: str) -> object:
        ...


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def apply_sqlite_migrations(database_path: str | Path) -> list[str]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
        applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()}
        applied_now: list[str] = []
        for file in migration_files():
            version = file.stem
            if version in applied:
                continue
            connection.executescript(file.read_text())
            connection.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            applied_now.append(version)
        connection.commit()
        return applied_now
    finally:
        connection.close()


def apply_postgres_migrations(database_url: str) -> list[str]:
    try:
        import psycopg  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("psycopg is required for PostgreSQL migrations") from exc

    with psycopg.connect(database_url) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
        applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()}
        applied_now: list[str] = []
        for file in migration_files():
            version = file.stem
            if version in applied:
                continue
            connection.execute(file.read_text())
            connection.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            applied_now.append(version)
        connection.commit()
        return applied_now


def apply_configured_migrations() -> list[str]:
    database_url = os.getenv("KERISLAB_DATABASE_URL")
    if database_url:
        return apply_postgres_migrations(database_url)
    sqlite_path = os.getenv("KERISLAB_SQLITE_PATH") or ".kerislab/kerislab.db"
    return apply_sqlite_migrations(sqlite_path)
