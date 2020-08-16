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

from bots import Bot
from dispatch import subscribe
from event import MessageEvent
from helpers import to_dict


LOG = logging.getLogger(__name__)



async def get_message_history(request):
    pgpool = request.app['pgpool']
    async with pgpool.acquire() as conn:
        records = await conn.fetch('SELECT create_time, value, client_id FROM messages')
    return web.json_response(data=[to_dict(r) for r in records])



class WsBot(Bot):
    def __init__(self, ws):
        self.client_id = None
        self.ws = ws
    
    async def run_until_close(self):
        while not self.ws.closed:
            msg = None
            try:
                msg = await self.ws.receive()
            except:
                e = sys.exc_info()[0]
                print('unknown error during receive')
                print(str(e))
                if not self.ws.closed:
                    await self.ws.close()
                break
            
            if msg:
                if msg.type == WSMsgType.TEXT:
                    # await route_message(ws, msg, app=request.app)
                    # TODO: put into an Event and continue looping
                    try:
                        payload = json.loads(msg.data)
                        if payload['type'] == 'open' and self.client_id is None:
                            self.client_id = payload['clientId']
                        elif payload['type'] == 'create_message' and self.client_id is not None:
                            await self._submit(MessageEvent.of(self.client_id, payload['text']))
                    except Exception as e:
                        print(f'error processing message: {msg}')
                        print(e)

                elif msg.type == WSMsgType.ERROR:
                    print(f'ws connection raised exception {self.ws.exception()}')

                elif msg.type in {WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED}:
                    print('socket closed normally')

                else:
                    print(f'unknown message type {msg.type}')

    
    @subscribe(kind="MessageEvent")
    async def on_message(self, event):
        # echo
        await self.ws.send_json(event.as_dict())


async def chat_ws(request):
    print('got ws request')
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    bot = WsBot(ws)
    bot.init(request.app['dispatcher'])
    await bot.run_until_close()
    bot.teardown()
    return ws
    

def init_app(app):
    app.router.add_get('/api/chat/ws', chat_ws)
    app.router.add_get('/api/chat/history', get_message_history)