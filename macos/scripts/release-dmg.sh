#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MACOS_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
VERSION=${CURSAY_VERSION:?CURSAY_VERSION is required}
IDENTITY=${CURSAY_CODESIGN_IDENTITY:?CURSAY_CODESIGN_IDENTITY is required}
DIST_DIR="$MACOS_DIR/dist"
APP_DIR="$DIST_DIR/Cursay.app"
DMG_PATH="$DIST_DIR/Cursay-$VERSION-macos.dmg"
ZIP_PATH="$DIST_DIR/Cursay-$VERSION-macos.zip"

CURSAY_RELEASE=1 "$SCRIPT_DIR/build-app.sh"

rm -f "$DMG_PATH" "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_DIR" "$ZIP_PATH"

notarize() {
    local artifact=$1
    if [[ -n "${APPLE_NOTARY_KEYCHAIN_PROFILE:-}" ]]; then
        xcrun notarytool submit "$artifact" --keychain-profile "$APPLE_NOTARY_KEYCHAIN_PROFILE" --wait
    else
        xcrun notarytool submit "$artifact" \
            --apple-id "${APPLE_ID:?APPLE_ID is required}" \
            --password "${APPLE_APP_SPECIFIC_PASSWORD:?APPLE_APP_SPECIFIC_PASSWORD is required}" \
            --team-id "${APPLE_TEAM_ID:?APPLE_TEAM_ID is required}" \
            --wait
    fi
}

# Notarize and staple the app itself before packaging it. This keeps Gatekeeper
# verification available even when the Mac is offline after installation.
notarize "$ZIP_PATH"
xcrun stapler staple "$APP_DIR"
xcrun stapler validate "$APP_DIR"
rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_DIR" "$ZIP_PATH"

STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT
ditto "$APP_DIR" "$STAGING/Cursay.app"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "Cursay" -srcfolder "$STAGING" -ov -format UDZO "$DMG_PATH"
codesign --force --timestamp --sign "$IDENTITY" "$DMG_PATH"

notarize "$DMG_PATH"
xcrun stapler staple "$DMG_PATH"
xcrun stapler validate "$DMG_PATH"
spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG_PATH"
shasum -a 256 "$DMG_PATH" > "$DMG_PATH.sha256"
shasum -a 256 "$ZIP_PATH" > "$ZIP_PATH.sha256"
echo "Created notarized release artifacts in $DIST_DIR"
