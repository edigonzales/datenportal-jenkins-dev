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

- Java 21 fuer Jenkins und den Jenkins-Plugin-Build
- Java 17 fuer GRETL/Gradle und das Offline-Bundle
- Maven nur fuer den Jenkins-Plugin-Build
- Git
- curl
- Docker nur fuer den Image-Build

Optionale lokale Overrides:

- `JAVA21_HOME` fuer den Jenkins-Controller
- `JAVA17_HOME` fuer GRETL/Gradle

## Plugin bauen

```bash
cd /Users/stefan/sources/jenkins-gretl-datenportal-plugin
export JAVA_HOME="$HOME/.sdkman/candidates/java/21.0.10-tem"
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
2. `shared/Jenkinsfile` startet im Repo-Root `shared/bin/gradlew-java17.sh`.
3. Der Wrapper sucht seine Distribution unter `GRADLE_USER_HOME/wrapper/dists`.
4. `shared/gradle/init.gradle` bindet `DATENPORTAL_OFFLINE_JARS_DIR` fuer
   `initscript` und `pluginManagement` ein.

Wichtig:

- Das Image ersetzt den Wrapper nicht durch ein global installiertes `gradle`.
- Der Wrapper bleibt der Launcher; Jenkins ruft ihn explizit ueber den
  Java-17-Wrapper `shared/bin/gradlew-java17.sh` auf.
- `build-offline-bundle.sh` waermt den benoetigten Wrapper-Cache gezielt vor.

## Jenkins lokal starten

```bash
cd /Users/stefan/sources/datenportal-jenkins-dev
./bin/start.sh
```

`start.sh` loest zuerst Java 17 fuer GRETL/Gradle und Java 21 fuer Jenkins auf,
baut dann das Offline-Bundle und exportiert anschliessend:

- `DATENPORTAL_OFFLINE_JARS_DIR`
- `GRADLE_USER_HOME`
- `GRADLE_JAVA_HOME_17`
- `THEMEN_REPO_URL`
- `THEMEN_REPO_BRANCH`

`JAVA17_HOME` und `JAVA21_HOME` koennen gesetzt werden, um die jeweilige
Auto-Erkennung lokal zu uebersteuern.

Dann oeffnen:

```text
http://localhost:8080
```

Login:

```text
admin / admin
```

Bootstrap nach frischem Checkout:

1. Jenkins starten.
2. In Jenkins den Seed-Job `gretl-datenportal-plugin-generator-local` ausfuehren.
3. Danach das Datenportal unter `/gretl-datenportal` oeffnen und einen generierten Job starten.

Wichtig:

- `jenkins-home/jobs` ist bewusst nicht versioniert. Generierte Jobs und Build-Historien bleiben lokal.
- Nach einem frischen Checkout ist zunaechst nur der per JCasC erzeugte Seed-Job vorhanden.
- Das lokal geklonte Themenrepo unter `jenkins-home/gretl-datenportal` bleibt ebenfalls unversioniert.

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
- Auch auf einem frischen Checkout ist der Seed-Lauf der verpflichtende
  Bootstrap-Schritt fuer alle generierten Jobs.

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

Das Basisimage ist standardmaessig `jenkins/jenkins:${JENKINS_VERSION}-lts`.
Dieses Image bringt Jenkins auf Java 21, waehrend das Dockerfile zusaetzlich
ein Temurin-JDK-17 nach `/opt/java/openjdk17` laedt und als
`GRADLE_JAVA_HOME_17` fuer GRETL/Gradle exportiert.

Zur Laufzeit sollte fuer echte Airgap-Tests zusaetzlich ein no-network-Modus
verwendet werden, z. B. `docker run --network none ...`.

## Seed-Job

Der lokale Generator-Job heisst:

```text
gretl-datenportal-plugin-generator-local
```

Dieser Seed-Job wird beim lokalen Start ueber `casc/jenkins.yaml` angelegt.
Die generierten Jobs selbst werden nicht versioniert.

Nach einem Lauf sollten mindestens diese Jobs vorhanden sein:

```text
gretl-datenportal-afu
gretl-datenportal-statistikdienst
```
