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

### Seed-Job

Nach dem Jenkins-Start legt das Plugin den Job `gretl-datenportal-seed`
automatisch an. Der Job:

- ist aktiviert, sobald `THEMEN_REPO_URL` oder ein Pfad konfiguriert ist;
- laeuft per Cron `H/15 * * * *`;
- kann fuer sofortige lokale Tests manuell gestartet werden.

Der Seed-Job wird nicht mehr per JCasC/Job-DSL erzeugt. Fuer bestehende lokale
Jenkins-Homes kann der alte Job `gretl-datenportal-plugin-generator-local`
manuell geloescht werden; relevant ist neu ausschliesslich
`gretl-datenportal-seed`.

Die lokale JCasC-Konfiguration verwendet die projektbezogene Matrix-
Autorisierung aus `matrix-auth`. Die Testkonten sind:

| Benutzer | Passwort | Zweck |
|---|---|---|
| `admin` | `admin` | Jenkins-Administrator und Bootstrap |
| `seed-user` | `seed` | Mitglied des konfigurierten Seeder-Teams |
| `read-user` | `read` | Nur Lesezugriff auf Organisationen |
| `afu-user` | `afu` | Lesen und Bauen des AFU-Jobs |
| `statistikdienst-user` | `statistikdienst` | Für das Statistikdienst-Fixture vorbereitet; aktuell wird daraus kein Job erzeugt |

Für lokale Tests ist keine AD-/LDAP-Umgebung nötig: JCasC verwendet den lokalen
Security-Realm und legt diese Konten beim Start an. Normale Benutzer erhalten
global nur `Overall/Read`. `Item/Read` und
`Item/Build` kommen ausschliesslich aus den ACLs der vom Plugin verwalteten
Jobs. Das lokale Seeder-Team wird über
`seedJobOperatorsTeam: gretl-datenportal-seed-operators` referenziert und in
`shared/gretl-datenportal-teams.yaml` des Themenrepos definiert. Der erste
Seed-Lauf wird mit `admin` ausgeführt; danach wird auch die ACL des Seeder-Jobs
aus der Teams-Datei synchronisiert. Die Teammitglieder werden über ihre
Jenkins-Benutzer-IDs aufgelöst; in einer produktiven Umgebung müssen diese IDs
zur konfigurierten AD-/LDAP-/Entra-Authentisierungsquelle passen.

Der Seed-Lauf verarbeitet den committed Git-Stand des konfigurierten Branches.
Uncommitted Änderungen im Themenrepo werden nicht verarbeitet. Für einen
lokalen Test daher: Änderungen committen, `./bin/start.sh` ausführen, den
Seed-Job zuerst als `admin / admin` starten und danach die ACLs mit
`seed-user / seed`, `read-user / read` und `afu-user / afu` prüfen. Die
vollständige Anleitung steht in
`docs/biblios/entwicklung/lokaler-jenkins-start.adoc`.

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
  `gretl-datenportal-job.yaml`, `shared/gretl-datenportal-teams.yaml`,
  `shared/Jenkinsfile` und den Gradle-Build-Vertrag.
- [jenkins-gretl-datenportal-plugin](https://codeberg.org/edigonzales/jenkins-gretl-datenportal-plugin)
  ist die kanonische Doku fuer Scanner, Startformular, Rechtepruefung,
  Seed-Builder und generierte Jenkins-Jobs.
