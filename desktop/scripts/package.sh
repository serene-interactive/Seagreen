#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=3.0.1
HOST_ARCH="$(uname -m)"
if [ ! -f "build/latest-$HOST_ARCH-app.txt" ]; then echo "Run scripts/build.sh first." >&2; exit 1; fi
SOURCE_APP="$(cat "build/latest-$HOST_ARCH-app.txt")"
if [ ! -x "$SOURCE_APP/Contents/MacOS/Seagreen" ]; then echo "Latest app is missing." >&2; exit 1; fi
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
APP="$STAGING/Seagreen.app"
ditto "$SOURCE_APP" "$APP"
mkdir -p build/releases
if [ -f build/arm64/Seagreen ] && [ -f build/x86_64/Seagreen ]; then
  lipo -create build/arm64/Seagreen build/x86_64/Seagreen -output "$APP/Contents/MacOS/Seagreen"
  FLAVOR=universal
else
  FLAVOR="$(uname -m)"
fi
codesign --force --sign "${SIGNING_IDENTITY:--}" --options runtime "$APP"
codesign --verify --deep --strict "$APP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "build/releases/Seagreen-v$VERSION-macOS-$FLAVOR.zip"
ln -s /Applications "$STAGING/Applications"
printf 'Seagreen v3.0.1\n\nDrag Seagreen into Applications. Requires macOS 13 or later.\n\nThis build is signed locally, not notarized by Apple. Gatekeeper may require an explicit Open Anyway action in Privacy & Security. No administrator access is required for ordinary monitoring.\n' > "$STAGING/Read Me.txt"
hdiutil create -volname "Seagreen v$VERSION" -srcfolder "$STAGING" -ov -format UDZO "build/releases/Seagreen-v$VERSION-macOS-$FLAVOR.dmg"
shasum -a 256 build/releases/*.zip build/releases/*.dmg > build/releases/SHA256SUMS.txt
echo "Packages are in desktop/build/releases."
