import json, random

with open("varibles/texts.json", encoding="utf-8") as f:
    DIALOGS = json.load(f)

def TEXT(*keys, **kwargs):
    data = DIALOGS

    try:
        for key in keys:
            data = data[key]

        if isinstance(data, list):
            data = random.choice(data)

        if isinstance(data, str) and kwargs:
            data = data.format(**kwargs)

        return data

    except KeyError:
        return f"[MISSING TEXT: {' -> '.join(keys)}]"