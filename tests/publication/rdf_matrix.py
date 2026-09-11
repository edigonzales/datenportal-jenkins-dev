"""Exportgrenzen mit einem tatsächlich erzeugten Katalog im Offline-Image prüfen."""
import copy
import json
import shutil
import xml.etree.ElementTree as ET
from rdf_checks import P, check_export


def run_matrix(work, docker, catalog):
    directory = work / 'rdf-matrix'
    directory.mkdir()
    original = ET.parse(catalog)
    series = next(original.iter(P+'DatasetSeries'))
    issue = next(original.iter(P+'DatasetIssue'))
    root = original.getroot()
    catalog_node = next(root.iter(P+'Catalog'))
    for name in ('datasets', 'datasetSeries'):
        for element in catalog_node.findall(P+name):
            catalog_node.remove(element)
    datasets = ET.SubElement(catalog_node, P+'datasets')
    series_container = ET.SubElement(catalog_node, P+'datasetSeries')

    def resource(base, identifier, status, standalone=False):
        clone = copy.deepcopy(base)
        clone.find(P+'identifier').text = identifier
        clone.find(P+'resourceUri').text = 'https://example.test/dataset/'+identifier
        clone.find(P+'publicationStatus').text = status
        for index, distribution in enumerate(clone.findall(P+'distributions/'+P+'Distribution')):
            distribution.find(P+'distributionUri').text = 'https://example.test/distribution/'+identifier+'/'+str(index)
        if standalone:
            clone.tag = P+'Dataset'
            for name in ('issueLabel', 'isCurrentIssue'):
                field = clone.find(P+name)
                if field is not None:
                    clone.remove(field)
        return clone

    statuses = ('draft', 'in_review', 'published', 'archived')
    for status in statuses:
        datasets.append(resource(issue, 'ch.so.single.'+status, status, standalone=True))
    for parent_status in statuses:
        for issue_status in statuses:
            name = 'ch.so.series.'+parent_status+'.'+issue_status
            parent = resource(series, name, parent_status)
            issues = parent.find(P+'issues')
            issues.clear()
            issues.append(resource(issue, name+'_2025', issue_status))
            # Auch mehrere freigegebene Ausgaben müssen als eigene Datensätze erscheinen.
            issues.append(resource(issue, name+'_2026', issue_status))
            series_container.append(parent)
    visible = next(e for e in datasets if e.findtext(P+'publicationStatus') == 'published')
    visible.find(P+'title').text = 'Titel mit Ä, &, < und "'
    visible.find(P+'description').text = 'Eigene Beschreibung\nmit Sonderzeichen: < & >'
    # «other» wird nicht aus der Dateiendung geraten; bestehende Links bleiben gleich.
    other = copy.deepcopy(visible.find(P+'distributions/'+P+'Distribution'))
    other.find(P+'format').text = 'other'
    other.find(P+'distributionUri').text += '/other'
    visible.find(P+'distributions').append(other)
    original.write(directory/'matrix.xml', encoding='UTF-8', xml_declaration=True)
    # Entgegengesetzte Eingangsreihenfolge darf die RDF-Reihenfolge nicht ändern.
    datasets[:] = list(reversed(list(datasets)))
    series_container[:] = list(reversed(list(series_container)))
    for element in root.iter(P+'distributions'):
        element[:] = list(reversed(list(element)))
    original.write(directory/'reordered.xml', encoding='UTF-8', xml_declaration=True)
    for element in root.iter(P+'publicationStatus'):
        element.text = 'archived'
    original.write(directory/'hidden.xml', encoding='UTF-8', xml_declaration=True)
    (directory/'settings.gradle').write_text("rootProject.name='rdf-matrix'\n")
    (directory/'build.gradle').write_text('''
plugins { id 'ch.so.agi.gretl' }
import ch.so.agi.gretl.tasks.XslTransformer
def source = findProperty('source') ?: 'matrix'
tasks.register('transform', XslTransformer) {
    xmlFiles file(source+'.xml')
    xslFile file('../repo/shared/xsl/opendata/catalog.xsl')
    outDirectory file('generated'); fileExtension 'rdf'
}
tasks.register('checkRdf', XslTransformer) {
    dependsOn 'transform'
    xmlFiles file('generated/'+source+'.rdf')
    xslFile file('../repo/shared/xsl/opendata/validate.xsl')
    outDirectory file('validation'); fileExtension 'json'
}
''')
    command = ['/test/repo/shared/bin/gradlew-java17.sh', '--offline', '--no-daemon',
               '-I', '/test/repo/shared/gradle/init.gradle', '-p', '/test/rdf-matrix', 'checkRdf']
    for name, count in [('matrix', 3), ('reordered', 3), ('hidden', 0)]:
        docker(command+['-Psource='+name], 'rdf-'+name)
        shutil.copy(directory/'generated'/f'{name}.rdf', directory/'opendata.rdf')
        shutil.copy(directory/f'{name}.xml', directory/'published-catalog.xtf')
        assert check_export(directory) == count
        assert json.loads((directory/'validation'/f'{name}.json').read_text())['datasetCount'] == count
    assert (directory/'generated/matrix.rdf').read_bytes() == (directory/'generated/reordered.rdf').read_bytes()

    def invalid(name, edit, message):
        tree = ET.parse(directory/'matrix.xml')
        dataset = next(e for e in tree.iter(P+'Dataset') if e.findtext(P+'publicationStatus') == 'published')
        edit(tree, dataset)
        tree.write(directory/f'{name}.xml', encoding='UTF-8', xml_declaration=True)
        log = docker(command+['-Psource='+name], 'rdf-'+name, success=False)
        assert message in log, log[-2000:]

    invalid('bad-id', lambda t, d: setattr(d.find(P+'identifier'), 'text', 'ch.so.unerlaubt:kennung'), 'Unzulässige Exportkennung')
    def collision(tree, dataset):
        clone = copy.deepcopy(dataset)
        clone.find(P+'identifier').text = dataset.findtext(P+'identifier').replace('.', '-')
        clone.find(P+'resourceUri').text += '/different'
        next(tree.iter(P+'datasets')).append(clone)
    invalid('collision', collision, 'Doppelte Exportkennung')
    invalid('missing-issued', lambda t, d: d.remove(d.find(P+'issued')), 'Datumswerte issued und modified')
    invalid('invalid-date', lambda t, d: setattr(d.find(P+'modified'), 'text', '2026-02-30'), 'Datumswerte issued und modified')
    invalid('missing-title', lambda t, d: setattr(d.find(P+'title'), 'text', '   '), 'Titel, Beschreibung')
    invalid('missing-distributions', lambda t, d: d.remove(d.find(P+'distributions')), 'Kontakt, Ersteller oder Distribution')
    invalid('missing-contact', lambda t, d: d.remove(d.find(P+'contactPoint')), 'RDF-Export:')
    (directory/'wrong-model.xml').write_text('<anderesModell/>')
    assert 'Erwartet wird ein PublishedCatalog' in docker(command+['-Psource=wrong-model'], 'rdf-wrong-model', success=False)
    print('RDF: Statusmatrix, Graphen, Formate, stabile Sortierung und Fehlerfälle bestanden.', flush=True)
