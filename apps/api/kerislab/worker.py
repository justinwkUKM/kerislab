from __future__ import annotations

import os
import signal
import socket
import sys
import time

from .services import ScanExecutionService, WorkerStatusService
from .store import create_store


def run_worker() -> None:
    store = create_store()
    engine = ScanExecutionService(store)
    worker_status = WorkerStatusService(store)
    poll_interval = float(os.getenv("KERISLAB_WORKER_POLL_INTERVAL", "2.0"))
    worker_id = os.getenv("KERISLAB_WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}"
    worker_name = os.getenv("KERISLAB_WORKER_NAME", "kerislab-worker")
    processed_jobs = 0
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    while not stopping:
        try:
            worker_status.heartbeat(
                worker_id=worker_id,
                name=worker_name,
                queue_name=engine.redis_queue,
                processed_jobs=processed_jobs,
            )
            processed_jobs += engine.drain_available_jobs()
            worker_status.heartbeat(
                worker_id=worker_id,
                name=worker_name,
                queue_name=engine.redis_queue,
                processed_jobs=processed_jobs,
            )
        except Exception as exc:
            print(f"worker error: {exc}", file=sys.stderr)
            worker_status.heartbeat(
                worker_id=worker_id,
                name=worker_name,
                queue_name=engine.redis_queue,
                processed_jobs=processed_jobs,
                status="error",
                error=str(exc),
            )
        time.sleep(poll_interval)

    worker_status.heartbeat(
        worker_id=worker_id,
        name=worker_name,
        queue_name=engine.redis_queue,
        processed_jobs=processed_jobs,
        status="stopping",
    )


if __name__ == "__main__":
    run_worker()
