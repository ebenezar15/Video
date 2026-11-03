#!/bin/bash
# Builds build/ClipForge.app (and build/ClipForge.zip) from the Swift package, with the engine bundled inside.
# Usage: macos/scripts/build-app.sh            # release build, ad-hoc signed
#        SIGN_ID="Developer ID Application: …" macos/scripts/build-app.sh   # signed for distribution
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(cd .. && pwd)"
CONFIG="${CONFIG:-release}"
VERSION="$(grep -m1 '^version' "$ROOT/engine/pyproject.toml" | cut -d'"' -f2)"

swift build -c "$CONFIG"
BIN="$(swift build -c "$CONFIG" --show-bin-path)/ClipForge"

APP="build/ClipForge.app"
rm -rf "$APP" build/ClipForge.zip
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/ClipForge"

# the engine source, installed into a private venv on first launch
rsync -a --exclude '__pycache__' --exclude '*.egg-info' --exclude '.pytest_cache' --exclude 'tests' \
  "$ROOT/engine/" "$APP/Contents/Resources/engine/"
# fingerprint of the bundled engine: the app reinstalls its private engine when this changes
(cd "$APP/Contents/Resources/engine" && find . -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256 | cut -c1-16) \
  > "$APP/Contents/Resources/engine/BUILD_ID"

# icon
if python3 -c "import PIL" 2>/dev/null; then
  ICONSET="build/AppIcon.iconset"
  rm -rf "$ICONSET" && mkdir -p "$ICONSET"
  python3 scripts/make_icon.py "$ICONSET"
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
fi

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>ClipForge</string>
  <key>CFBundleDisplayName</key><string>ClipForge</string>
  <key>CFBundleIdentifier</key><string>app.clipforge.mac</string>
  <key>CFBundleExecutable</key><string>ClipForge</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.video</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppTransportSecurity</key>
  <dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
PLIST

codesign --force --deep --options runtime --sign "${SIGN_ID:--}" "$APP"
ditto -c -k --keepParent "$APP" build/ClipForge.zip
echo "Built $APP ($VERSION)"
