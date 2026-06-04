# datenportal-jenkins-dev

Kanonisches Jenkins-Controller- und Image-Repo fuer das Datenportal-Plugin.

Dieses Repo ist die zentrale Stelle fuer:

- lokales Jenkins-Starten ohne Docker
- Jenkins-Controller-Image-Build
- Jenkins-Plugins und JCasC
- Offline-Bundle-Assembly fuer GRETL- und Drittplugins

Das Themenrepo bleibt Consumer. Die Source of Truth fuer Plugin-Versionen,
Repository-URLs und Offline-Seed-Koordinaten liegt in
[`shared/gradle/gradle-build.properties`](/Users/stefan/sources/datenportal-themenrepo/shared/gradle/gradle-build.properties)
im Repo `datenportal-themenrepo`.

Die Pflege neuer Maven-Repositories und zusaetzlicher Gradle-Plugins ist dort
ebenfalls dokumentiert. Dieses Repo beschreibt nur Bundle-Bau, Jenkins-Start
und Image-Bau, nicht den Wartungs-Workflow des Gradle-Build-Contracts.

## Voraussetzungen

- Java 17 fuer Jenkins und GRETL/Gradle
- Maven nur fuer den Jenkins-Plugin-Build
- Git
- curl
- Docker nur fuer den Image-Build

## Plugin bauen

```bash
cd /Users/stefan/sources/jenkins-gretl-datenportal-plugin
export JAVA_HOME="$HOME/.sdkman/candidates/java/17.0.10-tem"
export PATH="$JAVA_HOME/bin:$PATH"
mvn -ntp package
```

## Plugin lokal installieren

```bash
cd /Users/stefan/sources/datenportal-jenkins-dev
./bin/install-gretl-datenportal-plugin.sh
```

## Offline-Bundle bauen

```bash
cd /Users/stefan/sources/datenportal-jenkins-dev
./bin/build-offline-bundle.sh
```

Das erzeugt standardmaessig:

- `build/offline-bundle/jars`
- `build/offline-bundle/gradle-user-home`
- `build/offline-bundle/resolved-manifest.json`

`resolved-manifest.json` dokumentiert die effektiv aufgeloesten und gestagten
Plugin- und Runtime-Jars.

## Jenkins lokal starten

```bash
cd /Users/stefan/sources/datenportal-jenkins-dev
./bin/start.sh
```

`start.sh` baut oder aktualisiert zuerst das Offline-Bundle und exportiert dann:

- `DATENPORTAL_OFFLINE_JARS_DIR`
- `GRADLE_USER_HOME`
- `THEMEN_REPO_URL`
- `THEMEN_REPO_BRANCH`

Dann oeffnen:

```text
http://localhost:8080
```

Login:

```text
admin / admin
```

## Docker-Image bauen

```bash
cd /Users/stefan/sources/datenportal-jenkins-dev
./bin/build-image.sh
```

Der Build staged:

- das vorbereitete Offline-Bundle
- `plugins.txt`
- `casc/jenkins.yaml`
- das Themenrepo als lokales Git-Quellrepo
- das lokale `jenkins-gretl-datenportal-plugin.hpi`

Default-Image-Name:

```text
datenportal-jenkins-dev:local
```

Das Basisimage ist standardmaessig `jenkins/jenkins:lts-jdk17`, weil der
versionierte Tag `jenkins/jenkins:2.555.2-lts` aktuell Java 21 enthaelt.
Falls ein exakt gepinntes JDK-17-Image verwendet werden soll, kann
`JENKINS_IMAGE` beim Aufruf gesetzt werden.

Zur Laufzeit sollte fuer echte Airgap-Tests zusaetzlich ein no-network-Modus
verwendet werden, z. B. `docker run --network none ...`.

## Seed-Job

Der lokale Generator-Job heisst:

```text
gretl-datenportal-plugin-generator-local
```

Nach einem Lauf sollten mindestens diese Jobs vorhanden sein:

```text
gretl-datenportal-afu
gretl-datenportal-statistikdienst
```
