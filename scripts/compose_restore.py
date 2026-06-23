from __future__ import annotations

import argparse
import subprocess
from shlex import quote
from pathlib import Path

from compose_ops import env_value, load_env, run


def restore_postgres(env: dict[str, str], restore_dir: Path) -> None:
    db_name = env_value(env, "KERISLAB_POSTGRES_DB", "kerislab")
    db_user = env_value(env, "KERISLAB_POSTGRES_USER", "kerislab")
    sql_path = restore_dir / "postgres.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"missing PostgreSQL dump: {sql_path}")
    with sql_path.open("rb") as handle:
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "--set",
                "ON_ERROR_STOP=on",
                "-U",
                db_user,
                "-d",
                db_name,
            ],
            check=True,
            stdin=handle,
        )


def restore_minio(env: dict[str, str], restore_dir: Path) -> None:
    bucket = env_value(env, "KERISLAB_OBJECT_STORAGE_BUCKET", "kerislab-evidence")
    minio_user = env_value(env, "KERISLAB_MINIO_ROOT_USER", "kerislab")
    minio_password = env_value(env, "KERISLAB_MINIO_ROOT_PASSWORD", "kerislab_change_me")
    minio_backup = restore_dir / "minio" / bucket
    if not minio_backup.exists():
        raise FileNotFoundError(f"missing MinIO backup directory: {minio_backup}")
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
            f"{restore_dir.resolve()}:/backup",
            "--entrypoint",
            "/bin/sh",
            "minio-init",
            "-c",
            (
                f"{alias_command} && "
                f"mc mb --ignore-existing {quote(f'kerislab/{bucket}')} && "
                f"mc mirror --overwrite {quote(f'/backup/minio/{bucket}')} {quote(f'kerislab/{bucket}')}"
            ),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a KerisLab Docker Compose backup.")
    parser.add_argument("restore_dir", help="Backup directory created by scripts/compose_backup.py.")
    args = parser.parse_args()

    restore_dir = Path(args.restore_dir)
    if not restore_dir.exists():
        raise FileNotFoundError(f"restore directory does not exist: {restore_dir}")
    env = load_env()
    restore_postgres(env, restore_dir)
    restore_minio(env, restore_dir)
    print(f"restore completed from {restore_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
