#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$ROOT/engine/DroidVM"

if [[ ! -d "$ENGINE" ]]; then
  echo "DroidVM submodule is missing. Initializing submodules..."
  git -C "$ROOT" submodule update --init --recursive
fi

if [[ ! -x "$ENGINE/gradlew" ]]; then
  chmod +x "$ENGINE/gradlew"
fi

cd "$ENGINE"
echo "Building DroidVM debug APK..."
./gradlew --no-daemon assembleDebug

APK="$ENGINE/app/build/outputs/apk/debug/app-debug.apk"
if [[ -f "$APK" ]]; then
  echo
  echo "APK created: $APK"
else
  echo "Build finished but expected APK was not found: $APK" >&2
  exit 1
fi
