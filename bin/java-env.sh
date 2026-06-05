#!/usr/bin/env bash

JAVA_ENV_BASE_PATH="${JAVA_ENV_BASE_PATH:-$PATH}"

java_major_from_home() {
  local java_home="$1"
  "$java_home/bin/java" -version 2>&1 | awk -F'[".]' '/version/ {print $2; exit}'
}

current_java_home_from_path() {
  java -XshowSettings:properties -version 2>&1 | awk -F'= ' '/^[[:space:]]*java.home = / {print $2; exit}'
}

find_sdkman_java_home() {
  local expected_major="$1"
  ls -d "$HOME"/.sdkman/candidates/java/"$expected_major"* 2>/dev/null | sort | tail -n 1
}

is_java_home_for_major() {
  local java_home="$1"
  local expected_major="$2"

  [ -n "$java_home" ] || return 1
  [ -x "$java_home/bin/java" ] || return 1
  [ "$(java_major_from_home "$java_home")" = "$expected_major" ]
}

require_java_home_for_major() {
  local java_home="$1"
  local expected_major="$2"
  local source_label="$3"

  if [ -z "$java_home" ] || [ ! -x "$java_home/bin/java" ]; then
    echo "$source_label verweist nicht auf ein gueltiges Java-Home: $java_home" >&2
    exit 1
  fi

  local detected_major
  detected_major="$(java_major_from_home "$java_home")"
  if [ "$detected_major" != "$expected_major" ]; then
    echo "$source_label verweist auf Java $detected_major statt Java $expected_major: $java_home" >&2
    exit 1
  fi
}

resolve_java_home() {
  local expected_major="$1"
  local override_var="$2"
  local purpose_label="$3"
  local candidate=""
  local override_value="${!override_var:-}"

  if [ -n "$override_value" ]; then
    require_java_home_for_major "$override_value" "$expected_major" "$override_var"
    printf '%s\n' "$override_value"
    return 0
  fi

  if command -v /usr/libexec/java_home >/dev/null 2>&1; then
    candidate="$(/usr/libexec/java_home -v "$expected_major" 2>/dev/null || true)"
    if is_java_home_for_major "$candidate" "$expected_major"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi

  candidate="$(find_sdkman_java_home "$expected_major" || true)"
  if is_java_home_for_major "$candidate" "$expected_major"; then
    printf '%s\n' "$candidate"
    return 0
  fi

  if is_java_home_for_major "${JAVA_HOME:-}" "$expected_major"; then
    printf '%s\n' "$JAVA_HOME"
    return 0
  fi

  if command -v java >/dev/null 2>&1; then
    candidate="$(current_java_home_from_path || true)"
    if is_java_home_for_major "$candidate" "$expected_major"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi

  echo "$purpose_label nicht gefunden. Setze $override_var auf ein passendes Java-$expected_major-Home." >&2
  exit 1
}

activate_java_home() {
  local java_home="$1"
  export JAVA_HOME="$java_home"
  export PATH="$JAVA_HOME/bin:$JAVA_ENV_BASE_PATH"
}
