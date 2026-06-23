from __future__ import annotations

import argparse
import subprocess
from shlex import quote
from datetime import UTC, datetime
from pathlib import Path

from compose_ops import env_value, load_env, run


def dump_postgres(env: dict[str, str], backup_dir: Path) -> None:
    db_name = env_value(env, "KERISLAB_POSTGRES_DB", "kerislab")
    db_user = env_value(env, "KERISLAB_POSTGRES_USER", "kerislab")
    output = backup_dir / "postgres.sql"
    with output.open("wb") as handle:
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "--clean",
                "--if-exists",
                "-U",
                db_user,
                "-d",
                db_name,
            ],
            check=True,
            stdout=handle,
        )


def mirror_minio(env: dict[str, str], backup_dir: Path) -> None:
    bucket = env_value(env, "KERISLAB_OBJECT_STORAGE_BUCKET", "kerislab-evidence")
    minio_user = env_value(env, "KERISLAB_MINIO_ROOT_USER", "kerislab")
    minio_password = env_value(env, "KERISLAB_MINIO_ROOT_PASSWORD", "kerislab_change_me")
    backup_dir.mkdir(parents=True, exist_ok=True)
    alias_command = " ".join(
        [
            "mc",
            "alias",
            "set",
            "kerislab",
            "http://minio:9000",
            quote(minio_user),
            quote(minio_password),
        ]
    )
    run(
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "--volume",
            f"{backup_dir.resolve()}:/backup",
            "--entrypoint",
            "/bin/sh",
            "minio-init",
            "-c",
            (
                f"{alias_command} && "
                f"mkdir -p /backup/minio && "
                f"mc mirror --overwrite {quote(f'kerislab/{bucket}')} {quote(f'/backup/minio/{bucket}')}"
            ),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up the KerisLab Docker Compose deployment.")
    parser.add_argument("--backup-root", default="backups", help="Directory where timestamped backups are stored.")
    args = parser.parse_args()

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(args.backup_root) / f"kerislab-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    env = load_env()

    dump_postgres(env, backup_dir)
    mirror_minio(env, backup_dir)
    print(f"backup written to {backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
