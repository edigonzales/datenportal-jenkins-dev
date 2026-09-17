#!/usr/bin/env bash
set -euo pipefail

scenario="${1:?Test scenario required}"
test_work_dir="$(mktemp -d /tmp/datenportal-duckdb.XXXXXX)"
trap 'rm -rf "$test_work_dir"' EXIT
cp -R /inputs/test/. "$test_work_dir/"
cp /inputs/themenrepo/gradlew "$test_work_dir/"
cp -R /inputs/themenrepo/gradle "$test_work_dir/"
mkdir -p "$test_work_dir/shared"
cp -R /inputs/themenrepo/shared/bin /inputs/themenrepo/shared/gradle "$test_work_dir/shared/"
cd "$test_work_dir"

case "$scenario" in
  positive)
    /opt/java/openjdk17/bin/java -cp "$DATENPORTAL_OFFLINE_JARS_DIR/*" VerifyPlayground.java /inputs/themenrepo/shared/sql/publication/playground.sql
    /opt/java/openjdk17/bin/java -cp "$DATENPORTAL_OFFLINE_JARS_DIR/*" VerifyDuckDb.java
    ./shared/bin/gradlew-java17.sh --offline --no-daemon -I shared/gradle/init.gradle convert
    /opt/java/openjdk17/bin/java -cp "$DATENPORTAL_OFFLINE_JARS_DIR/*" VerifyDuckDb.java build/result.parquet build/result.xlsx
    ;;
  missing-extensions)
    export DUCKDB_EXTENSION_DIRECTORY="$test_work_dir/empty-extensions"
    mkdir -p "$DUCKDB_EXTENSION_DIRECTORY"
    if ./shared/bin/gradlew-java17.sh --offline --no-daemon -I shared/gradle/init.gradle convert > failure.log 2>&1; then
      echo "Export unexpectedly succeeded without installed extensions." >&2
      exit 1
    fi
    if ! grep -F "DuckDB extension 'excel' could not be loaded" failure.log; then
      cat failure.log >&2
      echo "Export failed for an unexpected reason." >&2
      exit 1
    fi
    test ! -e build/result.xlsx
    echo "Missing excel extension correctly rejected."
    ;;
  *) echo "Unknown scenario: $scenario" >&2; exit 1 ;;
esac
