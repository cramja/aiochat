from abc import ABC
from dataclasses import asdict
from dataclasses import dataclass
from time import time as time_s
import json
from uuid import uuid4


def time_m():
    return int(time_s() * 1000)


@dataclass
class Event(ABC):
    key: str
    create_time: int
    client_id: str

    @property
    def kind(self):
        return self.__class__.__name__

    def as_dict(self):
        rv = asdict(self)
        rv['kind'] = self.kind
        return rv

    def to_json(self):
        return json.dumps(self.as_dict())


@dataclass
class MessageEvent(Event):
    message: str

    @classmethod
    def of(cls, client_id, message):
        return cls(str(uuid4()), time_m(), client_id, message)


@dataclass
class IntentEvent(Event):
    message: str
    intent: str

    @classmethod
    def of(cls, client_id, message):
        return cls(str(uuid4()), time_m(), client_id, message, message)
        

_events = {
    MessageEvent.__name__: MessageEvent,
    IntentEvent.__name__: IntentEvent
}


def parse(message):
    try:
        msg = json.loads(message)
    except:
        return None
    class_ = _events.get(msg.get('kind', ''), None)
    del msg['kind']
    if class_:
        return class_(**msg)
    return None
