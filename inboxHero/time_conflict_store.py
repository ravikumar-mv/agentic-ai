"""x3_time_conflicts.json -- Part 8 capability X3's own store, same
create-if-missing pattern as every other derived store (plan.md 3j).
"""
import json

import config
import inbox_state


def _load():
    if not config.X3_TIME_CONFLICTS_PATH.exists():
        return []
    return json.loads(config.X3_TIME_CONFLICTS_PATH.read_text())


def _save(entries):
    config.X3_TIME_CONFLICTS_PATH.write_text(json.dumps(entries, indent=2) + "\n")


def log_check(
    message_id,
    is_time_request,
    requested_date=None,
    requested_start_time=None,
    requested_end_time=None,
    duration_minutes=None,
    conflict=False,
    conflict_with=None,
    conflict_reason=None,
    proposed_slots=None,
):
    if inbox_state.get_message(message_id) is None:
        raise ValueError(f"No such message id '{message_id}'")
    entries = [e for e in _load() if e["message_id"] != message_id]
    entry = {
        "message_id": message_id,
        "is_time_request": bool(is_time_request),
        "requested_date": requested_date,
        "requested_start_time": requested_start_time,
        "requested_end_time": requested_end_time,
        "duration_minutes": duration_minutes,
        "conflict": bool(conflict),
        "conflict_with": conflict_with or [],
        "conflict_reason": conflict_reason,
        "proposed_slots": proposed_slots or [],
    }
    entries.append(entry)
    _save(entries)
    return entry


def get(message_id):
    return next((e for e in _load() if e["message_id"] == message_id), None)


def all_entries():
    return _load()


def processed_ids():
    return {e["message_id"] for e in _load()}


def conflicts():
    return [e for e in _load() if e.get("conflict")]


def all_proposed_slots():
    """Every slot proposed so far across all conflicts -- read straight
    from the store rather than threaded in-memory state, so this stays
    stateless and resumable like everything else in this build."""
    slots = []
    for e in _load():
        slots.extend(e.get("proposed_slots") or [])
    return slots
