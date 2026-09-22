"""inbox.json is read-only, forever. inbox_state.json is the mutable copy
every tool actually reads/writes. Create-if-missing, never reset by a
normal run (see plan.md 3j) -- this is what makes a run idempotent without
ever touching the given input fixture.
"""
import json
import shutil

import config


def ensure_state():
    if not config.INBOX_STATE_PATH.exists():
        shutil.copy(config.INBOX_PATH, config.INBOX_STATE_PATH)


def reset_state():
    """Manual dev-only reset. No graded command calls this automatically."""
    shutil.copy(config.INBOX_PATH, config.INBOX_STATE_PATH)


def load_state():
    ensure_state()
    return json.loads(config.INBOX_STATE_PATH.read_text())


def save_state(messages):
    config.INBOX_STATE_PATH.write_text(json.dumps(messages, indent=2) + "\n")


def get_message(message_id):
    for m in load_state():
        if m.get("id") == message_id:
            return m
    return None


def update_message(message_id, **fields):
    messages = load_state()
    for m in messages:
        if m.get("id") == message_id:
            m.update(fields)
            save_state(messages)
            return m
    raise ValueError(f"No message found with id '{message_id}'")


def all_messages():
    return load_state()


def undisposed_messages():
    return [m for m in load_state() if "disposition" not in m]


def messages_by_thread(thread_id):
    return sorted(
        (m for m in load_state() if m.get("thread_id") == thread_id),
        key=lambda m: m.get("timestamp", ""),
    )
