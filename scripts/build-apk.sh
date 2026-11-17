#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$ROOT/engine/DroidVM"

# Initialize both the pinned DroidVM engine and its nested native/prebuilt dependencies.
git -C "$ROOT" submodule update --init --recursive

# Apply the experimental no-Root QEMU/TCG overlay to the pinned engine.
python3 "$ROOT/scripts/apply-rootless-mode.py"

if [[ ! -f "$ENGINE/gradlew" ]]; then
  echo "DroidVM Gradle wrapper is missing after submodule initialization." >&2
  exit 1
fi

if [[ ! -x "$ENGINE/gradlew" ]]; then
  chmod +x "$ENGINE/gradlew"
fi

cd "$ENGINE"
echo "Building upstream DroidVM debug APK..."
./gradlew --no-daemon assembleDebug

APK="$ENGINE/app/build/outputs/apk/debug/app-debug.apk"
if [[ -f "$APK" ]]; then
  echo
  echo "APK created: $APK"
else
  echo "Build finished but expected APK was not found: $APK" >&2
  exit 1
fi
