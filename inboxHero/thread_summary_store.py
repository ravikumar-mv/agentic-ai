"""x2_thread_summaries.json -- Part 8 capability X2's own store, same
create-if-missing pattern as every other derived store (plan.md 3j),
kept independent of inbox_state.json (Part 8.2).
"""
import json

import config


def _load():
    if not config.X2_THREAD_SUMMARIES_PATH.exists():
        return []
    return json.loads(config.X2_THREAD_SUMMARIES_PATH.read_text())


def _save(entries):
    config.X2_THREAD_SUMMARIES_PATH.write_text(json.dumps(entries, indent=2) + "\n")


def add_summary(thread_id, summary, open_question, resolved, source_message_ids, source="agent"):
    entries = [e for e in _load() if e["thread_id"] != thread_id]
    entry = {
        "thread_id": thread_id,
        "summary": summary,
        "open_question": open_question,
        "resolved": bool(resolved),
        "source_message_ids": source_message_ids,
        "source": source,
    }
    entries.append(entry)
    _save(entries)
    return entry


def get_summary(thread_id):
    return next((e for e in _load() if e["thread_id"] == thread_id), None)


def all_summaries():
    return _load()
