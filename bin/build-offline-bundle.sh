#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-/Users/stefan/sources/datenportal-themenrepo}"
OFFLINE_BUNDLE_DIR="${1:-${OFFLINE_BUNDLE_DIR:-$ROOT_DIR/build/offline-bundle}}"
source "$ROOT_DIR/bin/java-env.sh"

command -v git >/dev/null || { echo "Git fehlt."; exit 1; }

JAVA17_HOME="$(resolve_java_home 17 JAVA17_HOME "Java 17 fuer GRETL/Gradle")"
export JAVA17_HOME
export GRADLE_JAVA_HOME_17="$JAVA17_HOME"
activate_java_home "$JAVA17_HOME"

if [ ! -d "$THEMEN_REPO_DIR/.git" ]; then
  echo "Themenrepo nicht gefunden oder kein Git-Repo: $THEMEN_REPO_DIR" >&2
  exit 1
fi

cd "$ROOT_DIR"
chmod +x ./gradlew

./gradlew -i --no-daemon \
  --refresh-dependencies \
  prepareOfflineBundle \
  -PthemenRepoDir="$THEMEN_REPO_DIR" \
  -PofflineBundleDir="$OFFLINE_BUNDLE_DIR"

echo
echo "Offline-Bundle bereit:"
echo "  Jars:             $OFFLINE_BUNDLE_DIR/jars"
echo "  GRADLE_USER_HOME: $OFFLINE_BUNDLE_DIR/gradle-user-home"
echo "  Manifest:         $OFFLINE_BUNDLE_DIR/resolved-manifest.json"
echo "  Java 17:          $GRADLE_JAVA_HOME_17"
