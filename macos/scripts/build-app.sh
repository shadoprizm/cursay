#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACOS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPOSITORY_DIR="$(cd "$MACOS_DIR/.." && pwd)"
BUILD_DIR="$MACOS_DIR/dist"
APP_DIR="$BUILD_DIR/Cursay.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_CONTENTS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Cursay.app must be built on macOS with Xcode 15 or newer installed."
    exit 1
fi

if ! command -v xcrun >/dev/null 2>&1; then
    echo "Xcode Command Line Tools are required. Run: xcode-select --install"
    exit 1
fi

cd "$MACOS_DIR"
swift test
swift build -c release --product Cursay
BIN_DIR="$(swift build -c release --show-bin-path)"

if [[ -d "$APP_DIR" ]]; then
    rm -rf "$APP_DIR"
fi
mkdir -p "$MACOS_CONTENTS_DIR" "$RESOURCES_DIR"
cp "$BIN_DIR/Cursay" "$MACOS_CONTENTS_DIR/Cursay"
cp "$MACOS_DIR/Resources/Info.plist" "$CONTENTS_DIR/Info.plist"

ICON_SOURCE="$REPOSITORY_DIR/assets/cursay.svg"
if [[ -f "$ICON_SOURCE" ]]; then
    ICON_TEMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$ICON_TEMP_DIR"' EXIT
    qlmanage -t -s 1024 -o "$ICON_TEMP_DIR" "$ICON_SOURCE" >/dev/null 2>&1
    ICON_BASE="$ICON_TEMP_DIR/$(basename "$ICON_SOURCE").png"
    ICONSET_DIR="$ICON_TEMP_DIR/Cursay.iconset"
    if [[ -f "$ICON_BASE" ]]; then
        mkdir -p "$ICONSET_DIR"
        sips -z 16 16 "$ICON_BASE" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
        sips -z 32 32 "$ICON_BASE" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
        sips -z 32 32 "$ICON_BASE" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
        sips -z 64 64 "$ICON_BASE" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
        sips -z 128 128 "$ICON_BASE" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
        sips -z 256 256 "$ICON_BASE" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
        sips -z 256 256 "$ICON_BASE" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
        sips -z 512 512 "$ICON_BASE" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
        sips -z 512 512 "$ICON_BASE" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
        cp "$ICON_BASE" "$ICONSET_DIR/icon_512x512@2x.png"
        iconutil -c icns "$ICONSET_DIR" -o "$RESOURCES_DIR/Cursay.icns"
    fi
fi

plutil -lint "$CONTENTS_DIR/Info.plist"

# An ad-hoc signature is enough for running the local development build. A
# Developer ID signature and notarization should replace this for distribution.
codesign --force --deep --sign - "$APP_DIR"

echo "Built $APP_DIR"
echo "Open it with: open '$APP_DIR'"
