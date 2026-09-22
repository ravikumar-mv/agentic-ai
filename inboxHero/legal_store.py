"""x1_legal.json -- Part 8 capability X1's own store, not inbox_state.json.
Same create-if-missing, never-reset-mid-sequence pattern as every other
derived store (plan.md 3j). Kept separate from the required six's stores so
this capability stays independently runnable and inspectable (Part 8.2).
"""
import json

import config
import inbox_state


def _load():
    if not config.X1_LEGAL_PATH.exists():
        return []
    return json.loads(config.X1_LEGAL_PATH.read_text())


def _save(entries):
    config.X1_LEGAL_PATH.write_text(json.dumps(entries, indent=2) + "\n")


def set_flag(message_id, is_legal, reason, source="agent"):
    # Verified real: the model once hallucinated a numeric, non-existent
    # message_id argument, which was silently persisted since nothing
    # checked it. disposeMessage is protected against this via
    # inbox_state.update_message's own guard; this store had no
    # equivalent. Same fix here.
    if inbox_state.get_message(message_id) is None:
        raise ValueError(f"No such message id '{message_id}'")
    entries = [e for e in _load() if e["message_id"] != message_id]
    entry = {
        "message_id": message_id,
        "is_legal": bool(is_legal),
        "reason": reason,
        "source": source,
    }
    entries.append(entry)
    _save(entries)
    return entry


def get_flag(message_id):
    return next((e for e in _load() if e["message_id"] == message_id), None)


def all_flags():
    return _load()


def processed_ids():
    return {e["message_id"] for e in _load()}


def legal_messages():
    return [e for e in _load() if e.get("is_legal")]
