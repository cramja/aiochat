from asyncio import create_task
from asyncio import gather
from asyncio import queues
from dataclasses import dataclass
from functools import wraps
import logging

from event import Event
from event import IntentEvent

LOG = logging.getLogger(__name__)

# EventKind | * -> [qualname]
_event_manifest = {}

# INTENT -> [qualname]
_intent_manifest = {}


def subscribe(kind=None, intent=None):
    def wrapper(fn):
        @wraps(fn)
        def dec(*args, **kwargs):
            return fn(*args, **kwargs)
        if kind:
            methods = _event_manifest.get(kind, [])
            methods.append(fn.__qualname__)
            _event_manifest[kind] = methods
        elif intent:
            methods = _intent_manifest.get(intent, [])
            methods.append(fn.__qualname__)
            _intent_manifest[intent] = methods

        return dec
    return wrapper


class Dispatcher:
    def __init__(self):
        self._tasks = []
        self._bots = []
        self._queue = queues.Queue()

    def register(self, bot):
        self._bots.append(bot)

    def unregister(self, bot):
        self._bots.remove(bot)

    async def submit(self, event):
        await self._queue.put(event)

    def start(self):
        if self._tasks:
            return
        for _ in range(4):
            self._tasks.append(create_task(self._run_forever()))

    async def _run_forever(self):
        while True:
            event = await self._queue.get()
            await self._on_event(event)

    async def _on_event(self, e):
        names = list(_event_manifest.get(e.kind, []))
        names.extend(_event_manifest.get('*', []))
        if isinstance(e, IntentEvent):
            names.extend(_intent_manifest.get(e.intent, []))


        coroutines = []

        _names = []
        for bot in self._bots:
            instance_name = type(bot).__name__ + "."
            for name in names:
                if name.startswith(instance_name):
                    _names.append(instance_name)
                    method_name = name[len(instance_name):]
                    method = getattr(bot, method_name)
                    try:
                        coroutines.append(method(e))
                    except:
                        print(f'failed to publish {e} to {name}')

        LOG.debug(f'event dispatch: {e}')
        LOG.debug(f'matched: {names}')
        LOG.debug(f'available: {[type(b) for b in self._bots]}')
        LOG.debug(f'available matched: {_names}')
        
        results = await gather(*coroutines, return_exceptions=True)    

        for idx, result in enumerate(results):
            if isinstance(result, Event):
                await self.submit(result)
            elif isinstance(result, Exception):
                LOG.warning(f'error in gather, {_names[idx]} {e}')

