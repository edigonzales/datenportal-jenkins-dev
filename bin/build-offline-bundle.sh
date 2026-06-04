#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-/Users/stefan/sources/datenportal-themenrepo}"
OFFLINE_BUNDLE_DIR="${1:-${OFFLINE_BUNDLE_DIR:-$ROOT_DIR/build/offline-bundle}}"

java_major_version() {
  java -version 2>&1 | awk -F'[\".]' '/version/ {print $2; exit}'
}

ensure_java17() {
  local detected_major
  detected_major="$(java_major_version)"

  if [ "$detected_major" != "17" ]; then
    if command -v /usr/libexec/java_home >/dev/null 2>&1; then
      local java17_home
      java17_home="$(/usr/libexec/java_home -v 17 2>/dev/null || true)"
      if [ -n "$java17_home" ]; then
        export JAVA_HOME="$java17_home"
        export PATH="$JAVA_HOME/bin:$PATH"
        detected_major="$(java_major_version)"
      fi
    fi
  fi

  if [ "$detected_major" != "17" ]; then
    local sdkman_java17_home
    sdkman_java17_home="$(ls -d "$HOME"/.sdkman/candidates/java/17* 2>/dev/null | head -n 1 || true)"
    if [ -n "$sdkman_java17_home" ]; then
      export JAVA_HOME="$sdkman_java17_home"
      export PATH="$JAVA_HOME/bin:$PATH"
      detected_major="$(java_major_version)"
    fi
  fi

  if [ "$detected_major" != "17" ]; then
    echo "GRETL/Gradle benoetigt Java 17. Setze JAVA_HOME auf Java 17." >&2
    exit 1
  fi
}

command -v java >/dev/null || { echo "Java fehlt. Bitte Java 17 installieren."; exit 1; }
command -v git >/dev/null || { echo "Git fehlt."; exit 1; }

ensure_java17

if [ ! -d "$THEMEN_REPO_DIR/.git" ]; then
  echo "Themenrepo nicht gefunden oder kein Git-Repo: $THEMEN_REPO_DIR" >&2
  exit 1
fi

cd "$ROOT_DIR"
chmod +x ./gradlew

./gradlew --no-daemon \
  --refresh-dependencies \
  prepareOfflineBundle \
  -PthemenRepoDir="$THEMEN_REPO_DIR" \
  -PofflineBundleDir="$OFFLINE_BUNDLE_DIR"

echo
echo "Offline-Bundle bereit:"
echo "  Jars:             $OFFLINE_BUNDLE_DIR/jars"
echo "  GRADLE_USER_HOME: $OFFLINE_BUNDLE_DIR/gradle-user-home"
echo "  Manifest:         $OFFLINE_BUNDLE_DIR/resolved-manifest.json"
