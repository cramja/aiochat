from datetime import datetime

def _jsonable(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def to_dict(record):
    return {
        k: _jsonable(v) for k,v in record.items()
    }