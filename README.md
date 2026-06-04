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

### Wie der Offline-Gradle-Start funktioniert

Das Offline-Bundle besteht bewusst aus zwei verschiedenen Teilen:

- `build/offline-bundle/gradle-user-home`
- `build/offline-bundle/jars`

Rollen:

- `gradle-user-home` enthaelt die vom Themenrepo-Wrapper benoetigte
  Gradle-Distribution und die zugehoerigen Wrapper-Caches.
- `jars` enthaelt die offline vorbereiteten Plugin- und Runtime-Jars.

Der Laufzeitvertrag ist:

1. Jenkins checkt das Themenrepo aus.
2. `shared/Jenkinsfile` startet im Repo-Root `./gradlew`.
3. Der Wrapper sucht seine Distribution unter `GRADLE_USER_HOME/wrapper/dists`.
4. `shared/gradle/init.gradle` bindet `DATENPORTAL_OFFLINE_JARS_DIR` fuer
   `initscript` und `pluginManagement` ein.

Wichtig:

- Das Image ersetzt den Wrapper nicht durch ein global installiertes `gradle`.
- Der Wrapper bleibt der Launcher.
- `build-offline-bundle.sh` waermt den benoetigten Wrapper-Cache gezielt vor.

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

## Maintainer-Workflow nach Plugin-Aenderungen

Wenn sich das Jenkins-Plugin in
`/Users/stefan/sources/jenkins-gretl-datenportal-plugin` geaendert hat, ist der
volle lokale Ablauf:

1. Plugin-HPI neu bauen.
2. HPI in die lokale Jenkins-Installation kopieren.
3. Jenkins neu starten.
4. Seed-Job erneut ausfuehren.
5. Datenportal-UI oeffnen und einen generierten Job starten.

```bash
cd /Users/stefan/sources/jenkins-gretl-datenportal-plugin
source "$HOME/.sdkman/bin/sdkman-init.sh"
sdk use java 21.0.10-tem
mvn -ntp package

cd /Users/stefan/sources/datenportal-jenkins-dev
./bin/install-gretl-datenportal-plugin.sh
./bin/start.sh
```

Dann in Jenkins:

1. `gretl-datenportal-plugin-generator-local` ausfuehren.
2. `/gretl-datenportal` oeffnen.
3. Einen Datensatz auswaehlen.
4. Mindestens `METADATA_FILE` oder `DATA_FILE` hochladen.
5. Den Job starten.

Hinweise:

- Wenn Jenkins schon laeuft, reicht das Ueberschreiben der `.jpi` nicht; ein
  Restart ist notwendig.
- Der Seed-Lauf ist noetig, damit bestehende generierte Jobs neue
  Pipeline-Inhalte oder neue Plugin-Logik uebernehmen.

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
