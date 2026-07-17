#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-/Users/stefan/sources/datenportal-themenrepo}"
PLUGIN_REPO="${PLUGIN_REPO:-/Users/stefan/sources/jenkins-gretl-datenportal-plugin}"
PLUGIN_HPI_SOURCE="${PLUGIN_HPI_SOURCE:-$PLUGIN_REPO/target/jenkins-gretl-datenportal-plugin.hpi}"
OFFLINE_BUNDLE_DIR="${OFFLINE_BUNDLE_DIR:-$ROOT_DIR/build/offline-bundle}"
DOCKER_CONTEXT_DIR="$ROOT_DIR/build/docker-context"
IMAGE_NAME="${IMAGE_NAME:-datenportal-jenkins:local}"
JENKINS_VERSION="${JENKINS_VERSION:-2.555.2}"
JENKINS_IMAGE="${JENKINS_IMAGE:-jenkins/jenkins:${JENKINS_VERSION}-lts-jdk21}"
TEMURIN17_VERSION="${TEMURIN17_VERSION:-17.0.15+6}"

command -v docker >/dev/null || { echo "Docker fehlt."; exit 1; }
command -v rsync >/dev/null || { echo "rsync fehlt."; exit 1; }

if [ ! -f "$PLUGIN_HPI_SOURCE" ]; then
  echo "Plugin-HPI nicht gefunden: $PLUGIN_HPI_SOURCE" >&2
  echo "Bitte zuerst das Jenkins-Plugin bauen." >&2
  exit 1
fi

"$ROOT_DIR/bin/build-offline-bundle.sh" "$OFFLINE_BUNDLE_DIR"

rm -rf "$DOCKER_CONTEXT_DIR"
mkdir -p "$DOCKER_CONTEXT_DIR/offline-bundle"

cp "$ROOT_DIR/plugins.txt" "$DOCKER_CONTEXT_DIR/plugins.txt"
cp "$ROOT_DIR/casc/jenkins-production.yaml" "$DOCKER_CONTEXT_DIR/jenkins.yaml"
cp "$ROOT_DIR/docker-entrypoint.sh" "$DOCKER_CONTEXT_DIR/docker-entrypoint.sh"
cp "$PLUGIN_HPI_SOURCE" "$DOCKER_CONTEXT_DIR/jenkins-gretl-datenportal-plugin.jpi"
rsync -a --delete \
  --exclude '.DS_Store' \
  "$OFFLINE_BUNDLE_DIR/" "$DOCKER_CONTEXT_DIR/offline-bundle/"

docker build \
  --build-arg JENKINS_IMAGE="$JENKINS_IMAGE" \
  --build-arg TEMURIN17_VERSION="$TEMURIN17_VERSION" \
  -f "$ROOT_DIR/Dockerfile" \
  -t "$IMAGE_NAME" \
  "$DOCKER_CONTEXT_DIR"

echo
echo "Docker-Image gebaut: $IMAGE_NAME"
