"""PyInstaller entry point for the bundled Windows speech service."""
from __future__ import annotations

import multiprocessing

import uvicorn

from server import app


def main() -> None:
    multiprocessing.freeze_support()
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
