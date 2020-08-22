import os
import json
import pytest
import asyncio
import logging
from pytest import fixture

import asyncpg

from server.db.orm import Table, Column,Meta


LOG = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio


class TData(metaclass=Meta):
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
    await conn.execute('DROP TABLE IF EXISTS t_data')
    await conn.execute('CREATE TABLE t_data (id SERIAL PRIMARY KEY, data VARCHAR)')

    saved = await TData.create(conn, data='hello') 
    first = (await TData.all(conn))[0]
    assert saved.data == 'hello'
    assert first.data == 'hello'
    assert saved.id == first.id

    await conn.execute('DROP TABLE t_data')
