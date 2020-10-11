import pathlib
import json
import logging
import sys
import os
from uuid import uuid4 as uuid

from aiohttp import web
import asyncpg
import uvloop

from bots import HistoryBot
from bots import TranslatorBot
from bots import SystemBot
from bots import EchoBot
from chat import init_app
from db.migration import migrate
from dispatch import Dispatcher

logging.basicConfig(level=logging.DEBUG)

async def get_index(request):
    return web.Response(status=301, headers={'location': '/app/index.html'})


async def create_pgengine(app):
    config = app['config']
    app['pgpool'] = await asyncpg.create_pool(**config['db'])
    await migrate(app['pgpool'])


async def dispose_pgengine(app):
    app['pg_engine'].close()
    await app['pg_engine'].wait_closed()


def setup_db(app):
    app.on_startup.append(create_pgengine)
    app.on_cleanup.append(dispose_pgengine)

def setup_bots(app):
    async def create_history_bot(app):
        dispatcher = app['dispatcher']
        bot = HistoryBot(app['pgpool'])
        bot.init(dispatcher)

    async def create_translator_bot(app):
        dispatcher = app['dispatcher']
        bot = TranslatorBot()
        bot.init(dispatcher)

    async def create_system_bot(app):
        dispatcher = app['dispatcher']
        bot = SystemBot(app)
        bot.init(dispatcher)

    async def create_echo_bot(app):
        dispatcher = app['dispatcher']
        bot = EchoBot(app)
        bot.init(dispatcher)

    app.on_startup.append(create_history_bot)
    app.on_startup.append(create_translator_bot)
    app.on_startup.append(create_system_bot)
    app.on_startup.append(create_echo_bot)

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


async def start_dispatcher(app):
    app['dispatcher'].start()

def setup_dispatch(app):
    dispatcher = Dispatcher()
    app['dispatcher'] = dispatcher
    app.on_startup.append(start_dispatcher)


app = web.Application()
setup_config(app)
setup_routes(app)
setup_db(app)
setup_dispatch(app)
setup_bots(app)


if __name__ == '__main__':
    uvloop.install()
    web.run_app(app, host='127.0.0.1', port=8000)
