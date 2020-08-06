import pathlib
import json
import logging
import sys
from uuid import uuid4 as uuid

from aiohttp import WSMsgType
from aiohttp.web_ws import WebSocketResponse
from aiohttp import web
from asyncio import wait_for
from asyncio import queues
from asyncio import TimeoutError
from asyncio.queues import QueueEmpty
from asyncio import create_task
from asyncio import gather
import uvloop

from helpers import to_dict

LOG = logging.getLogger(__name__)


message_queues = {} # clientId -> queue<message>
task_workers = {}   # clientId -> list<task>

DB = {}

async def broadcast_message(cid, message):
    LOG.info(f'broadcast to {len(message_queues)} clients')
    await gather(*[message_queues[k].put(message) for k in message_queues.keys()])
    

async def get_message(client_id):
    q = message_queues.get(client_id)
    if q:
        return await q.get()
    return None
    

async def get_message_history(request):
    pgpool = request.app['pgpool']
    async with pgpool.acquire() as conn:
        records = await conn.fetch('SELECT create_time, value, client_id FROM messages')
    return web.json_response(data=[to_dict(r) for r in records])


async def post_message(request):
    print(request)
    return web.json_response(data={'status': 'ok'})


async def handle_questions_command(ws, client_id, *args):
    if args[0] == 'wwwww':
        idx = DB.get('wwwww', 0)
        DB['wwwww'] = idx + 1
        questions = ['who', 'what', 'when', 'where', 'why']
        await broadcast_message(client_id, {
            'type': 'create_message',
            'text': questions[idx % len(questions)] + '?'
            })


COMMAND_HANDLERS = {
    'questions': handle_questions_command
}


async def handle_execute_command(ws, payload, **kwargs):
    name = payload['args'][0]
    if name in COMMAND_HANDLERS:
        await COMMAND_HANDLERS[name](ws, payload['cid'], *payload['args'][1:])
    else:
        pass

async def handle_list_commands(ws, payload, **kwargs):
    prefix = payload['args'][0]
    keys = sorted(list(COMMAND_HANDLERS.keys()))
    matches = []
    for key in keys:
        if key.startswith(prefix):
            matches.append(key)
    if not matches:
        return keys
    return matches
    

async def handle_create_message(ws, payload, app, **kwargs):
    client_id = payload['cid']
    pgpool = app['pgpool']
    async with pgpool.acquire() as conn:
        await conn.execute('INSERT INTO messages(client_id, value) VALUES ($1, $2)', client_id, payload['text'])
    await broadcast_message(client_id, payload)
    await ws.send_json({'type': 'ack'})


async def handle_unknown(ws, payload, **kwargs):
    print(f'unknown message type {payload}')


async def kill_workers(client_id):
    if client_id in task_workers:
        for worker in task_workers[client_id]:
            if not worker.done():
                worker.cancel()
        for worker in task_workers[client_id]:
            try:
                await worker
            except:
                pass
        del task_workers[client_id]


async def forward_new_messages(ws, client_id):
    while not ws.closed:
        msg = await get_message(client_id)
        if msg.get('type', '?') == 'create_message':
            await ws.send_json(msg)
        else:
            break


async def handle_open(ws, payload, **kwargs):
    client_id = payload['cid']
    message_queues[client_id] = queues.Queue()
    await kill_workers(client_id) # todo: remove
    task_workers[client_id] = [create_task(forward_new_messages(ws, client_id))]


async def handle_close(ws, payload, **kwargs):
    client_id = payload['cid']
    message_queues.pop(client_id)
    await kill_workers(client_id)
    await ws.close()


ROUTER = {
    'close': handle_close,
    'open': handle_open,
    'execute_command': handle_execute_command,
    'list_commands': handle_list_commands,
    'create_message': handle_create_message
}


async def route_message(ws: WebSocketResponse, message, app):
    try:
        payload = json.loads(message.data)
        handler = ROUTER.get(payload.get('type','?'), handle_unknown)
        await handler(ws, payload, app=app)
    except Exception:
        print(f'error processing message: {message}')

async def chat_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    while not ws.closed:
        msg = None
        try:
            msg = await ws.receive()
        except:
            e = sys.exc_info()[0]
            print('unknown error during receive')
            print(str(e))
            if not ws.closed:
                await ws.close()
            break
        
        if msg:
            if msg.type == WSMsgType.TEXT:
                await route_message(ws, msg, app=request.app)

            elif msg.type == WSMsgType.ERROR:
                print(f'ws connection raised exception {ws.exception()}')

            elif msg.type in {WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED}:
                print('socket closed normally')

            else:
                print(f'unknown message type {msg.type}')
    # todo: kill workers

    return ws

def init_app(app):
    app.router.add_get('/api/chat/ws', chat_ws)
    app.router.add_post('/api/chat/messages', post_message)
    app.router.add_get('/api/chat/history', get_message_history)