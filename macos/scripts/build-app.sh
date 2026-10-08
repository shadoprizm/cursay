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
FRAMEWORKS_DIR="$CONTENTS_DIR/Frameworks"
ENTITLEMENTS="$MACOS_DIR/Resources/Cursay.entitlements"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Cursay.app must be built on macOS with Xcode 15 or newer installed."
    exit 1
fi

if ! command -v xcrun >/dev/null 2>&1; then
    echo "Xcode Command Line Tools are required. Run: xcode-select --install"
    exit 1
fi

cd "$MACOS_DIR"
if swift -e 'import XCTest' >/dev/null 2>&1; then
    swift test
else
    echo "Warning: XCTest is unavailable in the selected developer toolchain; skipping Swift tests."
    echo "Install and select full Xcode to enable them."
fi
swift build -c release --product Cursay
BIN_DIR="$(swift build -c release --show-bin-path)"
BACKEND_HELPER_DIR="$("$SCRIPT_DIR/build-backend.sh" | tail -n 1)"

if [[ -d "$APP_DIR" ]]; then
    rm -rf "$APP_DIR"
fi
mkdir -p "$MACOS_CONTENTS_DIR" "$RESOURCES_DIR" "$FRAMEWORKS_DIR"
cp "$BIN_DIR/Cursay" "$MACOS_CONTENTS_DIR/Cursay"
# SwiftPM links Sparkle through @rpath but does not add an application-bundle
# Frameworks search path to a standalone executable copied out of .build.
install_name_tool -add_rpath '@executable_path/../Frameworks' "$MACOS_CONTENTS_DIR/Cursay"
cp "$MACOS_DIR/Resources/Info.plist" "$CONTENTS_DIR/Info.plist"
ditto "$BACKEND_HELPER_DIR" "$RESOURCES_DIR/CursaySTT"

SPARKLE_FRAMEWORK=$(find "$MACOS_DIR/.build" -type d -name Sparkle.framework -print -quit)
if [[ -z "$SPARKLE_FRAMEWORK" ]]; then
    echo "Sparkle.framework was not produced by SwiftPM."
    exit 1
fi
ditto "$SPARKLE_FRAMEWORK" "$FRAMEWORKS_DIR/Sparkle.framework"

if [[ -n "${CURSAY_VERSION:-}" ]]; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $CURSAY_VERSION" "$CONTENTS_DIR/Info.plist"
    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${CURSAY_BUILD_NUMBER:-1}" "$CONTENTS_DIR/Info.plist"
fi
if [[ -n "${CURSAY_SPARKLE_PUBLIC_KEY:-}" ]]; then
    /usr/libexec/PlistBuddy -c "Set :SUPublicEDKey $CURSAY_SPARKLE_PUBLIC_KEY" "$CONTENTS_DIR/Info.plist"
fi

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

# Prefer a stable Apple Development identity when one is installed. macOS ties
# Accessibility consent to the app's signing requirement, so ad-hoc signing on
# every rebuild can make an already approved development app untrusted again.
SIGNING_IDENTITY="${CURSAY_CODESIGN_IDENTITY:-}"
if [[ -z "$SIGNING_IDENTITY" ]]; then
    SIGNING_IDENTITY="$(
        security find-identity -v -p codesigning 2>/dev/null \
            | sed -n 's/.*"\(Apple Development:[^"]*\)".*/\1/p' \
            | head -n 1
    )"
fi
if [[ "${CURSAY_RELEASE:-0}" == "1" && -z "$SIGNING_IDENTITY" ]]; then
    echo "CURSAY_CODESIGN_IDENTITY is required for a release build."
    exit 1
fi
if [[ "${CURSAY_RELEASE:-0}" == "1" && -z "${CURSAY_SPARKLE_PUBLIC_KEY:-}" ]]; then
    echo "CURSAY_SPARKLE_PUBLIC_KEY is required for a release build."
    exit 1
fi

sign_helper_binaries() {
    local identity=$1
    local options=()
    if [[ "$identity" != "-" ]]; then
        options+=(--options runtime)
        if [[ "${CURSAY_RELEASE:-0}" == "1" ]]; then
            options+=(--timestamp)
        fi
    fi
    while IFS= read -r -d '' candidate; do
        if file "$candidate" | grep -q 'Mach-O'; then
            if (( ${#options[@]} > 0 )); then
                codesign --force "${options[@]}" --sign "$identity" "$candidate" || return 1
            else
                codesign --force --sign "$identity" "$candidate" || return 1
            fi
        fi
    done < <(find "$RESOURCES_DIR/CursaySTT" -type f -print0)
    while IFS= read -r -d '' framework; do
        if (( ${#options[@]} > 0 )); then
            codesign --force "${options[@]}" --sign "$identity" "$framework" || return 1
        else
            codesign --force --sign "$identity" "$framework" || return 1
        fi
    done < <(find "$RESOURCES_DIR/CursaySTT" -type d -name '*.framework' -print0)
}

ad_hoc_sign() {
    sign_helper_binaries -
    codesign --force --deep --sign - "$FRAMEWORKS_DIR/Sparkle.framework"
    codesign --force --sign - \
        --requirements '=designated => identifier "io.github.shadoprizm.Cursay"' \
        "$APP_DIR"
}

developer_sign() {
    sign_helper_binaries "$SIGNING_IDENTITY" || return 1
    local framework_args=(--force --deep --options runtime --sign "$SIGNING_IDENTITY")
    local app_args=(
        --force
        --options runtime
        --entitlements "$ENTITLEMENTS"
        --sign "$SIGNING_IDENTITY"
    )
    if [[ "${CURSAY_RELEASE:-0}" == "1" ]]; then
        framework_args+=(--timestamp)
        app_args+=(--timestamp)
    fi
    codesign "${framework_args[@]}" "$FRAMEWORKS_DIR/Sparkle.framework" || return 1
    codesign "${app_args[@]}" "$APP_DIR" || return 1
}

if [[ -z "$SIGNING_IDENTITY" ]]; then
    echo "No Apple Development identity found; using a stable local development requirement."
    ad_hoc_sign
else
    if ! developer_sign; then
        if [[ "${CURSAY_RELEASE:-0}" == "1" ]]; then
            echo "Developer ID signing failed."
            exit 1
        fi
        echo "The selected signing identity was unavailable; using a stable local development requirement."
        ad_hoc_sign
    fi
fi

codesign --verify --strict --verbose=2 "$APP_DIR"
codesign --verify --deep --strict --verbose=2 "$FRAMEWORKS_DIR/Sparkle.framework"
while IFS= read -r -d '' candidate; do
    if file "$candidate" | grep -q 'Mach-O'; then
        codesign --verify --strict --verbose=2 "$candidate"
    fi
done < <(find "$RESOURCES_DIR/CursaySTT" -type f -print0)
while IFS= read -r -d '' framework; do
    codesign --verify --strict --verbose=2 "$framework"
done < <(find "$RESOURCES_DIR/CursaySTT" -type d -name '*.framework' -print0)

if [[ "${CURSAY_RELEASE:-0}" == "1" ]]; then
    codesign -dv --verbose=4 "$APP_DIR" 2>&1 | grep -q 'flags=.*runtime'
fi

echo "Built $APP_DIR"
echo "Open it with: open '$APP_DIR'"
