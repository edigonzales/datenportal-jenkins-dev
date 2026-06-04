#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOWNLOADS_DIR="$ROOT_DIR/downloads"
JENKINS_HOME_DIR="$ROOT_DIR/jenkins-home"
JENKINS_WAR="$DOWNLOADS_DIR/jenkins.war"
PLUGIN_MANAGER_JAR="$DOWNLOADS_DIR/jenkins-plugin-manager.jar"
PLUGINS_TXT="$ROOT_DIR/plugins.txt"
OFFLINE_BUNDLE_DIR="${OFFLINE_BUNDLE_DIR:-$ROOT_DIR/build/offline-bundle}"
JENKINS_VERSION="${JENKINS_VERSION:-2.555.2}"
PLUGIN_MANAGER_VERSION="${PLUGIN_MANAGER_VERSION:-2.14.0}"

THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-/Users/stefan/sources/datenportal-themenrepo}"
THEMEN_REPO_URL="${THEMEN_REPO_URL:-file://$THEMEN_REPO_DIR}"
THEMEN_REPO_BRANCH="${THEMEN_REPO_BRANCH:-main}"

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

mkdir -p "$DOWNLOADS_DIR" "$JENKINS_HOME_DIR/plugins"

command -v java >/dev/null || { echo "Java fehlt. Bitte Java 17 installieren."; exit 1; }
command -v git >/dev/null || { echo "Git fehlt."; exit 1; }
command -v curl >/dev/null || { echo "curl fehlt."; exit 1; }

ensure_java17

if [ ! -d "$THEMEN_REPO_DIR/.git" ]; then
  echo "Themenrepo nicht gefunden oder kein Git-Repo: $THEMEN_REPO_DIR" >&2
  exit 1
fi

echo "Baue/Aktualisiere Offline-Bundle..."
"$ROOT_DIR/bin/build-offline-bundle.sh" "$OFFLINE_BUNDLE_DIR"

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
export THEMEN_REPO_URL
export THEMEN_REPO_BRANCH
export DATENPORTAL_OFFLINE_JARS_DIR="$OFFLINE_BUNDLE_DIR/jars"
export GRADLE_USER_HOME="$OFFLINE_BUNDLE_DIR/gradle-user-home"

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
echo "Offline jars: $DATENPORTAL_OFFLINE_JARS_DIR"
echo "Gradle home:  $GRADLE_USER_HOME"
echo

exec java "${java_opts[@]}" -jar "$JENKINS_WAR" --httpPort=8080
