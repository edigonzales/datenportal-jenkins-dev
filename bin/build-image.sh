#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
THEMEN_REPO_DIR="${THEMEN_REPO_DIR:-$ROOT_DIR/../datenportal-themenrepo}"
IMAGE_NAME="${IMAGE_NAME:-datenportal-jenkins:local}"
IMAGE_PLATFORM="${IMAGE_PLATFORM:-}"
DOCKER_CONTEXT_DIR="$ROOT_DIR/build/docker-context"
prepared=false
if [[ $# -gt 0 ]]; then
  [[ $# -eq 2 && "$1" = --prepared-context && -n "$2" ]] || {
    echo 'Aufruf: build-image.sh [--prepared-context VERZEICHNIS]' >&2; exit 2;
  }
  DOCKER_CONTEXT_DIR="$2"
  prepared=true
fi
case "$IMAGE_PLATFORM" in
  ''|linux/amd64|linux/arm64) ;;
  *) echo 'IMAGE_PLATFORM muss linux/amd64 oder linux/arm64 sein.' >&2; exit 2 ;;
esac
command -v docker >/dev/null || { echo 'Docker fehlt.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Python 3 fehlt.' >&2; exit 1; }
docker buildx version >/dev/null
if ! $prepared; then
  "$SCRIPT_DIR/prepare-image-context.sh"
fi
# A prepared context is complete: no Maven, Java or dependency downloads on this host.
[[ -f "$DOCKER_CONTEXT_DIR/Dockerfile" ]] || { echo 'Dockerfile im Kontext fehlt.' >&2; exit 1; }
# Validate before process substitution so parser failures cannot be swallowed by Bash.
build_arguments="$(python3 - "$DOCKER_CONTEXT_DIR/build-args.json" <<'PYARGS'
import json
import sys
with open(sys.argv[1]) as stream:
    args = json.load(stream)
expected = {'JENKINS_IMAGE', 'IMAGE_VERSION', 'PLUGIN_VERSION', 'GRETL_VERSION',
            'THEMEN_REPO_REVISION', 'PLUGIN_REPO_REVISION', 'TEMURIN17_VERSION'}
if set(args) != expected or any(not isinstance(v, str) or not v or '\n' in v or '\r' in v for v in args.values()):
    raise SystemExit('Ungueltige Build-Metadaten im vorbereiteten Kontext.')
for key, value in args.items():
    print(f'{key}={value}')
PYARGS
)"
# A nonempty array also works with macOS Bash 3.2 and set -u.
# Load one platform so tests run against the exact image that will be pushed.
build_args=(buildx build --load --provenance=false)
if [[ -n "$IMAGE_PLATFORM" ]]; then build_args+=(--platform "$IMAGE_PLATFORM"); fi
while IFS= read -r argument; do build_args+=(--build-arg "$argument"); done <<< "$build_arguments"
docker "${build_args[@]}" -f "$DOCKER_CONTEXT_DIR/Dockerfile" -t "$IMAGE_NAME" "$DOCKER_CONTEXT_DIR"
if [[ -n "$IMAGE_PLATFORM" ]]; then
  actual="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$IMAGE_NAME")"
  [[ "$actual" = "$IMAGE_PLATFORM" ]] || { echo "Image-Plattform $actual statt $IMAGE_PLATFORM" >&2; exit 1; }
fi
THEMEN_REPO_DIR="$THEMEN_REPO_DIR" "$SCRIPT_DIR/test-image-duckdb.sh" "$IMAGE_NAME"
printf '\nDocker-Image gebaut und DuckDB offline geprueft: %s\n' "$IMAGE_NAME"
if [[ "${RUN_PUBLICATION_TESTS:-0}" = 1 ]]; then
  THEMEN_REPO_DIR="$THEMEN_REPO_DIR" "$SCRIPT_DIR/test-image-publication.sh" "$IMAGE_NAME"
fi
