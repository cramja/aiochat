import os
import json
import pytest
import asyncio
from pytest import fixture

import asyncpg

from server.db import Table, Column

pytestmark = pytest.mark.asyncio


class TData(Table):
    id = Column
    data = Column


@fixture
def config():
    config_file = os.getenv('AIO_CONFIG', None)
    with open(config_file, 'r') as fp:
        return json.load(fp)


@fixture
async def conn(config):
    conn = await asyncpg.connect(**config['db'])
    yield conn
    await asyncio.wait_for(conn.close(), timeout=1.0)
    

async def test_query_records(conn):
    await conn.execute('DROP TABLE IF EXISTS test_data')
    await conn.execute('CREATE TABLE test_data (id SERIAL PRIMARY KEY, data VARCHAR)')
    await conn.execute('INSERT INTO test_data (data) VALUES ($1)', 'hello')
    records = await conn.fetch('SELECT * FROM test_data')
    for record in records:
        td = TData(**record)
        assert td.data == 'hello'
    await conn.execute('DROP TABLE test_data')
