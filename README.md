# datenportal-jenkins-dev

Lokales Jenkins-WAR-Setup fuer das Datenportal-Plugin.

Dieses Setup ist bewusst klein:

- kein Docker
- kein OpenShift
- kein Agent-Setup
- Jenkins laeuft lokal mit `java -jar jenkins.war`
- das Themenrepo wird vom Plugin per `file://` ausgecheckt
- neue Jobs entstehen ueber einen manuellen Seed-Job

## Voraussetzungen

- Java 21
- Git
- curl

## Plugin bauen

```bash
cd /Users/stefan/sources/jenkins-gretl-datenportal-plugin
export JAVA_HOME="$HOME/.sdkman/candidates/java/21.0.7-tem"
export PATH="$JAVA_HOME/bin:$PATH"
mvn -ntp package
```

## Plugin lokal installieren

```bash
cd /Users/stefan/sources/datenportal-jenkins-dev
./bin/install-gretl-datenportal-plugin.sh
```

## Jenkins starten

```bash
cd /Users/stefan/sources/datenportal-jenkins-dev
./bin/start.sh
```

Dann oeffnen:

```text
http://localhost:8080
```

Login:

```text
admin / admin
```

## Seed-Job

Der lokale Generator-Job heisst:

```text
gretl-datenportal-plugin-generator-local
```

Er verwendet das Plugin-BuildStep und das lokale Repo:

```text
file:///Users/stefan/sources/datenportal-themenrepo
```

Nach einem Lauf sollten mindestens diese Jobs vorhanden sein:

```text
gretl-datenportal-afu
gretl-datenportal-statistikdienst
```

Wenn du im Repo `datenportal-themenrepo` neue Organisationen oder Datensaetze
hinzufuegst, committe die Aenderung und fuehre den Seed-Job erneut aus. Ein
Jenkins-Neustart ist dafuer nicht noetig.
