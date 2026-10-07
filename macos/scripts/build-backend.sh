#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACOS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPOSITORY_DIR="$(cd "$MACOS_DIR/.." && pwd)"
BUILD_ROOT="$MACOS_DIR/.backend-build"
VENV_DIR="$BUILD_ROOT/venv"
DIST_DIR="$BUILD_ROOT/dist"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "The macOS transcription helper must be built on macOS."
    exit 1
fi

PYTHON_BIN="${CURSAY_BACKEND_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
    for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 || true)"; do
        if [[ -x "$candidate" ]] && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
fi
if [[ -z "$PYTHON_BIN" ]] || ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Python 3.10 or newer is required to build the macOS transcription helper."
    exit 1
fi

if [[ -x "$VENV_DIR/bin/python" ]] && ! "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    rm -rf "$VENV_DIR"
fi
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check \
    --require-hashes \
    -r "$REPOSITORY_DIR/backend/requirements.lock"
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check "pyinstaller==6.16.0"

rm -rf "$DIST_DIR" "$BUILD_ROOT/work" "$BUILD_ROOT/CursaySTT.spec"
PYINSTALLER_CONFIG_DIR="$BUILD_ROOT/pyinstaller-cache" "$VENV_DIR/bin/python" -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --name CursaySTT \
    --paths "$REPOSITORY_DIR/backend" \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_ROOT/work" \
    --specpath "$BUILD_ROOT" \
    --collect-all av \
    --collect-all ctranslate2 \
    --collect-all faster_whisper \
    --collect-all huggingface_hub \
    --collect-all tokenizers \
    "$REPOSITORY_DIR/backend/macos_server.py"

test -x "$DIST_DIR/CursaySTT/CursaySTT"
echo "$DIST_DIR/CursaySTT"
