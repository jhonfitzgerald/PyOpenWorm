from six.moves.urllib.parse import urlparse, unquote, urlencode
from six.moves.urllib.request import Request, urlopen
from six.moves.urllib.error import HTTPError, URLError
import re
import logging
from yarom.graphObject import IdentifierMissingException

from .dataObject import DataObject
from PyOpenWorm import bibtex as BIB

logger = logging.getLogger(__file__)


class WormbaseRetrievalException(Exception):
    pass


class PubmedRetrievalException(Exception):
    pass


# A little bit about why this a separate type from Document:
#
# This type corresponds to a document which has some statements that we care
# about. The key reason this is distinct from Document is that a document need
# not provide evidence of anything. For example, the `WormData.n4` file
# generated by insert_worm.py is a document, but it doesn't provide any
# scientific or logical justification for any of the statements made within it.
class Document(DataObject):

    """
    A representation of some document.

    Possible keys include::

        pmid, pubmed: a pubmed id or url (e.g., 24098140)
        wbid, wormbase: a wormbase id or url (e.g., WBPaper00044287)
        doi: a Digitial Object id or url (e.g., s00454-010-9273-0)


    Attributes
    ----------
    doi : DatatypeProperty
        A Digital Object Identifier (DOI), optional
    pmid : DatatypeProperty
        A PubMed ID (PMID) that points to a paper, optional
    wormbaseid : DatatypeProperty
        An ID from WormBase that points to a record, optional
    author : DatatypeProperty
        The author of the document
    title : DatatypeProperty
        The title of the document
    year : DatatypeProperty
        The date (e.g., publication date) of the evidence
    uri : DatatypeProperty
        A URL that points to evidence
    """
    # class_context = 'http://openworm.org/schema'
    # rdf_namespace = Namespace("http://openworm.org/entities/")

    def __init__(
            self,
            author=None,
            uri=None,
            year=None,
            date=None,
            title=None,
            doi=None,
            wbid=None,
            wormbaseid=None,
            wormbase=None,
            bibtex=None,
            pmid=None,
            pubmed=None,
            **kwargs):
        """
        Parameters
        ----------
        bibtex : string
            A string containing a single BibTeX entry. Parsed during initialization, but not saved thereafter. optional
        doi : string
            A Digital Object Identifier (DOI). optional
        pmid : string
            A PubMed ID (PMID) that points to a paper. optional
        pubmed : string
            A PubMed ID (PMID) or URL that points to a paper. Ignored if 'pmid' is provided. optional
        wbid : string
            An ID from WormBase that points to a record. optional
        wormbaseid : string
            An ID or URL from WormBase that points to a record. Ignored if 'wbid' is provided. optional
        author : string
            The author of the document. optional
        title : string
            The title of the document. optional
        year : string or int
            The date (e.g., publication date) of the document. optional
        uri : string
            A URL that points to document. optional
        """
        super(Document, self).__init__(**kwargs)
        self._fields = dict()

        multivalued_fields = ('author', 'uri')
        other_fields = ('year', 'title', 'doi', 'wbid', 'pmid')
        self.id_precedence = ('doi', 'pmid', 'wbid', 'uri')
        for x in multivalued_fields:
            Document.DatatypeProperty(x, multiple=True, owner=self)

        for x in other_fields:
            Document.DatatypeProperty(x, owner=self)

        if bibtex is not None:
            self.update_with_bibtex(bibtex)

        if pmid is not None:
            self.pmid.set(pmid)
        elif pubmed is not None:
            if pubmed[:4] == 'http':
                # Probably a uri, right?
                _tmp = _pubmed_uri_to_pmid(pubmed)
                if _tmp is None:
                    raise ValueError("Couldn't convert Pubmed URL to a PubMed ID")
                pmid = _tmp
            else:
                pmid = pubmed
            self.pmid.set(pmid)

        if wormbase is not None:
            if wormbase[:4] == 'http':
                _tmp = _wormbase_uri_to_wbid(wormbase)
                if _tmp is None:
                    raise ValueError("Couldn't convert Wormbase URL to a Wormbase ID")
                wbid = _tmp
            else:
                wbid = wormbase
        elif wormbaseid is not None:
            wbid = wormbaseid

        if wbid is not None:
            self.wbid.set(wbid)

        if doi is not None:
            if doi[:4] == 'http':
                _tmp = _doi_uri_to_doi(doi)
                if _tmp is not None:
                    doi = _tmp
            self.doi.set(doi)

        if year is not None:
            self.year(year)
        elif date is not None:
            self.year(date)

        if title is not None:
            self.title(title)

        if author is not None:
            self.author(author)

        if uri is not None:
            self.uri(uri)

    def update_with_bibtex(self, bibtex):
        bib_db = BIB.loads(bibtex)
        if len(bib_db.entries) > 1:
            raise ValueError('The given BibTex string has %d entries.'
                             ' Cannot determine which entry to use for the document' % len(bib_db))
        BIB.update_document_with_bibtex(self, bib_db.entries[0])

    def defined_augment(self):
        for x in self.id_precedence:
            if getattr(self, x).has_defined_value():
                return True
        return False

    def identifier_augment(self):
        for idKind in self.id_precedence:
            idprop = getattr(self, idKind)
            if idprop.has_defined_value():
                s = str(idKind) + ":" + idprop.defined_values[0].identifier.n3()
                return self.make_identifier(s)
        raise IdentifierMissingException(self)

    # TODO: Provide a way to override modification of already set values.
    def update_from_wormbase(self, replace_existing=False):
        """ Queries wormbase for additional data to fill in the Document.

        If replace_existing is set to `True`, then existing values will be cleared.
        """

        # XXX: wormbase's REST API is pretty sparse in terms of data provided.
        #     Would be better off using AQL or the perl interface
        # _Very_ few of these have these fields filled in
        wbid = self.wbid.defined_values
        if len(wbid) == 1:
            wbid = wbid[0].identifier.toPython()

            # get the author
            try:
                j = _json_request('http://api.wormbase.org/rest/field/paper/' + str(wbid) + '/overview')
                print(j)
                if 'overview' in j:
                    f = j['overview']
                    if 'authors' in f:
                        dat = f['authors']['data']
                        if dat is not None:
                            if replace_existing and self.author.has_defined_value:
                                self.author.clear()
                            for x in dat:
                                self.author.set(x['label'])

                    for fname in ('pmid', 'year', 'title', 'doi'):
                        if fname in f and f[fname]['data'] is not None:
                            attr = getattr(self, fname)
                            if replace_existing and attr.has_defined_value:
                                attr.clear()
                            attr.set(f[fname]['data'])
            except Exception:
                logger.warning("Couldn't retrieve Wormbase data", exc_info=True)
        elif len(wbid) == 0:
            raise WormbaseRetrievalException("There is no Wormbase ID attached to this Document."
                                             " So no data can be retrieved")
        else:
            raise WormbaseRetrievalException("There is more than one Wormbase ID attached to this Document."
                                             " Please try with just one Wormbase ID")

    def _crossref_doi_extract(self):
        # Extract data from crossref
        def crRequest(doi):
            data = {'q': doi}
            data_encoded = urlencode(data)
            return _json_request(
                'http://search.labs.crossref.org/dois?%s' %
                data_encoded)

        doi = self._fields['doi']
        if doi[:4] == 'http':
            doi = _doi_uri_to_doi(doi)
        try:
            r = crRequest(doi)
        except Exception:
            logger.warning("Couldn't retrieve Crossref info", exc_info=True)
            return
        # XXX: I don't think coins is meant to be used, but it has structured
        # data...
        if len(r) > 0:
            extra_data = r[0]['coins'].split('&amp;')
            fields = (x.split("=") for x in extra_data)
            fields = [[y.replace('+', ' ').strip() for y in x] for x in fields]
            authors = [x[1] for x in fields if x[0] == 'rft.au']
            for a in authors:
                self.author(a)
            # no error for bad ids, just an empty list
            if len(r) > 0:
                # Crossref can process multiple doi's at one go and return the
                # metadata. we just need the first one
                r = r[0]
                if 'title' in r:
                    self.title(r['title'])
                if 'year' in r:
                    self.year(r['year'])

    def update_from_pubmed(self):
        def pmRequest(pmid):
            import xml.etree.ElementTree as ET  # Python 2.5 and up
            url = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=' + str(pmid)
            s = _url_request(url)
            if hasattr(s, 'charset'):
                parser = ET.XMLParser(encoding=s.charset)
            else:
                parser = None

            return ET.parse(s, parser)

        pmid = self.pmid.defined_values
        if len(pmid) == 1:
            pmid = pmid[0].identifier.toPython()

            try:
                tree = pmRequest(pmid)
            except Exception:
                logger.warning("Couldn't retrieve Pubmed info", exc_info=True)
                return
            for x in tree.findall('./DocSum/Item[@Name="AuthorList"]/Item'):
                self.author(x.text)

            for x in tree.findall('./DocSum/Item[@Name="Title"]'):
                self.title(x.text)

            for x in tree.findall('./DocSum/Item[@Name="DOI"]'):
                self.doi(x.text)

            for x in tree.findall('./DocSum/Item[@Name="PubDate"]'):
                self.year(x.text)

        elif len(pmid) == 0:
            raise PubmedRetrievalException('No Pubmed ID is attached to this document. Cannot retrieve Pubmed data')
        else:
            raise PubmedRetrievalException('More than one Pubmed ID is attached to this document.'
                                           ' Please try with just one Pubmed ID')


def _wormbase_uri_to_wbid(uri):
    return str(urlparse(uri).path.split("/")[2])


def _pubmed_uri_to_pmid(uri):
    return str(urlparse(uri).path.split("/")[2])


def _doi_uri_to_doi(uri):
    # DOI URL to DOI translation is complicated. This is a cop-out.
    parsed = urlparse(uri)
    if 'doi.org' in parsed.netloc:
        doi = parsed.path.split("/", 1)[1]
    else:
        doi = None

    return doi


def _url_request(url, headers={}):
    try:
        r = Request(url, headers=headers)
        s = urlopen(r, timeout=1)
        info = dict(s.info())
        content_type = {k.lower(): info[k] for k in info}['content-type']
        md = re.search("charset *= *([^ ]+)", content_type)
        if md:
            s.charset = md.group(1)

        return s
    except HTTPError:
        return ""
    except URLError:
        return ""


def _json_request(url):
    import json
    headers = {'Content-Type': 'application/json'}
    try:
        data = _url_request(url, headers).read().decode('UTF-8')
        if hasattr(data, 'charset'):
            return json.loads(data, encoding=data.charset)
        else:
            return json.loads(data)
    except BaseException:
        logger.warning("Couldn't retrieve JSON data from " + url,
                       exc_info=True)
        return {}


__yarom_mapped_classes__ = (Document,)
