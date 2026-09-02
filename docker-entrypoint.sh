#!/usr/bin/env bash
set -euo pipefail

runtime_mode="${JENKINS_RUNTIME_MODE:-production}"

case "$runtime_mode" in
  dev)
    ;;
  production)
    : "${THEMEN_REPO_URL:?THEMEN_REPO_URL muss fuer den Produktionsbetrieb gesetzt sein}"
    : "${THEMEN_REPO_BRANCH:?THEMEN_REPO_BRANCH muss gesetzt sein}"
    : "${JENKINS_URL:?JENKINS_URL muss fuer den Produktionsbetrieb gesetzt sein}"
    : "${JENKINS_ADMIN_ADDRESS:?JENKINS_ADMIN_ADDRESS muss gesetzt sein}"
    : "${AD_DOMAIN:?AD_DOMAIN muss fuer die Active-Directory-Anmeldung gesetzt sein}"
    : "${AD_SERVERS:?AD_SERVERS muss fuer die Active-Directory-Anmeldung gesetzt sein}"
    : "${AD_BIND_NAME:?AD_BIND_NAME muss fuer die Active-Directory-Anmeldung gesetzt sein}"
    : "${AD_BIND_PASSWORD:?AD_BIND_PASSWORD muss fuer die Active-Directory-Anmeldung gesetzt sein}"
    : "${JENKINS_ADMIN_GROUP:?JENKINS_ADMIN_GROUP muss gesetzt sein}"
    : "${JENKINS_AUTHENTICATED_GROUP:?JENKINS_AUTHENTICATED_GROUP muss gesetzt sein}"
    ;;
  *)
    echo "Unbekannter JENKINS_RUNTIME_MODE: $runtime_mode (erlaubt: dev, production)" >&2
    exit 1
    ;;
esac

exec /usr/bin/tini -- /usr/local/bin/jenkins.sh "$@"
