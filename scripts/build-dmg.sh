#!/usr/bin/env bash
# Build VoiceText.app with PyInstaller, re-sign, and package as DMG.
# Usage: ./scripts/build-dmg.sh [version]
# Example: ./scripts/build-dmg.sh 0.1.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"
APP_PATH="$DIST_DIR/VoiceText.app"
SIGN_IDENTITY="${CODESIGN_IDENTITY:-VoiceText Dev}"

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    # Try to extract from git tag
    VERSION=$(git -C "$PROJECT_DIR" describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo "")
fi
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.1.0"
    exit 1
fi

DMG_PATH="$DIST_DIR/VoiceText-${VERSION}-arm64.dmg"

cd "$PROJECT_DIR"

echo "==> Building VoiceText v${VERSION}..."

echo "==> Updating version in spec..."
sed -i '' "s/'CFBundleVersion': '.*'/'CFBundleVersion': '${VERSION}'/" VoiceText.spec
sed -i '' "s/'CFBundleShortVersionString': '.*'/'CFBundleShortVersionString': '${VERSION}'/" VoiceText.spec

echo "==> Cleaning previous build..."
rm -rf build dist

echo "==> Running PyInstaller..."
uv run pyinstaller VoiceText.spec --clean --noconfirm

echo "==> Re-signing app bundle (identity: $SIGN_IDENTITY)..."
codesign --force --deep --sign "$SIGN_IDENTITY" "$APP_PATH"

echo "==> Verifying signature..."
codesign --verify --verbose "$APP_PATH"

echo "==> Creating DMG..."
DMG_DIR=$(mktemp -d)
cp -R "$APP_PATH" "$DMG_DIR/"
ln -s /Applications "$DMG_DIR/Applications"
hdiutil create -volname "VoiceText" \
    -srcfolder "$DMG_DIR" \
    -ov -format UDZO \
    "$DMG_PATH"
rm -rf "$DMG_DIR"

APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
DMG_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
echo ""
echo "==> Build complete!"
echo "    App: $APP_PATH ($APP_SIZE)"
echo "    DMG: $DMG_PATH ($DMG_SIZE)"
echo "    Run with: open $APP_PATH"
