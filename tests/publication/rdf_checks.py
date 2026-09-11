"""Unabhängige Graphprüfung des RDF/XML; keine Wiederverwendung der XSL-Prüflogik."""
from pathlib import Path
import xml.etree.ElementTree as ET

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCAT, DCTERMS as DCT, FOAF, XSD

P = '{http://www.interlis.ch/xtf/2.4/SO_AGI_DataCatalog_PublishedCatalog_20260602}'
B = '{http://www.interlis.ch/xtf/2.4/SO_AGI_DataCatalog_Base_20260529}'
VCARD = Namespace('http://www.w3.org/2006/vcard/ns#')
SCHEMA = Namespace('http://schema.org/')
PUBLISHER = URIRef('https://so.ch/')
LICENSE = URIRef('http://dcat-ap.ch/vocabulary/licenses/terms_open')
LANGUAGE = URIRef('http://publications.europa.eu/resource/authority/language/DEU')


def check_export(output):
    output = Path(output)
    source = output / 'published-catalog.xtf'
    expected = []
    if source.exists():
        tree = ET.parse(source)
        expected.extend(e for e in tree.iter(P+'Dataset') if e.findtext(P+'publicationStatus') == 'published')
        for series in tree.iter(P+'DatasetSeries'):
            if series.findtext(P+'publicationStatus') == 'published':
                expected.extend(e for e in series.findall(P+'issues/'+P+'DatasetIssue')
                                if e.findtext(P+'publicationStatus') == 'published')
    graph = Graph().parse(output / 'opendata.rdf', format='xml')
    catalogs = list(graph.subjects(RDF.type, DCAT.Catalog))
    assert catalogs == [URIRef('https://data.so.ch/catalog/opendata')], catalogs
    subjects = {URIRef(e.findtext(P+'resourceUri')) for e in expected}
    assert set(graph.subjects(RDF.type, DCAT.Dataset)) == subjects
    assert set(graph.objects(catalogs[0], DCAT.dataset)) == subjects
    assert (PUBLISHER, FOAF.name, Literal('Kanton Solothurn', lang='de')) in graph
    assert (catalogs[0], DCT.publisher, PUBLISHER) in graph
    assert not list(graph.subjects(RDF.type, URIRef(str(DCAT)+'DatasetSeries')))
    for element in expected:
        subject = URIRef(element.findtext(P+'resourceUri'))
        assert graph.value(subject, DCT.identifier) == Literal(element.findtext(P+'identifier').replace('.', '-')+'@kanton_solothurn')
        for prop, tag in [(DCT.title, 'title'), (DCT.description, 'description')]:
            assert graph.value(subject, prop) == Literal(element.findtext(P+tag), lang='de')
        assert graph.value(subject, DCT.publisher) == PUBLISHER
        assert graph.value(subject, DCT.language) == LANGUAGE
        creator = element.find(P+'creator/'+P+'Office')
        assert graph.value(subject, DCT.creator) == URIRef(creator.findtext(P+'officeUri'))
        contact = graph.value(subject, DCAT.contactPoint)
        assert graph.value(contact, VCARD.hasEmail) == URIRef(element.findtext(P+'contactPoint/'+B+'ContactPoint/'+B+'email'))
        assert set(graph.objects(subject, DCAT.theme)) == {URIRef(e.text) for e in element.findall(P+'themes/'+P+'ThemeAssignment/'+P+'themeUri')}
        assert set(graph.objects(subject, DCAT.keyword)) == {Literal(e.text, lang='de') for e in element.findall(P+'keywords') if (e.text or '').strip()}
        distributions = element.findall(P+'distributions/'+P+'Distribution')
        assert set(graph.objects(subject, DCAT.distribution)) == {URIRef(e.findtext(P+'distributionUri')) for e in distributions}
        for distribution in distributions:
            node = URIRef(distribution.findtext(P+'distributionUri'))
            assert (node, RDF.type, DCAT.Distribution) in graph
            assert graph.value(node, DCT.license) == LICENSE
            assert graph.value(node, DCAT.accessURL) == URIRef(distribution.findtext(P+'accessURL'))
            assert graph.value(node, DCAT.downloadURL) == URIRef(distribution.findtext(P+'downloadURL'))
            media = {'csv':'text/csv', 'xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'parquet':'application/vnd.apache.parquet'}
            kind = distribution.findtext(P+'format')
            assert graph.value(node, DCAT.mediaType) == (URIRef('https://www.iana.org/assignments/media-types/'+media[kind]) if kind in media else None)
            assert graph.value(node, DCT.format) == (URIRef('http://publications.europa.eu/resource/authority/file-type/'+kind.upper()) if kind in media else None)
            for predicate, tag in [(DCT.issued, 'issued'), (DCT.modified, 'modified')]:
                date = Literal(element.findtext(P+tag), datatype=XSD.date)
                assert graph.value(subject, predicate) == date
                assert graph.value(node, predicate) == date
        temporal = element.find(P+'temporalCoverage/'+B+'TemporalCoverage')
        if temporal is not None:
            node = graph.value(subject, DCT.temporal)
            for predicate, tag in [(SCHEMA.startDate, 'startDate'), (SCHEMA.endDate, 'endDate')]:
                value = temporal.findtext(B+'referenceDate') or temporal.findtext(B+tag)
                assert graph.value(node, predicate) == (Literal(value, datatype=XSD.date) if value else None)
    return len(subjects)
