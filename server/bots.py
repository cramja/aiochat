import abc
import logging
import asyncio
from asyncio import queues

from event import MessageEvent
from event import IntentEvent
from dispatch import subscribe
from db.models import IntentDataEntity
from db.models import MessageEntity


LOG = logging.getLogger(__name__)


class Bot(abc.ABC):
    """
    - should have a clientId
    - should have an instance id.. e.g. userId
    - bots which have a dependency on a certain user should exit once the user exits
      for a sufficient period of time
    """
    def __init__(self):
        self._submit = None

    def init(self, dispatcher):
        self._dispatch = dispatcher
        self._dispatch.register(self)

    def teardown(self):
        self._dispatch.unregister(self)
        self._dispatch = None


class HistoryBot(Bot):
    def __init__(self, pgpool):
        self.client_id = 'HistoryBot'
        self.pgp = pgpool


    @subscribe(kind="MessageEvent")
    async def on_message(self, event: MessageEvent):
        async with self.pgp.acquire() as conn:
            await MessageEntity.create(conn, client_id=event.client_id, value=event.message)

    
    @subscribe(intent="clearHistory")
    async def on_start(self, event):
        async with self.pgp.acquire() as conn:
            await conn.execute('DELETE FROM message WHERE TRUE;')
        await self._dispatch.submit(MessageEvent.of(self.client_id, 'cleared'))


class TranslatorBot(Bot):
    def __init__(self):
        self.client_id = 'TranslatorBot'
    
    @subscribe(kind="WsMessageEvent")
    async def on_message(self, event):
        intent = IntentEvent.fromMessage(event)
        if intent:
            await self._dispatch.submit(intent)
        elif len(event.message.strip()) > 0:
            await self._dispatch.submit(MessageEvent.of(event.client_id, event.message.strip()))


class SystemBot(Bot):
    def __init__(self, app):
        self.client_id = 'SystemBot'
        self.app = app

    @subscribe(intent="createBot")
    async def on_start(self, event):
        if event.args and event.args[0] == 'QuestionBot':
            bot = QuestionBot()
            bot.init(self._dispatch)
            await self._dispatch.submit(MessageEvent.of(self.client_id, "created questions bot"))
        elif event.args and event.args[0] == 'IntentRecorderBot':
            bot = IntentRecorderBot(self.app)
            bot.init(self._dispatch)
            await self._dispatch.submit(MessageEvent.of(self.client_id, "created intent bot"))
        else:
            await self._dispatch.submit(MessageEvent.of(self.client_id, f"unknown start arg: {event.args}"))


class EchoBot(Bot):
    def __init__(self, app):
        self.client_id = 'EchoBot'
        self.pgp = app['pgpool']

    @subscribe(kind='MessageEvent')
    async def on_message(self, event):
        if event.client_id != self.client_id:
            await self._dispatch.submit(MessageEvent.of(self.client_id, event.message))


class IntentRecorderBot(Bot):
    def __init__(self, app):
        self.client_id = 'IntentRecorderBot'
        self.pgp = app['pgpool']
        self.mode = None
        self.last_message_id = None
    
    @subscribe(kind='MessageEvent')
    async def on_message(self, event):
        if self.mode is not None:
            async with self.pgp.acquire() as conn:
                await IntentDataEntity.create(conn, name=self.mode, value=event.message)

    
    @subscribe(intent='exit')
    async def on_exit(self, event):
        await self._dispatch.submit(MessageEvent.of(self.client_id, 'exiting'))
        self.teardown()


    @subscribe(intent='setIntent')
    async def on_set_intent(self, event):
        intent_name = event.args[0]
        if intent_name == 'NONE':
            await self._dispatch.submit(MessageEvent.of(self.client_id, 'exiting'))
            self.teardown()
        else:
            self.mode = intent_name
            await self._dispatch.submit(MessageEvent.of(self.client_id, f'using intent "{intent_name}"'))


    @subscribe(intent='listIntents')
    async def on_list_intent(self, event):
        async with self.pgp.acquire() as conn:
            records = [repr(r) for r in await IntentDataEntity.all()]
        await self._dispatch.submit(MessageEvent.of(self.client_id, "\n".join(records)))


    @subscribe(intent='getState')
    async def on_get_state(self, event):
        await self._dispatch.submit(MessageEvent.of(self.client_id, f'mode is "{self.mode}"'))



class QuestionBot(Bot):
    _QUESTION_SETS = {'wwwww': ['who', 'what', 'when', 'where', 'why']}

    def __init__(self):
        self.client_id = 'question_bot'
        self.question_idx = 0
    
    @subscribe(intent='ASK')
    async def ask(self, event):
        await self._dispatch.submit(MessageEvent.of(self.client_id, QuestionBot._QUESTION_SETS['wwwww'][self.question_idx]))
        self.question_idx += 1
        if self.question_idx == len(QuestionBot._QUESTION_SETS['wwwww']):
            self.teardown()
