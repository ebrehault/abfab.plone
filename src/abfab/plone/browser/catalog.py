from souper.interfaces import ICatalogFactory
from souper.soup import NodeAttributeIndexer
from zope.interface import implementer
from repoze.catalog.catalog import Catalog
from repoze.catalog.indexes.field import CatalogFieldIndex
from repoze.catalog.indexes.path import CatalogPathIndex

@implementer(ICatalogFactory)
class CatalogFactory(object):

    def __call__(self, context=None):
        catalog = Catalog()
        path_indexer = NodeAttributeIndexer('path')
        catalog[u'path'] = CatalogPathIndex(path_indexer)
        type_indexer = NodeAttributeIndexer('type')
        catalog[u'type'] = CatalogFieldIndex(type_indexer)
        return catalog