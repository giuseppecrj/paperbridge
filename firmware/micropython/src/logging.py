import json


def log(stream, level, message, **fields):
    record = {"type": "log", "level": level, "message": message}
    record.update(fields)
    stream.write(json.dumps(record) + "\n")
