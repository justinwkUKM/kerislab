from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REQUIRED_TEXT = (
    "VITE_API_BASE_URL: /api",
    "KERISLAB_GOOGLE_REDIRECT_URI: http://localhost:5173/api/auth/oidc/callback",
    "KERISLAB_SSO_REDIRECT_URI: http://localhost:5173/api/auth/oidc/callback",
    "condition: service_healthy",
    "KERISLAB_REDIS_URL: redis://redis:6379/0",
    "KERISLAB_OBJECT_STORAGE_ENDPOINT: http://minio:9000",
)

DEFAULT_SECRET_NAMES = (
    "KERISLAB_POSTGRES_PASSWORD",
    "KERISLAB_MINIO_ROOT_PASSWORD",
    "LITELLM_MASTER_KEY",
    "KERISLAB_BILLING_WEBHOOK_SECRET",
)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def run_compose_config() -> str:
    result = subprocess.run(
        ["docker", "compose", "config"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


def check_required_text(rendered_config: str) -> list[str]:
    return [text for text in REQUIRED_TEXT if text not in rendered_config]


def check_default_secrets(env_values: dict[str, str]) -> list[str]:
    unsafe_values = {"", "change-me", "kerislab_change_me", "sk-kerislab-local", "kerislab-webhook-secret"}
    warnings: list[str] = []
    for name in DEFAULT_SECRET_NAMES:
        value = os.getenv(name, env_values.get(name, ""))
        if value in unsafe_values:
            warnings.append(f"{name} is still using a local-development value")
    return warnings


def main() -> int:
    rendered_config = run_compose_config()
    missing = check_required_text(rendered_config)
    if missing:
        for text in missing:
            print(f"preflight failed: rendered Compose config is missing {text!r}", file=sys.stderr)
        return 1

    env_values = load_env(Path(".env")) or load_env(Path(".env.example"))
    for warning in check_default_secrets(env_values):
        print(f"preflight warning: {warning}")

    print("preflight ok: Compose config, web proxy, OAuth callbacks, Redis, and object storage are aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
