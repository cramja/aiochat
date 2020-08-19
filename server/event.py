from abc import ABC
from dataclasses import asdict
from dataclasses import dataclass
from time import time as time_s
from typing import Optional
from uuid import uuid4
import json



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

class WsMessageEvent(MessageEvent):
    pass


@dataclass
class IntentEvent(Event):
    message: str
    # target: str
    action: str
    args: list
    kwargs: dict

    @classmethod
    def fromMessage(cls, event: MessageEvent) -> Optional['IntentEvent']:
        message = event.message.strip()
        if not message.startswith('.'):
            return None
        parts = message.split()
        args = []
        kwargs = {}
        for arg in parts[1:]:
            if '=' in arg:
                kv = arg.split('=')
                kwargs[kv[0]] = kv[1]
            else:
                args.append(arg)
        return cls(str(uuid4()), time_m(), event.message, event.client_id, parts[0][1:], args, kwargs)


@dataclass
class LifecycleEvent(Event):
    phase: str

    @classmethod
    def of(cls, client_id, phase):
        return cls(str(uuid4()), time_m(), client_id, phase)


# TODO: maintain this
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
