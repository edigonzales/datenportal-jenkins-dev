# Multiarch-Prüfstand vom 28. September 2026

## Ausgangspunkt

Codeberg ist die führende Quelle. Das zuvor saubere lokale Repository wurde
von `76c581a` per Fast-forward auf `58d9930` aktualisiert; der GitHub-Mirror
hat denselben Ausgangsstand. Die Workflow-Änderungen liegen lokal in diesem
Codeberg-Checkout. Es wurde weder gepusht noch ein GitHub-Lauf gestartet.

## Erfolgreiche Prüfungen

- `actionlint` 1.7.12: Workflow gültig, einschliesslich Expressions, Matrix
  und Job-Abhängigkeiten.
- `python3 -m unittest discover -s tests`: 16 Tests bestanden.
  Neben der Versionsauflösung: vorbereiteter Kontext ohne neue Auflösung,
  Plattformprüfung, Fehlerweitergabe der Offline-Tests, macOS-Bash-3.2-
  Kompatibilität ohne Plattformangabe, vollständige Registry-Vorprüfung und
  digestbasierte Manifestzusammenführung. Registry-Schreiboperationen in
  diesen Tests sind Mock-Aufrufe, keine Veröffentlichung.
- Bash-Syntax der Buildskripte und `git diff --check` erfolgreich.
- `prepare-image-context.sh` mit Maven-Plugin `0.1.0-SNAPSHOT`, GRETL
  `5.0.0-SNAPSHOT` und Themenrepo `a354547` erfolgreich ausgeführt.
- `IMAGE_PLATFORM=linux/arm64` mit Buildx und `--prepared-context` erfolgreich
  nativ auf Docker Desktop/Apple Silicon gebaut. Lokaler Tag:
  `datenportal-jenkins:multiarch-check`, lokale Image-ID
  `sha256:0cfbb378ee6d260172c047e81dc73dd2b724805e287f77128fa3b197665b6c84`.
  Dies ist keine veröffentlichte Registry-Referenz.
- Java-17-/DuckDB-Offline-Tests im neuen Image erfolgreich: fünf Extensions aus
  `v1.5.2/linux_arm64`, Playground-Prüfung, CSV→Parquet/XLSX per GRETL,
  Inhaltsprüfung beider Exporte sowie erwartete Ablehnung bei fehlender
  Excel-Extension. Keine S3-Publikation.

Lokale ausführliche Logs liegen als ignorierte Artefakte unter
`build/multiarch-prepare.log` und `build/multiarch-arm64.log`.

## Noch auszuführen

Nach Übernahme nach Codeberg und Spiegelung nach GitHub muss der erste reale
Workflow-Lauf beide nativen Runner und das Zusammenführen/Verifizieren in
Docker Hub und GHCR bestätigen. Die lokalen Tests beweisen keinen erfolgreichen
Push. Erst danach den neuen gemeinsamen Manifest-Digest im CRC-/Betreiber-
Stack verwenden. Für Wiederholungen alle Workflow-Jobs erneut ausführen.
Sodata wurde nicht verändert; dessen ARM64-Release bleibt eine eigene Aufgabe.

## Bestehende Pluginwarnungen

`jenkins-plugin-cli` meldet beim Imagebau Sicherheitswarnungen zu vorhandenen
Pins unter anderem für `script-security`, `file-parameters`,
`pipeline-groovy-lib`, `pipeline-build-step` und `workflow-multibranch`.
`plugins.txt` wurde für diese Architekturänderung nicht geändert. Pluginupdates
und deren Kompatibilitätsprüfung sind vor einer produktiven Freigabe separat
zu behandeln. Die detaillierten Meldungen stehen im Buildlog.
