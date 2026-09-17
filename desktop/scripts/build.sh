#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
ARCH="${ARCH:-$(uname -m)}"
case "$ARCH" in arm64|x86_64) ;; *) echo "Unsupported architecture" >&2; exit 1 ;; esac
BUILD_TAG="$(date +%Y%m%d-%H%M%S)-$$"
TARGET="$ARCH-apple-macos13.0"
OUT="build/$ARCH"
mkdir -p "$OUT"
SDK="${SDKROOT:-$(xcrun --sdk macosx --show-sdk-path)}"
xcrun clang -target "$TARGET" -isysroot "$SDK" -O2 -I Sources/SGSystem/include -c Sources/SGSystem/system.c -o "$OUT/system.o"
xcrun swiftc -target "$TARGET" -sdk "$SDK" -O -parse-as-library -emit-library -static -emit-module \
  -module-name SeagreenCore -I Sources/SGSystem/include Sources/SeagreenCore/*.swift "$OUT/system.o" \
  -lproc -framework IOKit -emit-module-path "$OUT/SeagreenCore.swiftmodule" \
  -o "$OUT/libSeagreenCore.a"
xcrun swiftc -target "$TARGET" -sdk "$SDK" -O -parse-as-library -I "$OUT" -I Sources/SGSystem/include \
  "$OUT/libSeagreenCore.a" -lproc -framework IOKit -framework SwiftUI -framework AppKit -framework Charts \
  Sources/SeagreenApp/*.swift -o "$OUT/Seagreen"
APP="build/apps/$ARCH-$BUILD_TAG/Seagreen.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Frameworks" "$APP/Contents/Resources"
cp "$OUT/Seagreen" "$APP/Contents/MacOS/Seagreen"
cp Resources/Info.plist "$APP/Contents/Info.plist"
if [ -f Resources/Seagreen.icns ]; then cp Resources/Seagreen.icns "$APP/Contents/Resources/"; fi
IDENTITY="${SIGNING_IDENTITY:--}"
codesign --force --sign "$IDENTITY" --options runtime "$APP"
codesign --verify --deep --strict "$APP"
printf '%s\n' "$APP" > "build/latest-$ARCH-app.txt"
echo "Built $APP ($ARCH). Signing identity: $IDENTITY"
