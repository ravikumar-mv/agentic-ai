"""Part 7 -- the commitment store and conflict-detection logic (plan.md 3i).

Owns both the store and the conflict check (not duplicated inside the
markTimeCommitment tool). Conflict detection is a generic interval-overlap
check against other commitments and against standing preferences -- no
message-id-specific logic, so it generalizes to any inbox.
"""
import json

import config


def _load():
    if not config.COMMITMENTS_PATH.exists():
        return []
    return json.loads(config.COMMITMENTS_PATH.read_text())


def _save(entries):
    config.COMMITMENTS_PATH.write_text(json.dumps(entries, indent=2) + "\n")


def _overlaps(a, b):
    """True if two (date, start_time, end_time) entries overlap. Missing
    times are treated conservatively -- same date with no times given is
    NOT flagged as a conflict, since there's nothing to compare."""
    if a["date"] != b["date"]:
        return False
    if not a.get("start_time") or not b.get("start_time"):
        return False
    a_start, a_end = a["start_time"], a.get("end_time") or a["start_time"]
    b_start, b_end = b["start_time"], b.get("end_time") or b["start_time"]
    return a_start < b_end and b_start < a_end


def find_conflicts(new_entry, existing_entries, preferences=None):
    """Returns (conflict: bool, conflict_with: list[message_id], reason)."""
    conflict_with = []
    reasons = []

    for other in existing_entries:
        if other["message_id"] == new_entry["message_id"]:
            continue
        if _overlaps(new_entry, other):
            conflict_with.append(other["message_id"])
            reasons.append(
                f"overlaps with {other['message_id']} "
                f"({other['date']} {other.get('start_time')})"
            )

    preferences = preferences or {}
    no_meetings_before = preferences.get("no_meetings_before")
    if no_meetings_before and new_entry.get("start_time"):
        if new_entry["start_time"] < no_meetings_before:
            conflict_with.append("preference:no_meetings_before")
            reasons.append(
                f"starts at {new_entry['start_time']}, before the "
                f"standing preference of not before {no_meetings_before}"
            )

    conflict = bool(conflict_with)
    return conflict, conflict_with, "; ".join(reasons) if reasons else None


def add_commitment(
    message_id,
    date,
    title,
    source_message_ids,
    start_time=None,
    end_time=None,
    preferences=None,
):
    entries = _load()
    new_entry = {
        "message_id": message_id,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "title": title,
        "source_message_ids": source_message_ids,
    }
    conflict, conflict_with, reason = find_conflicts(new_entry, entries, preferences)
    new_entry["conflict"] = conflict
    new_entry["conflict_with"] = conflict_with
    new_entry["conflict_reason"] = reason

    entries = [e for e in entries if e["message_id"] != message_id]
    entries.append(new_entry)
    _save(entries)
    return new_entry


def all_commitments():
    return _load()
