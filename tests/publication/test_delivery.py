#!/usr/bin/env python3
"""Real GRETL/ili2duckdb delivery sequences without networking; candidates are promoted only by this test."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

RUNTIME = Path(__file__).resolve().parents[2]
TOPICS = Path(os.environ.get('THEMEN_REPO_DIR', RUNTIME.parent / 'datenportal-themenrepo')).resolve()
PILOT = Path(os.environ.get('PILOT_REPO_DIR', RUNTIME.parent / 'datenportal-pilot-daten')).resolve()
IMAGE = sys.argv[1] if len(sys.argv) > 1 else 'datenportal-jenkins:local'
(RUNTIME / 'build').mkdir(exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix='publication-test-', dir=RUNTIME / 'build'))
shutil.copy(RUNTIME / 'tests/publication/VerifyExports.java', WORK)
REPO = WORK / 'repo'
shutil.copytree(TOPICS, REPO, ignore=shutil.ignore_patterns('.git', '.gradle', 'build', '.DS_Store'))
# Identical filenames in different topics are legal; ili2db dataset names must not collide.
for source in (REPO/'agi').glob('*/*.xtf'):
    source.rename(source.with_name('datenblatt.xtf'))
# Tests intentionally exercise bootstrap, independent of any catalog in the source snapshot.
STATE = WORK / 'accepted'
STATE.mkdir()
CATALOG = STATE / 'catalog.xtf'
DATASET = 'ch.so.bevoelkerung.altersstruktur'
RELATIVE = Path('statistikdienst') / DATASET / ('meta-' + DATASET + '.xtf')
SHEET = REPO / RELATIVE
OUTPUT = REPO / 'statistikdienst/build/publication/outputs'
CSV = '/pilot/' + DATASET + '/so_bevo_altersstruktur_2025.csv'
NS = 'http://www.interlis.ch/xtf/2.4/SO_AGI_DataCatalog_Datasheet_20260523'
ET.register_namespace('', NS)
ET.register_namespace('base', 'http://www.interlis.ch/xtf/2.4/SO_AGI_DataCatalog_Base_20260529')
ET.register_namespace('ili', 'http://www.interlis.ch/xtf/2.4/INTERLIS')
sequence = 0


# DuckDB's working files use native container storage, like the Jenkins volume.
# Docker Desktop bind mounts are used only for inputs and completed artifacts.
(WORK / 'native-build.gradle').write_text("gradle.beforeProject { p -> p.buildDir = new File('/tmp/datenportal-build/' + p.projectDir.name) }\n")

def docker(arguments, name, success=True):
    if '-p' in arguments:
        arguments = arguments + ['-I', '/test/native-build.gradle']
    command = ['docker', 'run', '--rm', '--network', 'none', '--user', 'jenkins',
               '-v', str(WORK) + ':/test', '-v', str(PILOT) + ':/pilot:ro',
               '--entrypoint', '/bin/bash', IMAGE, '-c',
               'set -euo pipefail; /usr/local/bin/configure-duckdb-extensions.sh; '
               'git config --global --add safe.directory /test/repo; set +e; "$@"; result=$?; set -e; '
               'if [ -d /tmp/datenportal-build ]; then '
               'for source in /tmp/datenportal-build/*; do '
               'name=$(basename "$source"); target=/test/repo/$name/build; '
               'if [ "$name" = repo ]; then target=/test/repo/build; fi; '
               'rm -rf "$target"; mkdir -p "$target"; cp -a "$source/." "$target/"; done; fi; exit "$result"', 'bash'] + arguments
    log = WORK / (name + '.log')
    with log.open('w') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    if (result.returncode == 0) != success:
        raise AssertionError(str(log) + '\n' + '\n'.join(log.read_text().splitlines()[-35:]))
    return log.read_text()


def delivery(name, data=None, metadata=None, issue=None, write=False, success=True, extra=()):
    global sequence
    sequence += 1
    args = ['/test/repo/shared/bin/gradlew-java17.sh', '--offline', '--no-daemon',
            '-I', '/test/repo/shared/gradle/init.gradle', '-p', '/test/repo/statistikdienst',
            'publishToDatenportal', '-Pdataset=' + DATASET, '-PpublicationManifestUrl=file:///test/accepted/current.json']
    if data:
        args += ['-PdataFile=' + data]
    if metadata:
        args += ['-PmetadataFile=/test/' + metadata]
    if issue is not None:
        args += ['-PseriesId=' + issue]
    print(f'{sequence:02d} {name}', flush=True)
    log = docker(args + list(extra), f'{sequence:02d}-{name}', success)
    if not success:
        return log
    if success:
        report = json.loads((OUTPUT / 'report.json').read_text())
        assert report['mode'] == 'preview', report
        assert (OUTPUT / 'datasheets.xtf').is_file()
        assert (OUTPUT / 'metadata' / SHEET.name).is_file()
        shutil.copytree(OUTPUT, WORK / f'{sequence:02d}-{name}-outputs')
        if write:
            promote(OUTPUT)
            shutil.copy(OUTPUT / 'metadata' / SHEET.name, SHEET)
        return report


def local(element):
    return element.tag.rsplit('}', 1)[-1]


def child(element, name):
    return next((c for c in element if local(c) == name), None)


def text(element, name):
    value = child(element, name)
    return None if value is None else value.text


def resources(source=CATALOG):
    return {text(e, 'identifier'): e for e in ET.parse(source).iter()
            if local(e) in ('Dataset', 'DatasetSeries', 'DatasetIssue')}


def technical(resource):
    result = {key: text(resource, key) for key in ('issued', 'modified')}
    result['counts'] = [e.text for e in resource.iter() if local(e) in ('objectCount', 'attributeCount')]
    result['downloads'] = [e.text for e in resource.iter() if local(e) == 'downloadURL']
    return result


def metadata(name, edit=lambda tree: None):
    tree = ET.parse(SHEET)
    edit(tree)
    tree.write(WORK / name, encoding='UTF-8', xml_declaration=True)
    return name


def set_dates(tree):
    for e in tree.iter():
        if local(e) in ('issued', 'modified'):
            e.text = '1900-01-01'


def issue_count():
    return sum(local(e) == 'DatasetIssue' for e in ET.parse(SHEET).iter())


def promote(output):
    manifest = json.loads((output / 'current.json').read_text())
    for f in (output.parent / 'release').glob('*.xtf'):
        shutil.copy(f, STATE / f.name)
    shutil.copy(output / 'current.json', STATE / 'current.json')
    if manifest['catalog']:
        shutil.copy(STATE / manifest['catalog'], CATALOG)


print('Integration artifacts:', WORK, flush=True)
bootstrap = ['/test/repo/shared/bin/gradlew-java17.sh', '--offline', '--no-daemon',
    '-I', '/test/repo/shared/gradle/init.gradle', '-p', '/test/repo', 'initializePublication',
    '-PpublicationManifestUrl=file:///test/accepted/current.json']
docker(bootstrap, 'bootstrap')
promote(REPO / 'build/publication/outputs')
assert json.loads((STATE / 'current.json').read_text())['catalog'] is None
docker(bootstrap, 'bootstrap-existing-rejected', success=False)
(WORK / 'roundtrip.gradle').write_text('''
gradle.projectsEvaluated {
    def p=gradle.rootProject
    def type=p.buildscript.classLoader.loadClass('ch.so.agi.gretl.tasks.Ili2duckdbExport')
    def task=p.tasks.register('exportOfficesRoundtrip',type) {
        dependsOn 'preparePublication'
        databaseFile new File(p.buildDir,'publication/publication.duckdb')
        schema 'offices'
        modelNames 'SO_AGI_DataCatalog_Base_20260529'
        modelDirectories System.getenv('DATENPORTAL_MODELS_DIR')
        dataFiles '/test/offices-roundtrip.xtf'
    }
    p.tasks.named('commitAndPushMetadata') { dependsOn task }
}
''')
metadata('METADATA_FILE')
delivery('metadata-bootstrap', metadata='METADATA_FILE', issue='ignored')
assert not CATALOG.exists() and not (OUTPUT / 'published-catalog.xtf').exists()
assert not list(OUTPUT.glob('*.parquet'))
assert not (REPO / ".git").exists()

shutil.copy(PILOT / DATASET / 'so_bevo_altersstruktur_2025.csv', WORK / 'DATA_FILE')
delivery('known-data', data='/test/DATA_FILE', issue='2025', write=True, extra=['-I', '/test/roundtrip.gradle'])
def offices(path):
    return sorted(tuple(sorted((local(c), c.text) for c in e)) for e in ET.parse(path).iter() if local(e) == 'Office.Office')
assert offices(WORK / 'offices-roundtrip.xtf') == offices(REPO / 'shared/data/offices.xtf')
initial_resources = resources()
known_id = DATASET + '_2025'
known_technical = technical(initial_resources[known_id])
assert known_technical['issued'] and known_technical['counts'] == ['106', '6']
# Binary exports must contain the same actual values as the input, not merely have valid headers.
docker(['/opt/java/openjdk17/bin/java', '-cp', '/opt/datenportal/offline-bundle/jars/*',
        '/test/VerifyExports.java'], 'readback')
metadata('changed-dates.xtf', set_dates)
delivery('metadata-retains-technical', metadata='changed-dates.xtf', issue='ignored', write=True)
assert technical(resources()[known_id]) == known_technical
def semantic_xtf(path):
    # Namespace prefixes, sender and whitespace belong to the exporter. IDs and
    # ordered model content must survive an unchanged metadata roundtrip.
    def node(e):
        value = e.text or ''
        if len(e) and not value.strip():
            value = ''  # indentation between model elements, not leaf text
        return (e.tag, tuple(sorted(e.attrib.items())), value, tuple(node(c) for c in e))
    return node(next(e for e in ET.parse(path).iter() if local(e)=='datasection'))

stable = semantic_xtf(CATALOG)
delivery('stable-metadata-roundtrip', metadata='changed-dates.xtf', write=True)
assert semantic_xtf(CATALOG) == stable

original_issue_count = issue_count()
lines = (PILOT / DATASET / 'so_bevo_altersstruktur_2025.csv').read_text().splitlines()
(WORK / 'small.csv').write_text('\n'.join(lines[:4]) + '\n')
delivery('unknown-issue', data='/test/small.csv', issue='2030', write=True)
unknown = next(e for e in resources().values() if text(e, 'issueLabel') == '2030')
provisional = text(unknown, 'identifier')
assert text(unknown, 'publicationStatus') == 'in_review'
assert text(unknown, 'isCurrentIssue') == 'false'
assert issue_count() == original_issue_count
assert technical(resources()[known_id]) == known_technical
issued = text(unknown, 'issued')
(WORK / 'small.csv').write_text('\n'.join(lines[:6]) + '\n')
delivery('unknown-issue-replacement', data='/test/small.csv', issue='2030', write=True)
assert technical(resources()[provisional])['counts'] == ['5', '6']
assert text(resources()[provisional], 'issued') == issued


def identify_issue(tree):
    series = next(e for e in tree.iter() if local(e) == 'DatasetSeries')
    known = next(e for e in series.iter() if local(e) == 'DatasetIssue')
    child(known, 'isCurrentIssue').text = 'false'
    wrapper = ET.SubElement(series, '{' + NS + '}issues')
    new = copy.deepcopy(known)
    child(new, 'identifier').text = DATASET + '_2030'
    child(new, 'issueLabel').text = '2030'
    child(new, 'isCurrentIssue').text = 'true'
    wrapper.append(new)

metadata('identified.xtf', identify_issue)
delivery('assign-and-release-unknown', metadata='identified.xtf', write=True)
assert provisional not in resources()
identified = resources()[DATASET + '_2030']
assert text(identified, 'publicationStatus') == 'published'
assert text(identified, 'issued') == issued
assert technical(identified)['counts'] == ['5', '6']
assert technical(resources()[known_id]) == known_technical


def remove_known(tree):
    series = next(e for e in tree.iter() if local(e) == 'DatasetSeries')
    for wrapper in list(series):
        if local(wrapper) == 'issues':
            for issue in list(wrapper):
                if text(issue, 'issueLabel') == '2025':
                    wrapper.remove(issue)
            if not len(wrapper):
                series.remove(wrapper)

metadata('removed.xtf', remove_known)
delivery('removed-issue-retained', metadata='removed.xtf', write=True)
assert text(resources()[known_id], 'publicationStatus') == 'in_review'
assert technical(resources()[known_id]) == known_technical
assert issue_count() == original_issue_count

# Combined delivery, free edition text and publication withdrawal.
metadata('combined.xtf')
delivery('combined-delivery', data=CSV, metadata='combined.xtf', issue='2030', write=True)
assert technical(resources()[DATASET + '_2030'])['counts'] == ['106', '6']
delivery('free-edition-text', data='/test/small.csv', issue="2031 / Spezial's", write=True)
from urllib.parse import unquote, urlsplit
unlisted = next(e for e in resources().values() if text(e, 'issueLabel') == "2031 / Spezial's")
for url in technical(unlisted)['downloads']:
    filename = unquote(urlsplit(url).path.rsplit('/', 1)[-1])
    assert '/' not in filename and (OUTPUT / filename).is_file(), url

def withdraw(tree):
    series = next(e for e in tree.iter() if local(e) == 'DatasetSeries')
    child(series, 'publicationStatus').text = 'draft'
metadata('withdrawn.xtf', withdraw)
delivery('withdrawn-series', metadata='withdrawn.xtf', write=True)
assert all(text(e, 'publicationStatus') != 'published' for e in resources().values())

# A standalone topic must not require an edition either through Gradle.
standalone = 'ch.so.agi.av_nachfuehrungsstatistik.personal'
standalone_csv = next((PILOT / standalone).glob('*.csv'))
args = ['/test/repo/shared/bin/gradlew-java17.sh', '--offline', '--no-daemon',
        '-I', '/test/repo/shared/gradle/init.gradle', '-p', '/test/repo/agi',
        'publishToDatenportal', '-Pdataset=' + standalone, '-PpublicationManifestUrl=file:///test/accepted/current.json',
        '-PdataFile=/pilot/' + standalone + '/' + standalone_csv.name]
print('Standalone data delivery', flush=True)
docker(args, 'standalone-data')
standalone_output = REPO / 'agi/build/publication/outputs/published-catalog.xtf'
assert standalone in resources(standalone_output)
assert technical(resources(standalone_output)[standalone])['issued']
assert not (REPO / '.git').exists()

# Input rejection and preview isolation: no invalid delivery can advance the shared baseline.
baseline = (STATE / 'current.json').read_bytes()
delivery('no-upload-rejected', success=False)
delivery('blank-issue-rejected', data=CSV, issue='   ', success=False)
(WORK / 'invalid.csv').write_text('Jahrgang;Auslaender;Auslaenderinnen;Schweizer;Schweizerinnen;Total\nwrong;1;1;1;1;4\n')
delivery('invalid-csv-rejected', data='/test/invalid.csv', issue='2030', success=False)
(WORK / 'invalid.xtf').write_text('<broken')
delivery('invalid-metadata-rejected', metadata='invalid.xtf', success=False)
def wrong_identifier(tree):
    series = next(e for e in tree.iter() if local(e) == 'DatasetSeries')
    child(series, 'identifier').text = 'ch.so.wrong.topic'
metadata('wrong-identifier.xtf', wrong_identifier)
assert 'must match the selected topic' in delivery('wrong-identifier-rejected',
        metadata='wrong-identifier.xtf', success=False)

def duplicate_label(tree):
    series = next(e for e in tree.iter() if local(e) == 'DatasetSeries')
    original = next(e for e in series.iter() if local(e) == 'DatasetIssue')
    additional = copy.deepcopy(original)
    child(additional, 'identifier').text += '_different_identifier'
    wrapper = ET.SubElement(series, '{' + NS + '}issues')
    wrapper.append(additional)
metadata('duplicate-label.xtf', duplicate_label)
assert 'duplicate' in delivery('duplicate-label-rejected', metadata='duplicate-label.xtf', success=False).lower()

def missing_model(tree):
    series = next(e for e in tree.iter() if local(e) == 'DatasetSeries')
    ET.SubElement(series, '{' + NS + '}model').text = 'Missing_Delivery_Test_Model'
metadata('missing-model.xtf', missing_model)
assert 'model not found' in delivery('missing-model-rejected', metadata='missing-model.xtf',
        data=CSV, issue='2030', success=False)
valid_catalog = CATALOG.read_bytes()
active_catalog = STATE / json.loads((STATE / 'current.json').read_text())['catalog']
active_catalog.write_text('<broken')
delivery('invalid-existing-catalog-rejected', data=CSV, issue='2030', success=False)
active_catalog.write_bytes(valid_catalog)
assert (STATE / 'current.json').read_bytes() == baseline
assert not (REPO / '.git').exists()

# Repository-only mode uses exactly the selected metadata and preserves the accepted technical state.
before = {k: technical(v) for k, v in resources().items()}
delivery('repository-metadata', extra=['-PpublicationMode=repository-metadata'], write=True)
assert {k: technical(v) for k, v in resources().items()} == before
delivery('repository-rejects-upload', metadata='combined.xtf', extra=['-PpublicationMode=repository-metadata'], success=False)
# A newly added series must be inserted without changing the existing topics.
previous_resources = {k: technical(v) for k, v in resources().items()}
old_dataset = DATASET
new_series = SHEET.read_text().replace(old_dataset, 'ch.so.test.newseries')
DATASET = 'ch.so.test.newseries'
RELATIVE = Path('statistikdienst') / DATASET / ('meta-' + DATASET + '.xtf')
SHEET = REPO / RELATIVE
SHEET.parent.mkdir()
SHEET.write_text(new_series)
delivery('new-series-repository-metadata', extra=['-PpublicationMode=repository-metadata'], write=True)
assert DATASET not in resources()  # Metadata alone does not fabricate technical deliveries.
assert {k: technical(resources()[k]) for k in previous_resources} == previous_resources
collection = STATE / json.loads((STATE / 'current.json').read_text())['datasheets']
assert any(text(e, 'identifier') == DATASET for e in ET.parse(collection).iter())
delivery('new-series-first-csv', data=CSV, issue='2030', write=True)
assert DATASET + '_2030' in resources()
assert {k: technical(resources()[k]) for k in previous_resources} == previous_resources

# Malformed manifests and missing referenced XTF cannot silently reset the state.
manifest_file = STATE / 'current.json'
valid_manifest = manifest_file.read_bytes()
manifest_file.write_text('{broken')
delivery('broken-manifest', extra=['-PpublicationMode=repository-metadata'], success=False)
manifest_file.write_bytes(valid_manifest)
manifest = json.loads(valid_manifest)
referenced = STATE / manifest['datasheets']
backup = referenced.read_bytes()
referenced.unlink()
delivery('missing-referenced-sheets', extra=['-PpublicationMode=repository-metadata'], success=False)
referenced.write_bytes(backup)

# Explicit administrative migration accepts the previous catalog; missing sources fail.
migration_args = bootstrap + ['-PpublicationManifestUrl=file:///test/migration/current.json',
                             '-PinitialCatalog=/test/accepted/catalog.xtf']
docker(migration_args, 'bootstrap-migration')
migrated = REPO / 'build/publication/outputs'
assert json.loads((migrated / 'current.json').read_text())['catalog'] is not None
assert {k: technical(v) for k, v in resources(migrated / 'published-catalog.xtf').items()} == {k: technical(v) for k, v in resources().items()}
docker(bootstrap + ['-PpublicationManifestUrl=file:///test/migration/current.json',
                   '-PinitialCatalog=/test/missing.xtf'], 'bootstrap-missing-source', success=False)
# Schema-aware conversion: preserve text identifiers and enforce declared scalar types.
BASE_NS = 'http://www.interlis.ch/xtf/2.4/SO_AGI_DataCatalog_Base_20260529'
def typed_attributes(tree, datatype='Integer'):
    series = next(e for e in tree.iter() if local(e)=='DatasetSeries')
    for resource in tree.iter():
        if local(resource) in ('DatasetSeries','DatasetIssue'):
            for element in list(resource):
                if local(element) in ('attributes','model'):
                    resource.remove(element)
    for name, kind in [('code','Text'),('count',datatype),('value','Decimal'),('active','Boolean'),('day','Date'),('moment','DateTime')]:
        wrapper = ET.SubElement(series, '{'+NS+'}attributes')
        attr = ET.SubElement(wrapper, '{'+BASE_NS+'}DatasetAttribute')
        for key, value in [('name',name),('dataType',kind),('mandatory','true')]:
            ET.SubElement(attr, '{'+BASE_NS+'}'+key).text = value
metadata('typed.xtf', typed_attributes)
typed_csv = 'code,count,value,active,day,moment\n0012,4,1.25,true,2026-01-02,2026-01-02T12:34:56\n'
(WORK/'typed.csv').write_text(typed_csv)
delivery('typed-exports',data='/test/typed.csv',metadata='typed.xtf',issue='2050')
docker(['/opt/java/openjdk17/bin/java','-cp','/opt/datenportal/offline-bundle/jars/*',
        '/test/VerifyExports.java', '/test/repo/statistikdienst/build/publication/outputs/'+DATASET+'_2050.', 'typed'], 'typed-export-readback')
for label, content, diagnostic in [
        ('wrong-columns',typed_csv.replace('code,count','count,code'), 'CSV columns do not match'),
        ('duplicate-columns',typed_csv.replace('code,count','code,CODE'), 'unique column names'),
        ('blank-column',typed_csv.replace('code,count',',count'), 'unique column names'),
        ('mandatory-empty',typed_csv.replace('0012,4',',4'), 'Mandatory CSV column'),
        ('invalid-integer',typed_csv.replace('0012,4','0012,four'), 'Conversion Error')]:
    (WORK/'invalid-typed.csv').write_text(content)
    assert diagnostic.lower() in delivery(label,data='/test/invalid-typed.csv',metadata='typed.xtf',issue='2050',success=False).lower()
metadata('unsupported-type.xtf',lambda t: typed_attributes(t, 'Unsupported'))
assert 'Unsupported declared CSV datatype' in delivery('unsupported-type',data='/test/typed.csv',metadata='unsupported-type.xtf',issue='2050',success=False)
# Preparing only must remain side-effect-free even when write/reload switches are set.
docker(['/test/repo/shared/bin/gradlew-java17.sh','--offline','--no-daemon','-I','/test/repo/shared/gradle/init.gradle',
        '-p','/test/repo/statistikdienst','preparePublication','-Pdataset='+DATASET,
        '-PpublicationMode=repository-metadata','-PpublicationManifestUrl=file:///test/accepted/current.json',
        '-PgitWriteBack=true','-PreloadPortal=true'], 'preparation-only')
assert json.loads((OUTPUT/'report.json').read_text())['publication']=='not-published'
print('PASS: offline bootstrap, delivery sequences, input rejection and export readback', flush=True)
print('Artifacts:', WORK, flush=True)
