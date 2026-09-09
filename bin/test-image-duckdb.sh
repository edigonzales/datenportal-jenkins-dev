#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-$ROOT_DIR/../datenportal-themenrepo}"
TEST_IMAGE="${1:-${IMAGE_NAME:-datenportal-jenkins:local}}"

command -v docker >/dev/null || { echo "Docker fehlt." >&2; exit 1; }
THEMEN_REPO_DIR="$(cd "$THEMEN_REPO_DIR" && pwd)"
for required in gradlew gradle/wrapper/gradle-wrapper.jar shared/bin/gradlew-java17.sh shared/gradle/init.gradle shared/gradle/gradle-build.properties; do
  test -f "$THEMEN_REPO_DIR/$required" || { echo "Themenrepo-Datei fehlt: $required" >&2; exit 1; }
done

# Each case gets a fresh home and workspace; no host caches or Jenkins volumes.
for scenario in positive missing-extensions; do
  echo "DuckDB image test: $scenario ($TEST_IMAGE)"
  docker run --rm --network none --user jenkins \
    --tmpfs /var/jenkins_home:uid=1000,gid=1000,mode=0700 \
    --mount "type=bind,source=$THEMEN_REPO_DIR,target=/inputs/themenrepo,readonly" \
    --mount "type=bind,source=$ROOT_DIR/tests/duckdb,target=/inputs/test,readonly" \
    --entrypoint /bin/bash "$TEST_IMAGE" /inputs/test/run.sh "$scenario"
done

echo "DuckDB image offline tests passed."
