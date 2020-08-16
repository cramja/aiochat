import abc
import logging
import asyncio
from asyncio import queues

from event import MessageEvent
from event import IntentEvent
from dispatch import subscribe


LOG = logging.getLogger(__name__)


class Bot(abc.ABC):
    def __init__(self):
        self._submit = None

    def init(self, dispatcher):
        self._dispatch = dispatcher
        self._dispatch.register(self)

    def teardown(self):
        self._unregister(self)
        self._dispatch = None


class HistoryBot(Bot):
    def __init__(self, pgpool):
        self.client_id = 'history_bot'
        self._pgpool = pgpool
    
    @subscribe(kind="MessageEvent")
    async def on_message(self, event: MessageEvent):
        async with self._pgpool.acquire() as conn:
            await conn.execute(
                'INSERT INTO messages(client_id, value) VALUES ($1, $2)',
                event.client_id, 
                event.message
            )

class TranslatorBot(Bot):
    def __init__(self):
        self.client_id = 'translator_bot'
    
    @subscribe(kind="MessageEvent")
    async def on_message(self, event):
        if event.message.isupper():
            await self._dispatch._submit(IntentEvent.of(self.client_id, event.message))

    @subscribe(intent="START")
    async def on_start_q(self, event):
        bot = QuestionBot()
        bot.init(self._dispatch)
        await self._dispatch.submit(MessageEvent.of(self.client_id, "created questions bot"))


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
