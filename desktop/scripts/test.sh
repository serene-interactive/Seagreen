#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
ARCH="${ARCH:-$(uname -m)}"
SDK="${SDKROOT:-$(xcrun --sdk macosx --show-sdk-path)}"
OUT="build/$ARCH"
mkdir -p "$OUT/tests"
cp scripts/TestMain.swift "$OUT/tests/main.swift"
xcrun swiftc -D STANDALONE_TESTS -target "$ARCH-apple-macos13.0" -sdk "$SDK" -I "$OUT" -I Sources/SGSystem/include \
  -framework IOKit -lproc "$OUT/libSeagreenCore.a" scripts/StandaloneAssertions.swift \
  Tests/SeagreenCoreTests/*.swift "$OUT/tests/main.swift" -o "$OUT/tests/SeagreenTests"
"$OUT/tests/SeagreenTests"
xcrun swiftc -parse-as-library -target "$ARCH-apple-macos13.0" -sdk "$SDK" -I "$OUT" -I Sources/SGSystem/include \
  -framework AppKit -framework IOKit -lproc "$OUT/libSeagreenCore.a" \
  Sources/SeagreenApp/ProcessControl.swift scripts/ControlTests.swift -o "$OUT/tests/ControlTests"
"$OUT/tests/ControlTests"
