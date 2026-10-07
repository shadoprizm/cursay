"""Entrypoint for the self-contained macOS local transcription helper."""
from __future__ import annotations

import argparse
import os
import threading
import time

import uvicorn

from server import app


def _watch_parent(parent_pid: int) -> None:
    while True:
        if os.getppid() != parent_pid:
            os._exit(0)
        time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()

    threading.Thread(target=_watch_parent, args=(arguments.parent_pid,), daemon=True).start()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=arguments.port,
        workers=1,
        access_log=False,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
