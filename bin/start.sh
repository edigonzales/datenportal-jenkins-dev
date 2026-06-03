#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOWNLOADS_DIR="$ROOT_DIR/downloads"
JENKINS_HOME_DIR="$ROOT_DIR/jenkins-home"
JENKINS_WAR="$DOWNLOADS_DIR/jenkins.war"
PLUGIN_MANAGER_JAR="$DOWNLOADS_DIR/jenkins-plugin-manager.jar"
PLUGINS_TXT="$ROOT_DIR/plugins.txt"

THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-/Users/stefan/sources/datenportal-themenrepo}"
THEMEN_REPO_URL="${THEMEN_REPO_URL:-file://$THEMEN_REPO_DIR}"
THEMEN_REPO_BRANCH="${THEMEN_REPO_BRANCH:-main}"

mkdir -p "$DOWNLOADS_DIR" "$JENKINS_HOME_DIR/plugins"

command -v java >/dev/null || { echo "Java fehlt. Bitte Java 21 installieren."; exit 1; }
command -v git >/dev/null || { echo "Git fehlt."; exit 1; }
command -v curl >/dev/null || { echo "curl fehlt."; exit 1; }

if [ ! -d "$THEMEN_REPO_DIR/.git" ]; then
  echo "Themenrepo nicht gefunden oder kein Git-Repo: $THEMEN_REPO_DIR" >&2
  exit 1
fi

if [ ! -f "$JENKINS_WAR" ]; then
  echo "Downloading Jenkins WAR..."
  curl -L -o "$JENKINS_WAR" "https://get.jenkins.io/war-stable/latest/jenkins.war"
fi

if [ ! -f "$PLUGIN_MANAGER_JAR" ]; then
  echo "Downloading Jenkins Plugin Installation Manager..."
  curl -L -o "$PLUGIN_MANAGER_JAR" \
    "https://github.com/jenkinsci/plugin-installation-manager-tool/releases/download/2.14.0/jenkins-plugin-manager-2.14.0.jar"
fi

echo "Installing/updating Jenkins plugins..."
java -jar "$PLUGIN_MANAGER_JAR" \
  --war "$JENKINS_WAR" \
  --plugin-download-directory "$JENKINS_HOME_DIR/plugins" \
  --plugin-file "$PLUGINS_TXT"

export JENKINS_HOME="$JENKINS_HOME_DIR"
export CASC_JENKINS_CONFIG="$ROOT_DIR/casc/jenkins.yaml"
export THEMEN_REPO_URL
export THEMEN_REPO_BRANCH

java_opts=(
  "-Djenkins.install.runSetupWizard=false"
)

if [ -n "${JAVA_OPTS:-}" ]; then
  read -r -a extra_java_opts <<< "${JAVA_OPTS}"
  java_opts+=("${extra_java_opts[@]}")
fi

echo
echo "Starting Jenkins with java ${java_opts[*]} -jar jenkins.war ..."
echo "URL:         http://localhost:8080"
echo "Login:       admin / admin"
echo "Themes repo: $THEMEN_REPO_URL"
echo "Branch:      $THEMEN_REPO_BRANCH"
echo

exec java "${java_opts[@]}" -jar "$JENKINS_WAR" --httpPort=8080
