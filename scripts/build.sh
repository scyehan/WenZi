#!/usr/bin/env bash
# Build VoiceText.app with PyInstaller and re-sign for macOS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"
APP_PATH="$DIST_DIR/VoiceText.app"
SIGN_IDENTITY="${CODESIGN_IDENTITY:-VoiceText Dev}"

# Check if the signing identity exists in the keychain
if security find-identity -v -p codesigning | grep -q "$SIGN_IDENTITY"; then
    SIGN_MODE="identity"
else
    echo "WARNING: Signing identity '$SIGN_IDENTITY' not found in keychain, falling back to ad-hoc signing."
    SIGN_MODE="adhoc"
fi

cd "$PROJECT_DIR"

echo "==> Cleaning previous build..."
rm -rf build dist

echo "==> Running PyInstaller..."
uv run pyinstaller VoiceText.spec --clean --noconfirm

if [ "$SIGN_MODE" = "identity" ]; then
    echo "==> Re-signing app bundle (identity: $SIGN_IDENTITY)..."
    codesign --force --deep --sign "$SIGN_IDENTITY" "$APP_PATH"
else
    echo "==> Re-signing app bundle (ad-hoc)..."
    codesign --force --deep --sign - "$APP_PATH"
fi

echo "==> Verifying signature..."
codesign --verify --verbose "$APP_PATH"

APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
echo ""
echo "==> Build complete: $APP_PATH ($APP_SIZE)"
echo "    Run with: open $APP_PATH"
