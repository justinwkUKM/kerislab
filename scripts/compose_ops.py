from __future__ import annotations

import os
import subprocess
from pathlib import Path


def load_env(path: Path = Path(".env")) -> dict[str, str]:
    values: dict[str, str] = {}
    source = path if path.exists() else Path(".env.example")
    if not source.exists():
        return values
    for raw_line in source.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def env_value(env: dict[str, str], name: str, default: str) -> str:
    return os.getenv(name, env.get(name, default))


def run(command: list[str], *, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, input=stdin, check=True)
