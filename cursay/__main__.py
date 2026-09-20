from __future__ import annotations

import argparse

from .app import run, smoke_test
from .diagnostics import print_check, record_test


def main() -> int:
    parser = argparse.ArgumentParser(description="Cursay private dictation for Ubuntu")
    parser.add_argument("--check", action="store_true", help="check desktop and transcription dependencies")
    parser.add_argument("--record-test", action="store_true", help="record briefly and test local Whisper")
    parser.add_argument("--smoke-test", action="store_true", help="construct the native UI without portal prompts")
    args = parser.parse_args()
    if args.check:
        return print_check()
    if args.record_test:
        return record_test()
    if args.smoke_test:
        return smoke_test()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
