"""Non-secret, per-user application preferences; identity stays untouched."""
import json
from .native_runtime import DATA


def read():
    try:
        value = json.loads((DATA / 'preferences.json').read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save(**changes):
    value = read()
    value.update(changes)
    DATA.mkdir(parents=True, exist_ok=True)
    temporary = DATA / 'preferences.tmp'
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.replace(DATA / 'preferences.json')
