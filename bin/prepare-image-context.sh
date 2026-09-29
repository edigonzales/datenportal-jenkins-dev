#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-$ROOT_DIR/../datenportal-themenrepo}"
PLUGIN_REPO="${PLUGIN_REPO:-$ROOT_DIR/../datenportal-jenkins-gretl-plugin}"
PLUGIN_HPI_SOURCE="${PLUGIN_HPI_SOURCE:-}"
PLUGIN_SOURCE="${PLUGIN_SOURCE:-auto}"
PLUGIN_GROUP="${PLUGIN_GROUP:-ch.so.agi.jenkins}"
PLUGIN_ARTIFACT="${PLUGIN_ARTIFACT:-jenkins-gretl-datenportal-plugin}"
PLUGIN_VERSION="${PLUGIN_VERSION:-0.1.0-SNAPSHOT}"
PLUGIN_REPOSITORY_URL="${PLUGIN_REPOSITORY_URL:-https://jars.interlis.guru/snapshots}"
MAVEN_REPO_LOCAL="${MAVEN_REPO_LOCAL:-${HOME}/.m2/repository}"
OFFLINE_BUNDLE_DIR="${OFFLINE_BUNDLE_DIR:-$ROOT_DIR/build/offline-bundle}"
DOCKER_CONTEXT_DIR="$ROOT_DIR/build/docker-context"
IMAGE_VERSION="${IMAGE_VERSION:-local}"
JENKINS_VERSION="${JENKINS_VERSION:-2.555.2}"
JENKINS_IMAGE="${JENKINS_IMAGE:-jenkins/jenkins:${JENKINS_VERSION}-lts-jdk21}"
TEMURIN17_VERSION="${TEMURIN17_VERSION:-17.0.15+6}"

command -v python3 >/dev/null || { echo "Python 3 fehlt."; exit 1; }
command -v rsync >/dev/null || { echo "rsync fehlt."; exit 1; }

resolve_local_plugin() {
  command -v mvn >/dev/null || {
    echo "Maven fehlt fuer den lokalen Plugin-Build." >&2
    return 1
  }

  if [ ! -d "$PLUGIN_REPO" ]; then
    echo "Plugin-Repository nicht gefunden: $PLUGIN_REPO" >&2
    return 1
  fi

  echo "Baue Jenkins-Plugin lokal ..." >&2
  (
    cd "$PLUGIN_REPO"
    mvn -ntp package >&2
  )

  find "$PLUGIN_REPO/target" -maxdepth 1 -type f -name '*.hpi' -print | sort | tail -n 1
}

resolve_maven_plugin() {
  command -v mvn >/dev/null || {
    echo "Maven fehlt fuer die Plugin-Aufloesung aus Maven." >&2
    return 1
  }

  local coordinate="${PLUGIN_GROUP}:${PLUGIN_ARTIFACT}:${PLUGIN_VERSION}:hpi"
  echo "Loese Jenkins-Plugin aus Maven auf: $coordinate" >&2
  mvn -ntp org.apache.maven.plugins:maven-dependency-plugin:3.8.1:get \
    -Dartifact="$coordinate" \
    -DremoteRepositories="jars.interlis.guru::default::${PLUGIN_REPOSITORY_URL}" \
    -Dmaven.repo.local="$MAVEN_REPO_LOCAL" \
    -Dtransitive=false >&2

  find "$MAVEN_REPO_LOCAL/${PLUGIN_GROUP//.//}/${PLUGIN_ARTIFACT}/${PLUGIN_VERSION}" \
    -maxdepth 1 -type f -name '*.hpi' -print | sort | tail -n 1
}

resolve_plugin_hpi() {
  if [ -n "$PLUGIN_HPI_SOURCE" ]; then
    printf '%s\n' "$PLUGIN_HPI_SOURCE"
    return 0
  fi

  case "$PLUGIN_SOURCE" in
    local)
      resolve_local_plugin
      ;;
    maven)
      resolve_maven_plugin
      ;;
    auto)
      if [ -d "$PLUGIN_REPO" ]; then
        resolve_local_plugin
      else
        resolve_maven_plugin
      fi
      ;;
    *)
      echo "Unbekannter PLUGIN_SOURCE: $PLUGIN_SOURCE (erlaubt: local, maven, auto)" >&2
      return 1
      ;;
  esac
}

PLUGIN_HPI_SOURCE="$(resolve_plugin_hpi)"
if [ ! -f "$PLUGIN_HPI_SOURCE" ]; then
  echo "Plugin-HPI nicht gefunden: $PLUGIN_HPI_SOURCE" >&2
  exit 1
fi

if [ ! -f "$THEMEN_REPO_DIR/shared/gradle/gradle-build.properties" ]; then
  echo "Gradle-Build-Konfiguration des Themenrepos nicht gefunden: $THEMEN_REPO_DIR" >&2
  exit 1
fi

GRETL_VERSION="${GRETL_VERSION:-$(awk -F= '$1 == "datenportal.plugin.gretl.version" {print $2}' "$THEMEN_REPO_DIR/shared/gradle/gradle-build.properties" | tr -d '[:space:]')}"
GRETL_VERSION="${GRETL_VERSION:-unknown}"
THEMEN_REPO_REVISION="${THEMEN_REPO_REVISION:-$(git -C "$THEMEN_REPO_DIR" rev-parse HEAD 2>/dev/null || printf 'unknown')}"
PLUGIN_REPO_REVISION="${PLUGIN_REPO_REVISION:-$(git -C "$PLUGIN_REPO" rev-parse HEAD 2>/dev/null || printf 'unknown')}"

"$ROOT_DIR/bin/build-offline-bundle.sh" "$OFFLINE_BUNDLE_DIR"

rm -rf "$DOCKER_CONTEXT_DIR"
mkdir -p "$DOCKER_CONTEXT_DIR/offline-bundle"

cp "$ROOT_DIR/Dockerfile" "$DOCKER_CONTEXT_DIR/Dockerfile"
cp "$ROOT_DIR/plugins.txt" "$DOCKER_CONTEXT_DIR/plugins.txt"
cp "$ROOT_DIR/casc/jenkins-production.yaml" "$DOCKER_CONTEXT_DIR/jenkins.yaml"
cp "$ROOT_DIR/bin/configure-duckdb-extensions.sh" "$DOCKER_CONTEXT_DIR/configure-duckdb-extensions.sh"
cp "$ROOT_DIR/docker-entrypoint.sh" "$DOCKER_CONTEXT_DIR/docker-entrypoint.sh"
cp "$PLUGIN_HPI_SOURCE" "$DOCKER_CONTEXT_DIR/jenkins-gretl-datenportal-plugin.jpi"
rsync -a --delete \
  --exclude '.DS_Store' \
  "$OFFLINE_BUNDLE_DIR/" "$DOCKER_CONTEXT_DIR/offline-bundle/"

# Keep the exact inputs with the context; never re-resolve snapshots in matrix jobs.
export JENKINS_IMAGE IMAGE_VERSION PLUGIN_VERSION GRETL_VERSION THEMEN_REPO_REVISION
export PLUGIN_REPO_REVISION TEMURIN17_VERSION
python3 - "$DOCKER_CONTEXT_DIR/build-args.json" <<'PYARGS'
import json
import os
import sys
keys = ('JENKINS_IMAGE', 'IMAGE_VERSION', 'PLUGIN_VERSION', 'GRETL_VERSION',
        'THEMEN_REPO_REVISION', 'PLUGIN_REPO_REVISION', 'TEMURIN17_VERSION')
with open(sys.argv[1], 'w') as out:
    json.dump({key: os.environ[key] for key in keys}, out, indent=2)
    out.write('\n')
PYARGS
printf '\nBuild-Kontext vorbereitet: %s\n' "$DOCKER_CONTEXT_DIR"
