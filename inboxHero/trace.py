"""One shared envelope for every event any module logs (plan.md 3m).

Append-only, never truncated by a normal run. `cap` is threaded via
set_active_cap() so individual tools don't have to pass it on every call --
demo.py sets it once at the start of a --cap Rx invocation.
"""
import contextvars
import json
from contextlib import contextmanager
from datetime import datetime, timezone

import config

VALID_EVENTS = {"decision", "gate", "refusal", "preference", "action"}

_active_cap = contextvars.ContextVar("active_cap", default=None)


@contextmanager
def set_active_cap(cap_id):
    token = _active_cap.set(cap_id)
    try:
        yield
    finally:
        _active_cap.reset(token)


def append_event(event, message_id, source, payload, cap=None):
    if event not in VALID_EVENTS:
        raise ValueError(
            f"Invalid trace event '{event}'. Must be one of {sorted(VALID_EVENTS)}"
        )
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "cap": cap if cap is not None else _active_cap.get(),
        "message_id": message_id,
        "source": source,
        "payload": payload,
    }
    with open(config.TRACE_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_events(event=None, cap=None, message_id=None):
    if not config.TRACE_PATH.exists():
        return []
    out = []
    with open(config.TRACE_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if event and e.get("event") != event:
                continue
            if cap and e.get("cap") != cap:
                continue
            if message_id and e.get("message_id") != message_id:
                continue
            out.append(e)
    return out
