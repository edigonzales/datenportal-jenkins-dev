#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT_DIR/tests/publication/test_delivery.py" "${1:-datenportal-jenkins:local}"
