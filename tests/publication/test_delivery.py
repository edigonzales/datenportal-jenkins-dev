#!/usr/bin/env python3
"""Real GRETL/ili2duckdb integration, offline; all Git writes target a disposable bare repo."""
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
# Tests intentionally exercise bootstrap, independent of any catalog in the source snapshot.
CATALOG = REPO / 'shared/data/published-catalog.xtf'
CATALOG.unlink(missing_ok=True)
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


def docker(arguments, name, success=True):
    command = ['docker', 'run', '--rm', '--network', 'none', '--user', 'jenkins',
               '-v', str(WORK) + ':/test', '-v', str(PILOT) + ':/pilot:ro',
               '--entrypoint', '/bin/bash', IMAGE, '-c',
               'set -euo pipefail; /usr/local/bin/configure-duckdb-extensions.sh; '
               'git config --global --add safe.directory /test/repo; exec "$@"', 'bash'] + arguments
    log = WORK / (name + '.log')
    with log.open('w') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    if (result.returncode == 0) != success:
        raise AssertionError(str(log) + '\n' + '\n'.join(log.read_text().splitlines()[-35:]))
    return log.read_text()


def git(*args):
    return docker(['git', '-C', '/test/repo'] + list(args), 'git').strip()


def revision():
    return git('ls-remote', 'origin', 'refs/heads/main').split()[0]


def delivery(name, data=None, metadata=None, issue=None, write=False, success=True, extra=()):
    global sequence
    sequence += 1
    args = ['/test/repo/shared/bin/gradlew-java17.sh', '--offline', '--no-daemon',
            '-I', '/test/repo/shared/gradle/init.gradle', '-p', '/test/repo/statistikdienst',
            'publishToDatenportal', '-Pdataset=' + DATASET]
    if data:
        args += ['-PdataFile=' + data]
    if metadata:
        args += ['-PmetadataFile=/test/' + metadata]
    if issue is not None:
        args += ['-PseriesId=' + issue]
    if write:
        args += ['-PtopicRepositoryMode=managed-git', '-PgitWriteBack=true',
                 '-PtopicRepositoryUrl=file:///test/accepted.git', '-PtopicRepositoryBranch=main',
                 '-PgitBaseRevision=' + git('rev-parse', 'HEAD'),
                 '-PgitCommitterName=Delivery Test', '-PgitCommitterEmail=test@example.invalid']
    print(f'{sequence:02d} {name}', flush=True)
    log = docker(args + list(extra), f'{sequence:02d}-{name}', success)
    if not success:
        return log
    if success:
        report = json.loads((OUTPUT / 'report.json').read_text())
        assert report['mode'] == ('accepted' if write else 'preview'), report
        assert (OUTPUT / 'datasheets.xtf').is_file()
        assert (OUTPUT / 'metadata' / SHEET.name).is_file()
        shutil.copytree(OUTPUT, WORK / f'{sequence:02d}-{name}-outputs')
        if write:
            assert report['resultRevision'] == revision()
            assert not git('status', '--porcelain')
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


print('Integration artifacts:', WORK, flush=True)
docker(['bash', '-c', '''set -e
 git init -b main /test/repo
 git -C /test/repo config user.name 'Fixture Setup'
 git -C /test/repo config user.email fixture@example.invalid
 git -C /test/repo add --all
 git -C /test/repo commit -m 'initial fixture snapshot'
 git clone --bare /test/repo /test/accepted.git
 git -C /test/repo remote add origin file:///test/accepted.git
'''], 'initialize')
initial_revision = revision()
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
assert revision() == initial_revision

shutil.copy(PILOT / DATASET / 'so_bevo_altersstruktur_2025.csv', WORK / 'DATA_FILE')
delivery('known-data', data='/test/DATA_FILE', issue='2025', write=True, extra=['-I', '/test/roundtrip.gradle'])
def offices(path):
    return sorted(tuple(sorted((local(c), c.text) for c in e)) for e in ET.parse(path).iter() if local(e) == 'Office.Office')
assert offices(WORK / 'offices-roundtrip.xtf') == offices(REPO / 'shared/data/offices.xtf')
initial_resources = resources()
known_id = DATASET + '_2025'
known_technical = technical(initial_resources[known_id])
assert known_technical['issued'] and known_technical['counts'] == ['106', '6']
assert set(git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines()) == {
    str(RELATIVE), 'shared/data/published-catalog.xtf'}
# Binary exports must contain the same actual values as the input, not merely have valid headers.
docker(['/opt/java/openjdk17/bin/java', '-cp', '/opt/datenportal/offline-bundle/jars/*',
        '/test/VerifyExports.java'], 'readback')
metadata('changed-dates.xtf', set_dates)
delivery('metadata-retains-technical', metadata='changed-dates.xtf', issue='ignored', write=True)
assert technical(resources()[known_id]) == known_technical
stable = CATALOG.read_bytes()
delivery('stable-metadata-roundtrip', metadata='changed-dates.xtf', write=True)
assert CATALOG.read_bytes() == stable

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
        'publishToDatenportal', '-Pdataset=' + standalone,
        '-PdataFile=/pilot/' + standalone + '/' + standalone_csv.name]
print('Standalone data delivery', flush=True)
docker(args, 'standalone-data')
standalone_output = REPO / 'agi/build/publication/outputs/published-catalog.xtf'
assert standalone in resources(standalone_output)
assert technical(resources(standalone_output)[standalone])['issued']
assert not git('status', '--porcelain')

# Input rejection and preview isolation: no invalid delivery can advance the shared baseline.
baseline = revision()
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
assert 'Duplicate issue labels' in delivery('duplicate-label-rejected', metadata='duplicate-label.xtf', success=False)

def missing_model(tree):
    series = next(e for e in tree.iter() if local(e) == 'DatasetSeries')
    ET.SubElement(series, '{' + NS + '}model').text = 'Missing_Delivery_Test_Model'
metadata('missing-model.xtf', missing_model)
assert 'model not found' in delivery('missing-model-rejected', metadata='missing-model.xtf',
        data=CSV, issue='2030', success=False)
valid_catalog = CATALOG.read_bytes()
CATALOG.write_text('<broken')
delivery('invalid-existing-catalog-rejected', data=CSV, issue='2030', success=False)
CATALOG.write_bytes(valid_catalog)
assert revision() == baseline
assert not git('status', '--porcelain')

# A real competing commit advances the remote after preparation and before the Git gate.
docker(['git', 'clone', '/test/accepted.git', '/test/competitor'], 'competing-checkout')
(WORK / 'race.gradle').write_text("""
gradle.projectsEvaluated {
    gradle.rootProject.tasks.named('preparePublication') {
        doLast {
            project.exec { commandLine 'git','-C','/test/competitor','-c','user.name=Other',
                '-c','user.email=other@example.invalid','commit','--allow-empty','-m','concurrent manual change' }
            project.exec { commandLine 'git','-C','/test/competitor','push','origin','main' }
        }
    }
}
""")
delivery('concurrent-commit-rejected', data=CSV, issue='2030', write=True, success=False,
         extra=['-I', '/test/race.gradle'])
assert revision() != baseline
assert git('rev-parse', 'HEAD') == baseline
assert not git('status', '--porcelain')
# This reset is exclusively in the test-created checkout, to begin the next isolated scenario.
git('fetch', 'origin')
git('reset', '--hard', 'origin/main')
baseline = revision()

# A rejected push may leave a commit in its isolated checkout, never in the shared source.
hook = WORK / 'accepted.git/hooks/pre-receive'
hook.write_text('#!/bin/sh\nexit 1\n')
hook.chmod(0o755)
delivery('push-rejected', data='/test/small.csv', issue='2030', write=True, success=False)
assert revision() == baseline
hook.unlink()
assert git('rev-parse', 'HEAD') != baseline
print('PASS: isolated delivery sequences and rejection tests', flush=True)
print('Artifacts:', WORK, flush=True)
