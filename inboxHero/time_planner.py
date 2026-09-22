"""Part 8, X3 -- deterministic slot search. No LLM here at all: finding
non-colliding alternative times is arithmetic, not judgment, so it stays
plain Python, same principle as commitments.find_conflicts.
"""
from datetime import datetime, timedelta

DAY_START_DEFAULT = "09:00"
DAY_END_DEFAULT = "18:00"
STEP_MINUTES = 60


def _to_dt(date_str, time_str):
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def _fmt_time(dt):
    return dt.strftime("%H:%M")


def _fmt_date(dt):
    return dt.strftime("%Y-%m-%d")


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _collides(date_str, start_dt, end_dt, existing_commitments, taken_slots):
    for c in existing_commitments:
        if c.get("date") != date_str or not c.get("start_time"):
            continue
        c_start = _to_dt(date_str, c["start_time"])
        c_end = _to_dt(date_str, c.get("end_time") or c["start_time"])
        if _overlaps(start_dt, end_dt, c_start, c_end):
            return True
    for s in taken_slots:
        if s.get("date") != date_str or not s.get("start_time"):
            continue
        s_start = _to_dt(date_str, s["start_time"])
        s_end = _to_dt(date_str, s.get("end_time") or s["start_time"])
        if _overlaps(start_dt, end_dt, s_start, s_end):
            return True
    return False


def find_alternative_slots(
    requested_date,
    requested_start_time,
    duration_minutes,
    existing_commitments,
    preferences,
    already_offered,
    max_slots=3,
    max_days=5,
):
    """Same-day-first, then next-day search. Respects a `no_meetings_before`
    preference if set, avoids real commitments and anything already
    offered earlier in this run. Deterministic -- correct by construction,
    nothing here needs verifying after the fact."""
    duration_minutes = duration_minutes or 60
    no_earlier_than = (preferences or {}).get("no_meetings_before") or DAY_START_DEFAULT

    orig_start = _to_dt(requested_date, requested_start_time)
    base_date = datetime.strptime(requested_date, "%Y-%m-%d")

    found = []
    for day_offset in range(max_days):
        day = base_date + timedelta(days=day_offset)
        date_str = _fmt_date(day)
        day_start = _to_dt(date_str, no_earlier_than)
        day_end = _to_dt(date_str, DAY_END_DEFAULT)

        cursor = day_start
        while cursor + timedelta(minutes=duration_minutes) <= day_end and len(found) < max_slots:
            slot_end = cursor + timedelta(minutes=duration_minutes)
            is_original = date_str == requested_date and cursor == orig_start
            if not is_original and not _collides(
                date_str, cursor, slot_end, existing_commitments, already_offered + found
            ):
                found.append(
                    {"date": date_str, "start_time": _fmt_time(cursor), "end_time": _fmt_time(slot_end)}
                )
            cursor += timedelta(minutes=STEP_MINUTES)

        if len(found) >= max_slots:
            break

    return found[:max_slots]


def render_fallback_reply(requested_date, requested_start_time, conflict_reason, slots):
    """Template used only if the LLM's drafting step never fires (see
    time_conflict_agent's fallback). The slots are already correct by
    construction regardless, so this degrades to plainer phrasing, never
    to a missing or wrong draft."""
    lines = [
        f"Hi, {requested_date} at {requested_start_time} doesn't work -- {conflict_reason}.",
        "Could one of these work instead?",
    ]
    for s in slots:
        lines.append(f"- {s['date']} {s['start_time']}-{s['end_time']}")
    return "\n".join(lines)
