"""actions.json -- every draftReply/markForAttention result (plan.md 3i).
Same create-if-missing-by-nature, never-reset-mid-sequence rule as the
other derived stores (3j): this module just persists whatever it's told.
"""
import json

import config
import inbox_state


def _load():
    if not config.ACTIONS_PATH.exists():
        return []
    return json.loads(config.ACTIONS_PATH.read_text())


def _save(entries):
    config.ACTIONS_PATH.write_text(json.dumps(entries, indent=2) + "\n")


def add_action(message_id, **fields):
    # Same fix as legal_store/time_conflict_store: verified real that a
    # model can hallucinate a non-existent message_id argument, and
    # nothing here checked it before this.
    if inbox_state.get_message(message_id) is None:
        raise ValueError(f"No such message id '{message_id}'")
    entries = [e for e in _load() if e["message_id"] != message_id]
    entry = {"message_id": message_id, **fields}
    entries.append(entry)
    _save(entries)
    return entry


def update_action(message_id, **fields):
    entries = _load()
    for e in entries:
        if e["message_id"] == message_id:
            e.update(fields)
            _save(entries)
            return e
    raise ValueError(f"No action found for message '{message_id}'")


def all_actions(action_type=None):
    entries = _load()
    if action_type:
        entries = [e for e in entries if e.get("type") == action_type]
    return entries


def pending_replies():
    return [e for e in all_actions("reply") if e.get("status") == "pending_approval"]
