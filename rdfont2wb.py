#!/usr/bin/env python
'''
Converts the OKH RDF Ontology into items and properties in a WikiBase instance.
It reads input from an RDF(/Turtle) file,
and writes appropriate items and properties into a WikiBase instance
through its API (api.php).
'''

import os
import rdflib
from rdflib.namespace import DC, DCTERMS, DOAP, FOAF, SKOS, OWL, RDF, RDFS, VOID, XMLNS, XSD
import click
from wikibase import WBSession, API_URL_OHO, enable_debug

OBO = rdflib.Namespace('http://purl.obolibrary.org/obo/')
SCHEMA = rdflib.Namespace('http://schema.org/')

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option()
def version_token():
    '''
    Stub to set context settings and version info.
    '''
    #pass

RDF_FILE_LOCAL = '../OSHI/osh-metadata.ttl'
RDF_FILE_REMOTE = 'https://raw.githubusercontent.com/OPEN-NEXT/LOSH/master/osh-metadata.ttl'
RDF_FILE = RDF_FILE_LOCAL if os.path.exists(RDF_FILE_LOCAL) else RDF_FILE_REMOTE
BASE_URI = 'http://purl.org/oseg/ontologies/osh-metadata/0.1/base'
RDF_TO_WB_LINK_FILE = 'tmp_ont2wb_links.ttl'


def get_label_preds():
    return [RDFS.label or SKOS.prefLabel or DCTERMS.title or DC.title]

def get_desc_preds():
    return [RDFS.comment or SKOS.definition or DCTERMS.description or DC.description]

def get_non_claim_preds():
    return get_label_preds() + get_desc_preds() + [RDF.type,
            #RDFS.range, RDFS.domain,
            OWL.cardinality, OWL.maxCardinality, OWL.minCardinality]
            #RDFS.subPropertyOf, RDFS.subClassOf]

class RdfOntology2WikiBaseConverter:

    def __init__(self, ttl_source, wbs, link_graph_file):
        self.graph = rdflib.Graph()
        self.graph.load(ttl_source, format='turtle')
        self.wbs = wbs
        self.link_graph_file = link_graph_file
        self.ont2wb = rdflib.Graph()
        self.default_language = 'en'
        self.label_sep = '\n\n'
        self.description_sep = '\n\n'

    def create_ont_wb_thing(self, subj) -> str:
        data = {
                'aliases': {},
                'datatype': 'string' # XXX unused later on!
                }

        lbs = {}
        for lb_prop in get_label_preds():
            for lb in self.graph.objects(subj, lb_prop):
                lng = lb.language if lb.language is not None else self.default_language
                lbs[lng] = ((lbs[lng] + self.label_sep) if lng in lbs else '') + lb.value
        data['labels'] = lbs

        dscs = {}
        for dc_prop in get_desc_preds():
            for dc in self.graph.objects(subj, dc_prop):
                lng = dc.language if dc.language is not None else self.default_language
                dscs[lng] = ((dscs[lng] + self.description_sep) if lng in dscs else '') + dc.value
        data['description'] = dscs

        types = list(self.graph.objects(subj, RDF.type))
        if OWL.Class in types:
            item = True
        elif (OWL.ObjectProperty in types) or (OWL.DatatypeProperty in types):
            item = False
        elif OWL.Ontology in types:
            return None
        else:
            print('RDF subject has unknown type: %s' % subj)
            for typ in types:
                print('\t%s' % typ)
            exit(1)

        #return "XXX"
        return self.wbs.create_wb_thing(item=item, labels=lbs, descriptions=dscs, claims={})

    def skip_subj(self, subj):
        return str(subj) == BASE_URI # It is the owl:Ontology instance

    def rdf2wb_id(self, rdf_ref, fail_if_missing=True):
        wb_ids = self.ont2wb.objects(rdf_ref, SCHEMA.identifier)
        if wb_ids is not None:
            wb_ids = list(wb_ids)
            if len(wb_ids) == 1:
                return str(wb_ids[0])
        if fail_if_missing:
            raise RuntimeError(
                    'We do not have a (single)  WikiBase ID for RDF reference %s'
                    % rdf_ref)
        return None

    def create_claim(self, wb_id, subj, pred, obj):
        if pred in get_non_claim_preds():
            return
        claims = {}
        pred_wb_id = self.rdf2wb_id(pred)
        if isinstance(obj, rdflib.Literal):
            main_value = str(obj)
        else:
            obj_id = self.rdf2wb_id(obj)
            obj_id_num = int(obj_id[1:])
            main_value = {
                'entity-type': 'item',
                'id': obj_id,
                'numeric-id': obj_id_num
                }
        #main_type = 'string' if isinstance(obj, rdflib.Literal) else 'wikibase-item'
        main_data_type = 'string' if isinstance(obj, rdflib.Literal) else 'wikibase-item'
        main_type = 'string' if isinstance(obj, rdflib.Literal) else 'wikibase-entityid'
        main_snak_type = 'value'
        '''
commonsMedia
entity-schema
external-id
globe-coordinate
geo-shape
wikibase-item
monolingualtext
time
wikibase-property
quantity
string
tabular-data
url
        '''
        claims[pred_wb_id] = [{
            #'id': '', # TODO
            'mainsnak': {
                'snaktype': main_snak_type,
                'property': pred_wb_id,
                'datatype': main_data_type,
                'datavalue': {
                    'value': main_value,
                    'type': main_type
                    }
                },
            'type': 'statement',
            'rank': 'normal',
            }]
        print('- Adding on %s claim %s ...' % (wb_id, str(claims)))
        self.wbs.add_wb_thing_claims(wb_id, claims)

    def convert(self):
        self.ont2wb = rdflib.Graph()
        if os.path.exists(self.link_graph_file):
            self.ont2wb.load(self.link_graph_file, format='turtle')
        else:
            self.ont2wb.add((RDFS.subClassOf, SCHEMA.identifier, rdflib.Literal('P279'))) # https://www.wikidata.org/wiki/Property:P279
            self.ont2wb.add((RDFS.subPropertyOf, SCHEMA.identifier, rdflib.Literal('P1647'))) # https://www.wikidata.org/wiki/Property:P1647
            #self.ont2wb.add((SCHEMA.domain, SCHEMA.identifier, '')) #
            #self.ont2wb.add((SCHEMA.range, SCHEMA.identifier, '')) # -> datatype
            self.ont2wb.add((SCHEMA.inLanguage, SCHEMA.identifier, rdflib.Literal('P305'))) # https://www.wikidata.org/wiki/Property:P305
            self.ont2wb.add((SCHEMA.version, SCHEMA.identifier, rdflib.Literal('P348'))) # https://www.wikidata.org/wiki/Property:P348
            self.ont2wb.add((SCHEMA.isBasedOn, SCHEMA.identifier, rdflib.Literal('P144'))) # https://www.wikidata.org/wiki/Property:P144
            self.ont2wb.add((SCHEMA.copyrightHolder, SCHEMA.identifier, rdflib.Literal('P3931'))) # https://www.wikidata.org/wiki/Property:P3931
            self.ont2wb.add((SCHEMA.licenseDeclared, SCHEMA.identifier, rdflib.Literal('P2479'))) # https://www.wikidata.org/wiki/Property:P2479
            self.ont2wb.add((SCHEMA.creativeWorkStatus, SCHEMA.identifier, rdflib.Literal('P548'))) # https://www.wikidata.org/wiki/Property:P548 - aka version type
            self.ont2wb.add((SCHEMA.image, SCHEMA.identifier, rdflib.Literal('P4765'))) # https://www.wikidata.org/wiki/Property:P4765 - aka Commons compatible image available at URL
            self.ont2wb.add((SCHEMA.hasPart, SCHEMA.identifier, rdflib.Literal('P527'))) # https://www.wikidata.org/wiki/Property:P527 - has part
            #self.ont2wb.add((SCHEMA.hasPart, SCHEMA.identifier, rdflib.Literal('P2670'))) # https://www.wikidata.org/wiki/Property:P2670 - has parts of the class
            self.ont2wb.add((SCHEMA.codeRepository, SCHEMA.identifier, rdflib.Literal('P1324'))) # https://www.wikidata.org/wiki/Property:P1324 - source code repository
            self.ont2wb.add((SCHEMA.value, SCHEMA.identifier, rdflib.Literal('P8203'))) # https://www.wikidata.org/wiki/Property:P8203 -  aka supported Metadata
            self.ont2wb.add((OBO.BFO_0000016, SCHEMA.identifier, rdflib.Literal('P7535'))) # function -> https://www.wikidata.org/wiki/Property:P7535 - aka scope and content
            self.ont2wb.add((SCHEMA.amount, SCHEMA.identifier, rdflib.Literal('P1114'))) # https://www.wikidata.org/wiki/Property:P1114 -  aka quantity
            self.ont2wb.add((SCHEMA.URL, SCHEMA.identifier, rdflib.Literal('P2699'))) # https://www.wikidata.org/wiki/Property:P2699 -  aka URL

        # create the items and properties
        for subj in self.graph.subjects():
            if self.skip_subj(subj):
                continue
            wb_ids = list(self.ont2wb.objects(subj, SCHEMA.identifier))
            wb_id = wb_ids[0] if len(wb_ids) > 0 else None
            if wb_id is None:
                print('- Creating WB part for subject "%s" ...' % subj)
                wb_id = self.create_ont_wb_thing(subj)
                self.ont2wb.add((subj, SCHEMA.identifier, rdflib.Literal(wb_id)))
            #else: # XXX We might want to recreate it here, anyway!
            print('- Subject "%s" is represented by "%s"' % (subj, wb_id))

        self.ont2wb.serialize(self.link_graph_file, format='turtle')

        # Create the connections/predicates/claims
        for subj in self.graph.subjects():
            if self.skip_subj(subj):
                continue
            wb_ids = list(self.ont2wb.objects(subj, SCHEMA.identifier))
            wb_id = wb_ids[0]
            for _, pred, obj in self.graph.triples((subj, None, None)):
                if pred == RDFS.range:
                    print('XXX range')
                elif pred == RDFS.domain:
                    print('XXX domain')
                else:
                    self.create_claim(wb_id, subj, pred, obj)

@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('user', envvar='USER')
@click.argument('passwd', envvar='PASSWD')
@click.version_option("0.1.0")
def cli(user, passwd):
    # Run as a CLI script
    #enable_debug()
    wbs = WBSession(API_URL_OHO)
    #wbs.bot_login(bot_user, bot_passwd)
    wbs.login(user, passwd)

    converter = RdfOntology2WikiBaseConverter(RDF_FILE, wbs, RDF_TO_WB_LINK_FILE)
    converter.convert()

if __name__ == "__main__":
    cli()
