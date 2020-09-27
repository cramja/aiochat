from db.orm import Column
from db.orm import Table


class MessageEntity(Table):
    id              = Column(primary_key=True)
    create_time     = Column
    client_id       = Column
    value           = Column


class IntentDataEntity(Table):
    id              = Column(primary_key=True)
    create_time     = Column
    client_id       = Column
    name            = Column
    value           = Column