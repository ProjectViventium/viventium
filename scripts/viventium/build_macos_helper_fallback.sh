#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HELPER_PACKAGE_DIR="${VIVENTIUM_HELPER_PACKAGE_DIR:-$REPO_ROOT/apps/macos/ViventiumHelper}"
PREBUILT_DIR="${VIVENTIUM_HELPER_PREBUILT_DIR:-$HELPER_PACKAGE_DIR/prebuilt}"
UNIVERSAL_OUT="${VIVENTIUM_HELPER_PREBUILT_EXECUTABLE:-$PREBUILT_DIR/ViventiumHelper-universal}"
SOURCE_HASH_FILE="${VIVENTIUM_HELPER_PREBUILT_SOURCE_HASH_FILE:-$PREBUILT_DIR/source.sha256}"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

SDK_PATH="$(xcrun --show-sdk-path)"
SOURCE_PATH="$HELPER_PACKAGE_DIR/Sources/ViventiumHelper/ViventiumHelperApp.swift"
ARM64_OUT="$TEMP_DIR/ViventiumHelper-arm64"
X86_64_OUT="$TEMP_DIR/ViventiumHelper-x86_64"

mkdir -p "$PREBUILT_DIR"

xcrun swiftc -parse-as-library -sdk "$SDK_PATH" -target arm64-apple-macosx13.0 "$SOURCE_PATH" -o "$ARM64_OUT"
xcrun swiftc -parse-as-library -sdk "$SDK_PATH" -target x86_64-apple-macosx13.0 "$SOURCE_PATH" -o "$X86_64_OUT"
lipo -create -output "$UNIVERSAL_OUT" "$ARM64_OUT" "$X86_64_OUT"
chmod +x "$UNIVERSAL_OUT"

python3 - "$HELPER_PACKAGE_DIR" "$SOURCE_HASH_FILE" <<'PY'
import hashlib
import sys
from pathlib import Path

helper_dir = Path(sys.argv[1])
out_path = Path(sys.argv[2])
paths = [
    helper_dir / "Package.swift",
    helper_dir / "Sources" / "ViventiumHelper" / "ViventiumHelperApp.swift",
    helper_dir / "Sources" / "ViventiumHelper" / "Resources" / "Info.plist",
]

digest = hashlib.sha256()
for path in paths:
    digest.update(path.relative_to(helper_dir).as_posix().encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")

out_path.write_text(digest.hexdigest() + "\n", encoding="utf-8")
PY

echo "Built fallback helper: $UNIVERSAL_OUT"
echo "Recorded source hash: $SOURCE_HASH_FILE"
