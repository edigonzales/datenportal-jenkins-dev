#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_JENKINS_DEV_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
JENKINS_DEV_HOME="${JENKINS_DEV_HOME:-$DEFAULT_JENKINS_DEV_HOME}"
PLUGIN_REPO="${PLUGIN_REPO:-/Users/stefan/sources/jenkins-gretl-datenportal-plugin}"
HPI_SOURCE="${1:-$PLUGIN_REPO/target/jenkins-gretl-datenportal-plugin.hpi}"

PLUGINS_DIR="$JENKINS_DEV_HOME/jenkins-home/plugins"
PLUGIN_TARGET="$PLUGINS_DIR/jenkins-gretl-datenportal-plugin.jpi"
PLUGIN_LEGACY_TARGET="$PLUGINS_DIR/jenkins-gretl-datenportal-plugin.hpi"
PLUGIN_EXPLODED_DIR="$PLUGINS_DIR/jenkins-gretl-datenportal-plugin"
PORT=8080

format_mtime() {
  local file_path="$1"

  if stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S' "$file_path" >/dev/null 2>&1; then
    stat -f '%Sm' -t '%Y-%m-%d %H:%M:%S' "$file_path"
    return
  fi

  if stat -c '%y' "$file_path" >/dev/null 2>&1; then
    stat -c '%y' "$file_path"
    return
  fi

  echo "unknown"
}

print_file_details() {
  local label="$1"
  local file_path="$2"

  echo "$label:"
  echo "  path:      $file_path"
  echo "  modified:  $(format_mtime "$file_path")"
  if command -v cksum >/dev/null 2>&1; then
    echo "  checksum:  $(cksum "$file_path" | awk '{print $1}')"
  fi
}

warn_if_jenkins_running() {
  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi

  local listeners
  listeners="$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
  if [ -z "$listeners" ]; then
    return
  fi

  echo
  echo "WARNING: Port ${PORT} is already in use. Jenkins must be fully restarted"
  echo "so the new plugin classes and Jelly views are loaded."
  echo "$listeners"
}

if [ ! -f "$HPI_SOURCE" ]; then
  echo "HPI not found: $HPI_SOURCE" >&2
  echo "Build it first, for example:" >&2
  echo "  cd $PLUGIN_REPO && export JAVA_HOME=\"\$HOME/.sdkman/candidates/java/21.0.10-tem\" && export PATH=\"\$JAVA_HOME/bin:\$PATH\" && mvn -ntp package" >&2
  exit 1
fi

mkdir -p "$PLUGINS_DIR"

had_exploded_dir=false
if [ -d "$PLUGIN_EXPLODED_DIR" ]; then
  had_exploded_dir=true
fi

cp "$HPI_SOURCE" "$PLUGIN_TARGET"
rm -f "$PLUGIN_LEGACY_TARGET"
rm -rf "$PLUGIN_EXPLODED_DIR"

echo "Installed GRETL Datenportal plugin:"
print_file_details "Source HPI" "$HPI_SOURCE"
print_file_details "Installed JPI" "$PLUGIN_TARGET"
if [ "$had_exploded_dir" = true ]; then
  echo "Removed exploded plugin directory: $PLUGIN_EXPLODED_DIR"
fi
warn_if_jenkins_running
echo
echo "Restart Jenkins completely if it is already running."
echo "A simple file copy is not enough once Jenkins has already loaded the plugin."
echo "Start local Jenkins with:"
echo "  cd $JENKINS_DEV_HOME && ./bin/start.sh"
