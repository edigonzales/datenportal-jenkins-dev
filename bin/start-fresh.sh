#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRESH_JENKINS_HOME_DIR="${FRESH_JENKINS_HOME_DIR:-$ROOT_DIR/build/jenkins-home-fresh}"
PLUGIN_REPO="${PLUGIN_REPO:-$ROOT_DIR/../jenkins-gretl-datenportal-plugin}"
PLUGIN_HPI_SOURCE="${PLUGIN_HPI_SOURCE:-$PLUGIN_REPO/target/jenkins-gretl-datenportal-plugin.hpi}"

case "$FRESH_JENKINS_HOME_DIR" in
  "$ROOT_DIR/build"/*)
    ;;
  *)
    echo "Fresh Jenkins home muss unter $ROOT_DIR/build/ liegen: $FRESH_JENKINS_HOME_DIR" >&2
    exit 1
    ;;
esac

if [ ! -f "$PLUGIN_HPI_SOURCE" ]; then
  echo "Plugin-HPI nicht gefunden: $PLUGIN_HPI_SOURCE" >&2
  echo "Zuerst im Plugin-Repo 'mvn -ntp package' ausfuehren oder PLUGIN_HPI_SOURCE setzen." >&2
  exit 1
fi

rm -rf "$FRESH_JENKINS_HOME_DIR"
mkdir -p "$(dirname "$FRESH_JENKINS_HOME_DIR")"

mkdir -p "$FRESH_JENKINS_HOME_DIR/plugins"
cp "$PLUGIN_HPI_SOURCE" "$FRESH_JENKINS_HOME_DIR/plugins/jenkins-gretl-datenportal-plugin.jpi"
echo "Plugin-HPI fuer Fresh-Start installiert: $PLUGIN_HPI_SOURCE"

export JENKINS_HOME_DIR="$FRESH_JENKINS_HOME_DIR"
exec "$ROOT_DIR/bin/start.sh"
