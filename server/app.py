import pathlib
import json
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


message_history = []
message_queues = {} # clientId -> queue<message>
task_workers = {}   # clientId -> list<task>

DB = {}


async def broadcast_message(cid, message):
    await gather(*[message_queues[k].put(message) for k in message_queues.keys()])
    

async def get_message(client_id):
    q = message_queues.get(client_id)
    if q:
        return await q.get()
    return None
    


async def get_message_history(request):
    return web.json_response(data=message_history)


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


async def handle_execute_command(ws, payload):
    name = payload['args'][0]
    if name in COMMAND_HANDLERS:
        await COMMAND_HANDLERS[name](ws, payload['cid'], *payload['args'][1:])
    else:
        pass

async def handle_list_commands(ws, payload):
    prefix = payload['args'][0]
    keys = sorted(list(COMMAND_HANDLERS.keys()))
    matches = []
    for key in keys:
        if key.startswith(prefix):
            matches.append(key)
    if not matches:
        return keys
    return matches
    

async def handle_create_message(ws, payload):
    client_id = payload['cid']
    message_history.append(payload)
    await broadcast_message(client_id, payload)
    await ws.send_json({'type': 'ack'})


async def handle_unknown(ws, payload):
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


async def handle_open(ws, payload):
    client_id = payload['cid']
    message_queues[client_id] = queues.Queue()
    await kill_workers(client_id) # todo: remove
    task_workers[client_id] = [create_task(forward_new_messages(ws, client_id))]


async def handle_close(ws, payload):
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


async def route_message(ws: WebSocketResponse, message):
    try:
        payload = json.loads(message.data)
        handler = ROUTER.get(payload.get('type','?'), handle_unknown)
        await handler(ws, payload)
    except Exception as e:
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
                await route_message(ws, msg)

            elif msg.type == WSMsgType.ERROR:
                print(f'ws connection raised exception {ws.exception()}')

            elif msg.type in {WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED}:
                print('socket closed normally')

            else:
                print(f'unknown message type {msg.type}')
    # todo: kill workers

    return ws


async def get_index(request):
    return web.Response(status=301, headers={'location': '/app/index.html'})


def setup_routes(app):
    app.router.add_get('/', get_index)
    app.router.add_get('/api/chat/ws', chat_ws)
    app.router.add_post('/api/chat/messages', post_message)
    app.router.add_get('/api/chat/history', get_message_history)

    app.router.add_static('/app', str(pathlib.Path(__file__).parent.parent) + "/app", show_index=False)


app = web.Application()
setup_routes(app)

if __name__ == '__main__':
    uvloop.install()
    web.run_app(app, host='127.0.0.1', port=8000)
