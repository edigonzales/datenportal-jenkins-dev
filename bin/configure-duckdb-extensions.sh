#!/usr/bin/env bash
set -euo pipefail

# ili2duckdb uses DuckDB's default lookup path; GRETL also supports the explicit path.
: "${DUCKDB_EXTENSION_DIRECTORY:?DUCKDB_EXTENSION_DIRECTORY is required}"
source_dir="$(cd "$DUCKDB_EXTENSION_DIRECTORY" && pwd)"
target_dir="${HOME}/.duckdb/extensions"
mkdir -p "$(dirname "$target_dir")"
if [ -L "$target_dir" ]; then
  [ "$(readlink "$target_dir")" = "$source_dir" ] || {
    echo "DuckDB extension path points elsewhere: $target_dir" >&2
    exit 1
  }
elif [ -e "$target_dir" ]; then
  # Existing Jenkins homes may already contain extensions. Preserve them and install only
  # missing links at the version/platform level; refuse conflicting contents.
  while IFS= read -r artifact; do
    relative="${artifact#"$source_dir/"}"
    target="$target_dir/$relative"
    mkdir -p "$(dirname "$target")"
    if [ -e "$target" ]; then
      cmp -s "$artifact" "$target" || { echo "Conflicting DuckDB extension: $target" >&2; exit 1; }
    else
      ln -s "$artifact" "$target"
    fi
  done < <(find "$source_dir" -type f)
else
  ln -s "$source_dir" "$target_dir"
fi
