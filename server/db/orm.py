"""
Mini asycnpg ORM

### Examples

class Entity(Table):
    id      = Column(primary_key=True)
    data    = Column
    created = Column(name='create_time')

    find_by_create_time_gt = Query('SELECT * FROM entity WHERE create_time > ?', Arg('create_time'))

pg  # asyncpg connection

## creates
rec = Entity(data='abc')
with pg.transaction():
    await rec.create(pg)
# rec now has the id, create_time populated by the create statement

## updates
with pg.transaction():
    await rec.update(pg, data='bar')
# rec now has data = bar

## query
records = await Entity.find_by_create_time_gt(pg, create_time=datetime.now())

# uses create_time value from current record
records = await rec.find_by_create_time_gt(pg)

"""

import asyncpg
import logging

LOG = logging.getLogger(__name__)

def to_snake(str): 
    return ''.join(['_'+i.lower() if i.isupper()  
               else i for i in str]).lstrip('_') 


class Column:
    def __init__(self, name=None, primary_key=False, **kwargs):
        self.primary_key = primary_key
        self.name = name
        self.attr = name if not 'attr' in kwargs else kwargs['attr']


class TableMeta:
    def __init__(self, name, cols):
        self.name = name
        self.cols = cols
        self.col_map = {c.attr: c for c in self.cols}
        self.name_attr = {c.name: c.attr for c in self.cols}
        pkl = list(filter(lambda col: col.primary_key, cols))
        self.pk = pkl[0] if pkl else None


def table_init(table_meta):
    def init(self, *args, **kwargs):
        unused_attr = list(table_meta.name_attr.values())
        for k, v in kwargs.items():
            attr = table_meta.name_attr.get(k)
            if attr:
                setattr(self, attr, v)
                unused_attr.remove(attr)
        for k in unused_attr:
            setattr(self, k, None)
    return init


def table_create(table_meta):
    async def create(cls, pg: asyncpg.Connection, timeout=None, **kwargs):
        given_cols = [given_key for given_key in kwargs.keys() if given_key in table_meta.col_map]
        stmt = f'INSERT INTO {table_meta.name} ({",".join(given_cols)}) VALUES ($1{",".join(["${{i}}" for i in range(2, len(given_cols))])}) RETURNING *'
        LOG.debug('statement: %s', stmt)
        res = await pg.fetchrow(stmt, *[kwargs[k] for k in given_cols], timeout=timeout)
        return cls(**res)
    return create


def table_update(table_meta):
    async def update(self, pg: asyncpg.Connection, timeout=None, **kwargs):
        set_sql = []
        var_list = []
        for k,v in kwargs.items():
            if k in table_meta.col_map:
                col = table_meta.col_map.get(k)
                set_sql.append(f'{col.name}=${len(var_list) + 1}')
                var_list.append(v)

        stmt = f'UPDATE {table_meta.name} SET {", ".join(set_sql)} WHERE {table_meta.pk.name}={getattr(self, table_meta.pk.attr)} RETURNING *'
        LOG.debug('statement: %s', stmt)
        res = await pg.fetchrow(stmt, *var_list, timeout=timeout)
        self.__init__(**res)  # why not?
        return self
    return update


def table_all(table_meta):
    async def t_all(clz, pg: asyncpg.Connection):
        return [clz(**r) for r in await pg.fetch(f'SELECT * FROM {table_meta.name}')]
    return t_all


def table_repr(table_meta):
    def trepr(self):
        rv = [table_meta.name, "("]
        LOG.debug(table_meta.col_map)
        for k,v in table_meta.col_map.items():
            rv.append(k)
            rv.append("=")
            rv.append(repr(getattr(self, k)))
            rv.append(", ")
        rv.pop(len(rv)-1)
        rv.append(")")
        return "".join(rv)
    return trepr

    class Meta(type):

        def __new__(cls, name, bases, dct):
            clz = super().__new__(cls, name, bases, dct)

            cols = []
            for k, v in dct.items():
                if k.startswith('_') or not (isinstance(v, Column) or v == Column):
                    continue
                if not isinstance(v, Column):
                    v = v(name=k, attr=k)
                if not v.name:
                    v.name = k
                v.attr = k
                cols.append(v)
            
            # TODO: class name
            table_meta = TableMeta(to_snake(name), cols)
            clz.table_meta = table_meta
        
            clz.__init__        = table_init(table_meta)
            clz.create          = classmethod(table_create(table_meta))
            clz.update          = table_update(table_meta)
            clz.all             = classmethod(table_all(table_meta))
            clz.__repr__        = table_repr(table_meta)

            return clz


class Table(metaclass=Meta):
    pass
