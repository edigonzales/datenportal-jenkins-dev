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
  [datenportal-jenkins-gretl-plugin](https://codeberg.org/edigonzales/datenportal-jenkins-gretl-plugin)

## Zentrale Workflows

### Jenkins lokal starten

```bash
cd ../datenportal-jenkins-dev
./bin/start.sh
```

`start.sh` baut oder aktualisiert zuerst das Offline-Bundle, installiert die
Jenkins-Plugins und startet danach Jenkins mit Java 21. Fuer GRETL und Gradle
exportiert das Skript separat Java 17.

Das vorhandene Home wird dabei wiederverwendet. Fuer einen isolierten Neustart
mit leerer Konfiguration:

```bash
cd ../datenportal-jenkins-dev
./bin/start-fresh.sh
```

Das Skript setzt eine zuvor gebaute Plugin-HPI unter
`../datenportal-jenkins-gretl-plugin/target/` voraus und legt sie automatisch im
frischen Home ab. Ein abweichender Build kann mit
`PLUGIN_HPI_SOURCE=/pfad/zur/plugin.hpi` angegeben werden.

`start-fresh.sh` leert ausschliesslich ein Home unter `build/`; das versionierte
`jenkins-home/` bleibt erhalten. Ein anderes bestehendes Home kann mit
`JENKINS_HOME_DIR=/pfad/zum/home ./bin/start.sh` verwendet werden.

### Plugin aus dem Schwester-Repo installieren

```bash
cd ../datenportal-jenkins-gretl-plugin
export JAVA_HOME="${JAVA21_HOME:-$HOME/.sdkman/candidates/java/current}"
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
| `agi-user` | `agi` | Lesen und Bauen des AGI-Jobs |
| `mfk-user` | `mfk` | Lesen und Bauen des MFK-Jobs |
| `statistikdienst-user` | `statistikdienst` | Lesen und Bauen des Statistikdienst-Jobs |

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

Der Seed-Lauf kennt zwei Modi. `managed-git` ist der produktionsnahe Default:
Jenkins aktualisiert seinen internen Checkout mit dem committed Stand des
konfigurierten Branches. `working-tree` ist nur für lokale Entwicklung gedacht:
Beim Seed-Lauf wird der externe Arbeitsbaum inklusive uncommitteter und
untracked Änderungen in einen Jenkins-internen Snapshot kopiert. Das externe
Themenrepo wird dabei nicht verändert; der Snapshot bleibt bis zum nächsten
Seed-Lauf unverändert. Für einen lokalen Test mit diesem Modus:

```bash
THEMEN_REPO_MODE=working-tree ./bin/start.sh
```

Im produktionsnahen Modus müssen Änderungen committen und auf dem konfigurierten
Branch bereitgestellt werden. Danach den Seed-Job zuerst als `admin / admin`
starten und die ACLs mit
`seed-user / seed`, `read-user / read`, `agi-user / agi`, `mfk-user / mfk`
und `statistikdienst-user / statistikdienst` prüfen. Die
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

Das gemeinsame Image heisst `datenportal-jenkins`. Der lokale Default-Tag ist
`datenportal-jenkins:local`; für die Registry kann `IMAGE_NAME` und
`IMAGE_VERSION` gesetzt werden. Es unterstützt die Laufzeitmodi
`JENKINS_RUNTIME_MODE=dev` und `JENKINS_RUNTIME_MODE=production`. Im
Produktionsmodus prüft der Entrypoint die AD- und Deployment-Variablen; im
Dev-Modus wird die lokale JCasC von aussen gemountet.

Das Image enthält den Jenkins-Controller, Java 17 für GRETL, das vorbereitete
Offline-Bundle und das beim Image-Bau installierte Datenportal-Plugin. Das
Themenrepo wird nicht in das Image kopiert, sondern zur Laufzeit über
`THEMEN_REPO_URL`/`THEMEN_REPO_PATH` und `THEMEN_REPO_BRANCH` gesetzt. Für das
Bauen des Offline-Bundles dient `THEMEN_REPO_DIR` weiterhin als lokale
Build-Quelle.

Das Image verwendet `Europe/Zurich` als Systemzeitzone. Damit verwenden Jenkins,
Gradle und Konsolenlogs automatisch CET beziehungsweise CEST.

Das Image installiert die DuckDB-Extensions `postgres`, `spatial` und `excel`
beim Build mit dem JDBC-Treiber aus dem Offline-Bundle. Sie liegen unter
`/opt/datenportal/duckdb-extensions`, ausserhalb des Jenkins-Homes, und sind
zur Laufzeit nur lesbar. `DUCKDB_EXTENSION_DIRECTORY` macht diesen Pfad fuer
GRETL verfuegbar; Jobs verwenden weiterhin `installExtensions false`.

`build-image.sh` prueft das gebaute Image automatisch ohne Netzwerk: Alle drei
Extensions werden geladen, und ein echter GRETL-Task exportiert CSV nach XLSX
und Parquet. Die Exporte werden anschliessend inhaltlich geprueft. Der Test
kann separat wiederholt werden:

```bash
./bin/test-image-duckdb.sh datenportal-jenkins:local
```

Der Test verwendet `THEMEN_REPO_DIR` (Default `../datenportal-themenrepo`)
fuer Wrapper und Gradle-Initialisierung. Er benoetigt Docker, aber kein
bestehendes Jenkins-Home. Die technischen Fixtures unter `tests/duckdb` dienen
ausschliesslich der Laufzeitpruefung; sie definieren keinen Publikationsjob.
Das direkte Starten von Jenkins auf dem Host installiert diese
plattformspezifischen Extensions nicht.

Die Pluginquelle ist konfigurierbar:

* `PLUGIN_SOURCE=local` baut den Checkout unter `PLUGIN_REPO` und installiert
  dessen HPI;
* `PLUGIN_SOURCE=maven` löst `PLUGIN_GROUP`, `PLUGIN_ARTIFACT` und
  `PLUGIN_VERSION` aus `PLUGIN_REPOSITORY_URL` auf;
* `PLUGIN_SOURCE=auto` bevorzugt den lokalen Checkout und verwendet sonst
  Maven.

Beispiel für den veröffentlichten Snapshot:

```bash
PLUGIN_SOURCE=maven \
PLUGIN_VERSION=0.1.0-SNAPSHOT \
PLUGIN_REPOSITORY_URL=https://jars.interlis.guru/snapshots \
./bin/build-image.sh
```

Das HPI wird ausschliesslich beim Image-Bau installiert. GRETL `5.0.0-SNAPSHOT`
und die übrigen Gradle-/GRETL-Artefakte werden beim Offline-Bundle-Bau aus den
im Themenrepo definierten Repositories geladen und zur Laufzeit offline
verwendet.

## Langform-Doku

Die technische Langform-Doku liegt unter
[docs/biblios/entwicklung/index.adoc](docs/biblios/entwicklung/index.adoc).

## Schwester-Repositories

- [datenportal-themenrepo](https://codeberg.org/edigonzales/datenportal-themenrepo)
  ist die kanonische Doku fuer Organisationsstruktur, Datensaetze,
  `gretl-datenportal-job.yaml`, `shared/gretl-datenportal-teams.yaml`,
  `shared/Jenkinsfile` und den Gradle-Build-Vertrag.
- [datenportal-jenkins-gretl-plugin](https://codeberg.org/edigonzales/datenportal-jenkins-gretl-plugin)
  ist die kanonische Doku fuer Scanner, Startformular, Rechtepruefung,
  Seed-Builder und generierte Jenkins-Jobs.

### SQL-Lieferverarbeitung offline prüfen

```bash
./bin/test-image-publication.sh datenportal-jenkins:local
# Alternativ nach dem Image-Bau automatisch ausführen:
RUN_PUBLICATION_TESTS=1 ./bin/build-image.sh
```

Die Prüfung verwendet die Arbeitsstände der Schwester-Repositories
`datenportal-themenrepo` und `datenportal-pilot-daten`, eine temporäre Kopie und
ein separates lokales Bare-Repository. Alle GRETL-Prozesse laufen ohne Netzwerk.
Details zu Modellen, Extensions und Ergebnissen stehen in der
[Offline-Bundle-Dokumentation](docs/biblios/entwicklung/offline-bundle.adoc).
