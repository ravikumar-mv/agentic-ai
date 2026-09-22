"""Thin wrapper pinning Assignment 5's memory.py `source` param to prefs.json.

memory.py's remember/recall/getMemoryData all take `source` explicitly with
no hidden default inside the module itself. This mirrors Assignment 5's own
tools.py pattern of pinning that path once so callers elsewhere don't
re-pass it on every call.
"""
import config
import memory


def remember(key, value):
    return memory.remember(key, value, config.PREFS_PATH)


def recall(key):
    return memory.recall(key, config.PREFS_PATH)


def get_all():
    return memory.getMemoryData(config.PREFS_PATH)


def summary():
    data = get_all()
    if not data:
        return "No standing preferences recorded yet."
    lines = [f"- {key}: {value}" for key, value in data.items()]
    return "Standing preferences on file:\n" + "\n".join(lines)
