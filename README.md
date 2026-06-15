# datenportal-jenkins-dev

Lokales Jenkins-Controller- und Integrationsrepo fuer das GRETL-Datenportal.

## Rolle im Gesamtsystem

Dieses Repo ist die technische Laufzeitumgebung fuer lokale Entwicklung und
Offline-Tests.

Hierher gehoeren:

- lokaler Jenkins-Controller, `casc/jenkins.yaml` und `plugins.txt`
- Offline-Bundle fuer GRETL, Gradle-Wrapper und Plugin-Runtimes
- Plugin-Installations- und Restart-Loop fuer lokales Testen
- Docker-Image fuer reproduzierbare Jenkins- und Airgap-Tests

Nicht hierher gehoeren:

- der fachliche Vertrag des Themenrepos:
  [datenportal-themenrepo](https://codeberg.org/edigonzales/datenportal-themenrepo)
- die Implementierung des Jenkins-Plugins:
  [jenkins-gretl-datenportal-plugin](https://codeberg.org/edigonzales/jenkins-gretl-datenportal-plugin)

## Zentrale Workflows

### Jenkins lokal starten

```bash
cd ../datenportal-jenkins-dev
./bin/start.sh
```

`start.sh` baut oder aktualisiert zuerst das Offline-Bundle, installiert die
Jenkins-Plugins und startet danach Jenkins mit Java 21. Fuer GRETL und Gradle
exportiert das Skript separat Java 17.

### Plugin aus dem Schwester-Repo installieren

```bash
cd ../jenkins-gretl-datenportal-plugin
export JAVA_HOME="$HOME/.sdkman/candidates/java/21.0.10-tem"
export PATH="$JAVA_HOME/bin:$PATH"
mvn -ntp package

cd ../datenportal-jenkins-dev
./bin/install-gretl-datenportal-plugin.sh
```

Wenn Jenkins bereits laeuft, ist anschliessend ein voller Restart noetig.

### Offline-Bundle separat bauen

```bash
cd ../datenportal-jenkins-dev
./bin/build-offline-bundle.sh
```

Das Bundle landet standardmaessig unter `build/offline-bundle/`.

### Docker-Image bauen

```bash
cd ../datenportal-jenkins-dev
./bin/build-image.sh
```

Das Image enthaelt den lokalen Jenkins-Controller, das vorbereitete
Offline-Bundle, das Themenrepo als Git-Quelle und das lokal gebaute Plugin.

## Langform-Doku

Die technische Langform-Doku liegt unter
[docs/biblios/entwicklung/index.adoc](docs/biblios/entwicklung/index.adoc).

## Schwester-Repositories

- [datenportal-themenrepo](https://codeberg.org/edigonzales/datenportal-themenrepo)
  ist die kanonische Doku fuer Organisationsstruktur, Datensaetze,
  `gretl-datenportal-job.yaml`, `shared/Jenkinsfile` und den Gradle-Build-Vertrag.
- [jenkins-gretl-datenportal-plugin](https://codeberg.org/edigonzales/jenkins-gretl-datenportal-plugin)
  ist die kanonische Doku fuer Scanner, Startformular, Rechtepruefung,
  Seed-Builder und generierte Jenkins-Jobs.
