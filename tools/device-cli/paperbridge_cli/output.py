import json


def emit(value, json_output=False):
    if json_output:
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list, tuple)):
                item = json.dumps(item, sort_keys=True)
            print(f"{key}: {item}")
    elif isinstance(value, list):
        for item in value:
            emit(item)
            print()
    else:
        print(value)
