import pathlib
import json
import logging
import sys
import os
from uuid import uuid4 as uuid

from aiohttp import web
import asyncpg
import uvloop

from chat import init_app
from db import migrate

logging.basicConfig(level=logging.DEBUG)

async def get_index(request):
    return web.Response(status=301, headers={'location': '/app/index.html'})


async def create_pgengine(app):
    config = app['config']
    app['pgpool'] = await asyncpg.create_pool(
        user=config['db_user'],
        database=config['db_name'],
        host=config['db_host'],
        port=config['db_port'],
        password=config['db_password']
    )
    await migrate(app['pgpool'])

async def dispose_pgengine(app):
    app['pg_engine'].close()
    await app['pg_engine'].wait_closed()


def setup_db(app):
    app.on_startup.append(create_pgengine)
    app.on_cleanup.append(dispose_pgengine)


def setup_routes(app):
    app.router.add_get('/', get_index)
    init_app(app)

    app.router.add_static('/app', str(pathlib.Path(__file__).parent.parent) + "/app", show_index=False)


def setup_config(app):
    cfg = {}
    config = os.environ.get('AIO_CONFIG')
    if config:
        with open(config, 'r') as f:
            cfg = json.load(f)
    for key in os.environ.keys():
        k = key.lower()
        if k.startswith('aio_') and k != 'aio_config':
            config[k[4:]] = os.environ.get(key)
    app['config'] = cfg


app = web.Application()
setup_config(app)
setup_routes(app)
setup_db(app)


if __name__ == '__main__':
    uvloop.install()
    web.run_app(app, host='127.0.0.1', port=8000)
