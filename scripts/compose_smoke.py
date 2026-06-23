from __future__ import annotations

import sys
import os
import time
from dataclasses import dataclass
from pathlib import Path
import urllib.request


@dataclass(frozen=True)
class HttpCheck:
    name: str
    urls: tuple[str, ...]
    expected_text: tuple[str, ...] = ()


def env_port(name: str, default: str) -> str:
    return os.getenv(name, default)


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def checks() -> tuple[HttpCheck, ...]:
    web_port = env_port("KERISLAB_WEB_PORT", "5173")
    api_port = env_port("KERISLAB_API_PORT", "8000")
    minio_port = env_port("KERISLAB_MINIO_PORT", "9000")
    litellm_port = env_port("KERISLAB_LITELLM_PORT", "4000")
    return (
        HttpCheck("web", (f"http://localhost:{web_port}/",), ("KerisLab",)),
        HttpCheck("web-api-proxy", (f"http://localhost:{web_port}/api/health",), ("kerislab-api",)),
        HttpCheck("api", (f"http://localhost:{api_port}/api/health",), ("kerislab-api",)),
        HttpCheck("worker", (f"http://localhost:{api_port}/api/health/components",), ("worker_heartbeat", '"status":"ok"')),
        HttpCheck("minio", (f"http://localhost:{minio_port}/minio/health/ready",)),
        HttpCheck(
            "litellm",
            (
                f"http://localhost:{litellm_port}/health/liveliness",
                f"http://localhost:{litellm_port}/health/readiness",
                f"http://localhost:{litellm_port}/health",
            ),
        ),
    )


def request_ok(check: HttpCheck) -> tuple[bool, str | None]:
    last_error: str | None = None
    for url in check.urls:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                body = response.read().decode(errors="replace")
                if response.status < 200 or response.status >= 300:
                    last_error = f"{url} returned HTTP {response.status}"
                    continue
                missing = [text for text in check.expected_text if text not in body]
                if missing:
                    last_error = f"{url} did not include {missing!r}"
                    continue
                return True, None
        except Exception as exc:
            last_error = f"{url}: {exc}"
    return False, last_error


def wait_for(check: HttpCheck) -> tuple[bool, str | None]:
    last_error: str | None = None
    for _ in range(60):
        ok, error = request_ok(check)
        if ok:
            print(f"{check.name}: ok")
            return True, None
        last_error = error
        time.sleep(2)
    return False, last_error


def main() -> int:
    load_dotenv()
    for check in checks():
        ok, error = wait_for(check)
        if not ok:
            print(f"{check.name}: failed: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
