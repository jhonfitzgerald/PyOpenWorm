from __future__ import print_function
from rdflib.term import URIRef
from six.moves.urllib.parse import quote
from six import string_types
import hashlib
import logging
from yarom.graphObject import IdentifierMissingException


__all__ = ['IdMixin']
# Dictionary of previously created mixins
_IdMixins = dict()

L = logging.getLogger(__name__)


def IdMixin(typ=object, hashfunc=None):
    """
    Mixin that provides common identifier logic

    Parameters
    ----------
    typ : type
        The type of object to use as the hash function's super class. Defaults
        to 'object'
    hashfunc : function
        The function to use for encoding data provided to make_identifier.
        Should return an object can ``.encode()`` to a :py:class:`bytes` (a.k.a.
        :py:class:`str` in Python 2).  Defaults to :py:func:`hashlib.sha224`
    """
    res = _IdMixins.get((id(typ), hashfunc), None)
    if res is None:
        class _IdMixin(typ):
            hashfun = hashfunc if hashfunc is not None else hashlib.sha224

            def __init__(self, ident=None, key=None, *args, **kwargs):
                super(_IdMixin, self).__init__(*args, **kwargs)
                if key is not None and ident is not None:
                    raise Exception("Only one of 'key' or 'ident' can be given to Context")

                if ident is not None:
                    self._id = URIRef(ident)
                else:
                    # Randomly generate an identifier if the derived class can't
                    # come up with one from the start. Ensures we always have something
                    # that functions as an identifier
                    self._id = None

                self._key = None
                if key is not None:
                    self.set_key(key)

            @classmethod
            def make_identifier(cls, data):
                '''
                Makes an identifier based on this class' namespace by calling
                __str__ on the data and passing to the class' hashfunc.

                If the __str__ for data's type doesn't function as an
                identifier, you should use either
                :meth:`make_identifier_direct` or override
                :meth:`identifier_augment` and :meth:`defined_augment`
                '''
                strdata = str(data)
                if strdata:
                    hsh = "a" + cls.hashfun(strdata.encode()).hexdigest()
                    return URIRef(cls.rdf_namespace[hsh])
                else:
                    raise ValueError('Cannot use falsy value'
                                     ' {} to make an identifier'.format(strdata))

            @classmethod
            def make_identifier_direct(cls, string):
                if not isinstance(string, string_types):
                    raise ValueError('make_identifier_direct only accepts strings')
                return URIRef(cls.rdf_namespace[quote(string)])

            @property
            def key(self):
                return self._key

            @key.setter
            def key(self, key):
                self.set_key(key)

            def set_key(self, key):
                '''
                Sets the identifier for this object based on the given key

                Equivalent to self.key = key
                '''
                if isinstance(key, string_types):
                    self._id = self.make_identifier_direct(key)
                else:
                    self._id = self.make_identifier(key)
                self._key = str(key)

            @property
            def identifier(self):
                if self._id is not None:
                    return self._id
                elif self.defined_augment():
                    return self.identifier_augment()
                else:
                    raise IdentifierMissingException(self)

            def identifier_augment(self):
                """ Override this method to define an identifier in lieu of one explicity set.

                One must also override :meth:`defined_augment` to return True whenever
                this method could return a valid identifier.
                :exc:`~yarom.graphObject.IdentifierMissingException` should be
                raised if an identifier cannot be generated by this method.

                Raises
                ------

                IdentifierMissingException

                """
                raise IdentifierMissingException(self)

            @property
            def defined(self):
                if self._id is not None:
                    return True
                else:
                    return self.defined_augment()

            def defined_augment(self):
                """ This fuction must return False if :meth:`identifier_augment` would
                raise an :exc:`~yarom.graphObject.IdentifierMissingException`. Override
                it when defining a non-standard identifier for subclasses of DataObjects.
                """
                return False

        _IdMixins[(id(typ), hashfunc)] = _IdMixin
        res = _IdMixin
    return res
