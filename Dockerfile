ARG JENKINS_IMAGE=jenkins/jenkins:2.555.2-lts-jdk21
FROM ${JENKINS_IMAGE}

ARG TARGETARCH
ARG IMAGE_VERSION=local
ARG PLUGIN_VERSION=0.1.0-SNAPSHOT
ARG GRETL_VERSION=5.0.0-SNAPSHOT
ARG THEMEN_REPO_REVISION=unknown
ARG PLUGIN_REPO_REVISION=unknown
ARG TEMURIN17_VERSION=17.0.15+6

LABEL org.opencontainers.image.title="datenportal-jenkins" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      io.datenportal.plugin.version="${PLUGIN_VERSION}" \
      io.datenportal.gretl.version="${GRETL_VERSION}" \
      io.datenportal.themenrepo.revision="${THEMEN_REPO_REVISION}" \
      io.datenportal.plugin.revision="${PLUGIN_REPO_REVISION}"

USER root

ENV TZ=Europe/Zurich \
    DUCKDB_EXTENSION_DIRECTORY=/opt/datenportal/duckdb-extensions

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl git tar tzdata \
    && ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "${TZ}" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && case "$TARGETARCH" in \
         amd64) adoptium_arch='x64' ;; \
         arm64) adoptium_arch='aarch64' ;; \
         *) echo "Unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && temurin_version="jdk-${TEMURIN17_VERSION}" \
    && temurin_url="https://api.adoptium.net/v3/binary/version/${temurin_version}/linux/${adoptium_arch}/jdk/hotspot/normal/eclipse" \
    && checksum_url="https://api.adoptium.net/v3/checksum/version/${temurin_version}/linux/${adoptium_arch}/jdk/hotspot/normal/eclipse" \
    && curl -fsSL -o /tmp/temurin17.tar.gz "$temurin_url" \
    && curl -fsSL -o /tmp/temurin17.sha256 "$checksum_url" \
    && expected_checksum="$(awk '{print $1}' /tmp/temurin17.sha256)" \
    && printf '%s  %s\n' "$expected_checksum" /tmp/temurin17.tar.gz | sha256sum -c - \
    && mkdir -p /opt/java/openjdk17 \
    && tar -xzf /tmp/temurin17.tar.gz --strip-components=1 -C /opt/java/openjdk17 \
    && rm /tmp/temurin17.tar.gz /tmp/temurin17.sha256 \
    && mkdir -p /opt/datenportal /usr/share/jenkins/ref/casc_configs /usr/share/jenkins/ref/plugins

COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
COPY --chown=jenkins:jenkins jenkins.yaml /usr/share/jenkins/ref/casc_configs/jenkins.yaml
COPY --chown=root:root configure-duckdb-extensions.sh /usr/local/bin/configure-duckdb-extensions.sh
COPY --chown=root:root docker-entrypoint.sh /usr/local/bin/datenportal-jenkins-entrypoint.sh
COPY --chown=jenkins:jenkins offline-bundle/ /opt/datenportal/offline-bundle/
COPY --chown=jenkins:jenkins jenkins-gretl-datenportal-plugin.jpi /usr/share/jenkins/ref/plugins/jenkins-gretl-datenportal-plugin.jpi

RUN chmod 0755 /usr/local/bin/datenportal-jenkins-entrypoint.sh /usr/local/bin/configure-duckdb-extensions.sh \
    && mkdir -p "${DUCKDB_EXTENSION_DIRECTORY}" \
    && chown -R jenkins:jenkins /opt/datenportal /usr/share/jenkins/ref

USER jenkins

RUN /opt/java/openjdk17/bin/java \
    -cp '/opt/datenportal/offline-bundle/jars/*' \
    ch.so.agi.gretl.internal.duckdb.DuckDbExtensionInstaller postgres spatial excel

USER root
RUN chown -R root:root "${DUCKDB_EXTENSION_DIRECTORY}" \
    && chmod -R a+rX,a-w "${DUCKDB_EXTENSION_DIRECTORY}"
USER jenkins

RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

ENV CASC_JENKINS_CONFIG=/usr/share/jenkins/ref/casc_configs/jenkins.yaml \
    JENKINS_RUNTIME_MODE=production \
    THEMEN_REPO_MODE=managed-git \
    THEMEN_REPO_BRANCH=main \
    DATENPORTAL_MODELS_DIR=/opt/datenportal/offline-bundle/models \
    DATENPORTAL_OFFLINE_JARS_DIR=/opt/datenportal/offline-bundle/jars \
    GRADLE_USER_HOME=/opt/datenportal/offline-bundle/gradle-user-home \
    GRADLE_JAVA_HOME_17=/opt/java/openjdk17 \
    JENKINS_JAVA_OPTS=-Djenkins.install.runSetupWizard=false

ENTRYPOINT ["/usr/local/bin/datenportal-jenkins-entrypoint.sh"]
