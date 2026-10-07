#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MACOS_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
VERSION=${CURSAY_VERSION:?CURSAY_VERSION is required}
PRIVATE_KEY=${SPARKLE_PRIVATE_KEY_FILE:?SPARKLE_PRIVATE_KEY_FILE is required}
ARCHIVE="$MACOS_DIR/dist/Cursay-$VERSION-macos.zip"
TOOL=$(find "$MACOS_DIR/.build" -type f -name generate_appcast -perm +111 -print -quit)

if [[ -z "$TOOL" ]]; then
    echo "Sparkle generate_appcast tool was not found."
    exit 1
fi

"$TOOL" \
    --ed-key-file "$PRIVATE_KEY" \
    --download-url-prefix "https://github.com/shadoprizm/cursay/releases/download/v$VERSION/" \
    "$MACOS_DIR/dist"

test -s "$MACOS_DIR/dist/appcast.xml"
grep -q "Cursay-$VERSION-macos.zip" "$MACOS_DIR/dist/appcast.xml"
echo "Generated signed appcast for $ARCHIVE"
