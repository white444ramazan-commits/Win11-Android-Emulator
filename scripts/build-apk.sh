#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$ROOT/engine/DroidVM"

# Initialize both the pinned DroidVM engine and its nested native/prebuilt dependencies.
git -C "$ROOT" submodule update --init --recursive

if [[ ! -f "$ENGINE/gradlew" ]]; then
  echo "DroidVM Gradle wrapper is missing after submodule initialization." >&2
  exit 1
fi

if [[ ! -x "$ENGINE/gradlew" ]]; then
  chmod +x "$ENGINE/gradlew"
fi

cd "$ENGINE"
# Android API 37 is not yet available from the public SDK package index.
# Build the app against the latest published stable SDK (API 36) until API 37 ships.
sed -i -e 's/version = release(37)/version = release(36)/' -e 's/targetSdk = 37/targetSdk = 36/' app/build.gradle.kts
grep -q 'version = release(36)' app/build.gradle.kts
grep -q 'targetSdk = 36' app/build.gradle.kts

echo "Building upstream DroidVM debug APK against Android API 36..."
./gradlew --no-daemon assembleDebug

APK="$ENGINE/app/build/outputs/apk/debug/app-debug.apk"
if [[ -f "$APK" ]]; then
  echo
  echo "APK created: $APK"
else
  echo "Build finished but expected APK was not found: $APK" >&2
  exit 1
fi
