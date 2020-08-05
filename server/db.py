import logging

LOG = logging.Logger(__name__)



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


_MIGRATIONS = [
    (0, 'init', init_tables)
]