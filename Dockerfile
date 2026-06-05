ARG JENKINS_IMAGE=jenkins/jenkins:lts-jdk21
FROM ${JENKINS_IMAGE}

ARG TARGETARCH

USER root

RUN case "$TARGETARCH" in \
      amd64) adoptium_arch='x64' ;; \
      arm64) adoptium_arch='aarch64' ;; \
      *) echo "Unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && mkdir -p /opt/java \
    && curl -fsSL -o /tmp/temurin17.tar.gz "https://api.adoptium.net/v3/binary/latest/17/ga/linux/${adoptium_arch}/jdk/hotspot/normal/eclipse" \
    && mkdir -p /opt/java/openjdk17 \
    && tar -xzf /tmp/temurin17.tar.gz --strip-components=1 -C /opt/java/openjdk17 \
    && rm /tmp/temurin17.tar.gz \
    && mkdir -p /opt/datenportal \
    /usr/share/jenkins/ref/casc_configs \
    /usr/share/jenkins/ref/plugins

COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
COPY --chown=jenkins:jenkins casc/ /usr/share/jenkins/ref/casc_configs/
COPY --chown=jenkins:jenkins offline-bundle/ /opt/datenportal/offline-bundle/
COPY --chown=jenkins:jenkins topic-repo-source/ /opt/datenportal/topic-repo-source/
COPY --chown=jenkins:jenkins jenkins-gretl-datenportal-plugin.jpi /usr/share/jenkins/ref/plugins/jenkins-gretl-datenportal-plugin.jpi

RUN chown -R jenkins:jenkins /opt/datenportal /usr/share/jenkins/ref

USER jenkins

RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

ENV CASC_JENKINS_CONFIG=/usr/share/jenkins/ref/casc_configs/jenkins.yaml \
    THEMEN_REPO_URL=file:///opt/datenportal/topic-repo-source \
    THEMEN_REPO_BRANCH=main \
    DATENPORTAL_OFFLINE_JARS_DIR=/opt/datenportal/offline-bundle/jars \
    GRADLE_USER_HOME=/opt/datenportal/offline-bundle/gradle-user-home \
    GRADLE_JAVA_HOME_17=/opt/java/openjdk17 \
    JAVA_OPTS=-Djenkins.install.runSetupWizard=false
