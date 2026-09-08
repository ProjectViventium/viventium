#!/usr/bin/env python3
"""Host the existing Scheduling Cortex on the installed private socket."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


def main() -> None:
    package, socket_path = Path(sys.argv[1]), sys.argv[2]
    sys.path[:0] = [str(package), str(package / "site-packages")]
    import uvicorn
    from scheduling_cortex.server import build_server
    from scheduling_cortex.scheduler import SchedulerEngine
    from scheduling_cortex.storage import ScheduleStorage, StorageConfig

    os.umask(0o077)
    storage = ScheduleStorage(StorageConfig(db_path=os.environ["SCHEDULING_DB_PATH"]))
    scheduler = SchedulerEngine(storage,
        int(os.getenv("SCHEDULER_POLL_INTERVAL_S", "30")),
        int(os.getenv("SCHEDULER_MISFIRE_GRACE_S", "900")),
        int(os.getenv("SCHEDULER_RETRY_DELAY_S", "300")),
        int(os.getenv("SCHEDULER_CATCH_UP_MAX_LATE_S", "43200")))
    app = build_server(storage).http_app()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(socket_path)
        os.chmod(socket_path, 0o600)
        scheduler.start()
        try:
            uvicorn.Server(uvicorn.Config(app, uds=socket_path, http="h11", access_log=False)).run(sockets=[listener])
        finally:
            scheduler.stop()


if __name__ == "__main__":
    main()
