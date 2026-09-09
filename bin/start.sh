#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOWNLOADS_DIR="$ROOT_DIR/downloads"
JENKINS_HOME_DIR="${JENKINS_HOME_DIR:-${JENKINS_HOME:-$ROOT_DIR/jenkins-home}}"
JENKINS_WAR="$DOWNLOADS_DIR/jenkins.war"
PLUGIN_MANAGER_JAR="$DOWNLOADS_DIR/jenkins-plugin-manager.jar"
PLUGINS_TXT="$ROOT_DIR/plugins.txt"
OFFLINE_BUNDLE_DIR="${OFFLINE_BUNDLE_DIR:-$ROOT_DIR/build/offline-bundle}"
JENKINS_VERSION="${JENKINS_VERSION:-2.555.2}"
PLUGIN_MANAGER_VERSION="${PLUGIN_MANAGER_VERSION:-2.14.0}"
JENKINS_PORT="${JENKINS_PORT:-8080}"
SKIP_OFFLINE_BUNDLE="${SKIP_OFFLINE_BUNDLE:-0}"

THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-$ROOT_DIR/../datenportal-themenrepo}"
THEMEN_REPO_MODE="${THEMEN_REPO_MODE:-managed-git}"
THEMEN_REPO_URL="${THEMEN_REPO_URL:-}"
THEMEN_REPO_PATH="${THEMEN_REPO_PATH:-}"
THEMEN_REPO_BRANCH="${THEMEN_REPO_BRANCH:-main}"
source "$ROOT_DIR/bin/java-env.sh"

mkdir -p "$DOWNLOADS_DIR" "$JENKINS_HOME_DIR/plugins"

command -v git >/dev/null || { echo "Git fehlt."; exit 1; }
command -v curl >/dev/null || { echo "curl fehlt."; exit 1; }

JAVA17_HOME="$(resolve_java_home 17 JAVA17_HOME "Java 17 fuer GRETL/Gradle")"
JAVA21_HOME="$(resolve_java_home 21 JAVA21_HOME "Java 21 fuer Jenkins")"
export JAVA17_HOME JAVA21_HOME
export GRADLE_JAVA_HOME_17="$JAVA17_HOME"

if [ ! -d "$THEMEN_REPO_DIR/.git" ]; then
  echo "Themenrepo nicht gefunden oder kein Git-Repo: $THEMEN_REPO_DIR" >&2
  exit 1
fi

case "$THEMEN_REPO_MODE" in
  managed-git)
    if [ -z "$THEMEN_REPO_URL" ]; then
      THEMEN_REPO_URL="file://$THEMEN_REPO_DIR"
    fi
    ;;
  working-tree)
    THEMEN_REPO_URL=""
    if [ -z "$THEMEN_REPO_PATH" ]; then
      THEMEN_REPO_PATH="$THEMEN_REPO_DIR"
    fi
    ;;
  *)
    echo "Unbekannter THEMEN_REPO_MODE: $THEMEN_REPO_MODE (erlaubt: managed-git, working-tree)" >&2
    exit 1
    ;;
esac

if [ "$SKIP_OFFLINE_BUNDLE" = "1" ]; then
  if [ ! -d "$OFFLINE_BUNDLE_DIR/jars" ] || [ ! -d "$OFFLINE_BUNDLE_DIR/gradle-user-home" ]; then
    echo "Offline-Bundle fehlt unter $OFFLINE_BUNDLE_DIR; SKIP_OFFLINE_BUNDLE=1 ist nicht moeglich." >&2
    exit 1
  fi
  echo "Offline-Bundle wird wiederverwendet: $OFFLINE_BUNDLE_DIR"
else
  echo "Baue/Aktualisiere Offline-Bundle..."
  "$ROOT_DIR/bin/build-offline-bundle.sh" "$OFFLINE_BUNDLE_DIR"
fi

activate_java_home "$JAVA21_HOME"

if [ ! -f "$JENKINS_WAR" ]; then
  echo "Downloading Jenkins WAR..."
  curl -L -o "$JENKINS_WAR" "https://get.jenkins.io/war-stable/${JENKINS_VERSION}/jenkins.war"
fi

if [ ! -f "$PLUGIN_MANAGER_JAR" ]; then
  echo "Downloading Jenkins Plugin Installation Manager..."
  curl -L -o "$PLUGIN_MANAGER_JAR" \
    "https://github.com/jenkinsci/plugin-installation-manager-tool/releases/download/${PLUGIN_MANAGER_VERSION}/jenkins-plugin-manager-${PLUGIN_MANAGER_VERSION}.jar"
fi

echo "Installing/updating Jenkins plugins..."
java -jar "$PLUGIN_MANAGER_JAR" \
  --war "$JENKINS_WAR" \
  --plugin-download-directory "$JENKINS_HOME_DIR/plugins" \
  --plugin-file "$PLUGINS_TXT"

export JENKINS_HOME="$JENKINS_HOME_DIR"
export CASC_JENKINS_CONFIG="$ROOT_DIR/casc/jenkins.yaml"
export JENKINS_RUNTIME_MODE=dev
export JENKINS_URL="${JENKINS_URL:-http://localhost:${JENKINS_PORT}/}"
export THEMEN_REPO_MODE
export THEMEN_REPO_URL
export THEMEN_REPO_PATH
export THEMEN_REPO_BRANCH
export DATENPORTAL_MODELS_DIR="$OFFLINE_BUNDLE_DIR/models"
export DATENPORTAL_OFFLINE_JARS_DIR="$OFFLINE_BUNDLE_DIR/jars"
export GRADLE_USER_HOME="$OFFLINE_BUNDLE_DIR/gradle-user-home"
export DUCKDB_EXTENSION_DIRECTORY="${DUCKDB_EXTENSION_DIRECTORY:-$ROOT_DIR/build/duckdb-extensions-host}"
"$JAVA17_HOME/bin/java" -cp "$DATENPORTAL_OFFLINE_JARS_DIR/*" \
  ch.so.agi.gretl.internal.duckdb.DuckDbExtensionInstaller postgres spatial excel
"$ROOT_DIR/bin/configure-duckdb-extensions.sh"

java_opts=(
  "-Djenkins.install.runSetupWizard=false"
)

if [ -n "${JAVA_OPTS:-}" ]; then
  read -r -a extra_java_opts <<< "${JAVA_OPTS}"
  java_opts+=("${extra_java_opts[@]}")
fi

echo
echo "Starting Jenkins with java ${java_opts[*]} -jar jenkins.war ..."
echo "URL:         http://localhost:${JENKINS_PORT}"
echo "Login:       admin / admin"
echo "Jenkins home: $JENKINS_HOME"
echo "Repo mode:   $THEMEN_REPO_MODE"
echo "Themes repo: $THEMEN_REPO_URL"
echo "Repo path:   $THEMEN_REPO_PATH"
echo "Branch:      $THEMEN_REPO_BRANCH"
echo "Offline jars: $DATENPORTAL_OFFLINE_JARS_DIR"
echo "Gradle home:  $GRADLE_USER_HOME"
echo "Gradle Java:  $GRADLE_JAVA_HOME_17"
echo "Jenkins Java: $JAVA_HOME"
echo

exec java "${java_opts[@]}" -jar "$JENKINS_WAR" --httpPort="$JENKINS_PORT"
