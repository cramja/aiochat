import logging
from dataclasses import dataclass


LOG = logging.Logger(__name__)


class Column:
    def __init__(self, name = None):
        self.name = name


class Meta(type):

    def __new__(cls, name, bases, dct):
        clz = super().__new__(cls, name, bases, dct)
        cols = []
        for k,v in dct.items():
            if k.startswith('_') or not (isinstance(v, Column) or v == Column):
                continue
            cols.append(k)
        def init(self, *args, **kwargs):
            for k,v in kwargs.items():
                if k in cols:
                    setattr(self, k, v)
        clz.__init__ = init
        return clz


class Table(metaclass=Meta):
    pass


class IntentData(Table):
    id = Column
    create_time = Column
    client_id = Column
    value = Column


async def migrate(pgpool):
    current_version = _MIGRATIONS[-1][0]
    async with pgpool.acquire() as conn:
        db_version = await init_migrator(conn)
        while db_version != current_version:
            async with conn.transaction():
                await conn.execute('LOCK schema_version IN ACCESS EXCLUSIVE MODE')
                db_version = await conn.fetchval('SELECT max(version) FROM schema_version')
                if db_version is None:
                    db_version = -1
                for version, name, fn in _MIGRATIONS:
                    if version == db_version + 1:
                        LOG.info(f'migrating to version {version}:{name}')
                        await fn(conn)
                        await conn.execute('INSERT INTO schema_version (version, name) VALUES ($1, $2)', version, name)


async def init_migrator(conn):
    async with conn.transaction():
        table_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT FROM pg_catalog.pg_class c
                JOIN   pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE  n.nspname = 'public'
                AND    c.relname = 'schema_version'
                AND    c.relkind = 'r'
        );
        ''')
        if not table_exists:
            LOG.info('creating schema_version table')
            await conn.execute('''
            CREATE TABLE schema_version (
                version     INTEGER PRIMARY KEY,
                name        VARCHAR NOT NULL,
                create_time TIMESTAMP NOT NULL DEFAULT now()
            );
            ''')
        

async def init_tables(conn):
    await conn.execute('''
    CREATE TABLE messages (
        id              SERIAL PRIMARY KEY,
        create_time     TIMESTAMP NOT NULL DEFAULT now(),
        client_id       VARCHAR NOT NULL,
        value           VARCHAR NOT NULL
    );
    CREATE INDEX messages_create_time_idx ON messages(create_time);
    ''')


async def add_intent_data_table(conn):
    await conn.execute('''
    CREATE TABLE intent_data(
        id              SERIAL PRIMARY KEY,
        create_time     TIMESTAMP NOT NULL DEFAULT now(),
        intent          VARCHAR NOT NULL,
        value           VARCHAR NOT NULL
    );
    ''')


_MIGRATIONS = [
    (0, 'init', init_tables),
    (1, 'add intent data table', add_intent_data_table),
]
