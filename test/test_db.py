import asyncio
import datetime
import json
import logging
import os
import pytest
from pytest import fixture

import asyncpg

from server.db.orm import Table, Column,Meta


LOG = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio


class TData(metaclass=Meta):
    id          = Column(primary_key=True)
    created     = Column(name='create_time')
    updated     = Column(name='update_time')
    data        = Column


@fixture
def config():
    config_file = os.getenv('AIO_CONFIG', None)
    with open(config_file, 'r') as fp:
        return json.load(fp)


@fixture
async def conn(config):
    conn = await asyncpg.connect(**config['db'])
    await conn.execute('DROP TABLE IF EXISTS t_data')
    await conn.execute('''CREATE TABLE t_data (id SERIAL PRIMARY KEY, 
                            create_time TIMESTAMP DEFAULT now(), 
                            update_time TIMESTAMP DEFAULT now(), 
                            data VARCHAR)
                        ''')

    yield conn

    await conn.execute('DROP TABLE t_data')
    await asyncio.wait_for(conn.close(), timeout=1.0)
    

async def test_create_records(conn):
    saved = await TData.create(conn, data='hello') 
    first = (await TData.all(conn))[0]
    assert saved.data == 'hello'
    assert first.data == 'hello'
    assert saved.id == first.id
    assert type(saved.created) == datetime.datetime


async def test_update_records(conn):
    saved = await TData.create(conn, data='hello') 
    now = datetime.datetime.now()
    updated = await saved.update(conn, data='goodbye', updated=now)
    assert updated.data == 'goodbye'
    assert updated.updated == now
