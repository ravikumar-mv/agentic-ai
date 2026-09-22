"""The Time Conflict Agent's two tools (Part 8, X3). Tool 1 does the
deterministic logging + conflict-check + slot-search entirely in Python --
the LLM only extracts fields from the message and reads back the slots
tool 1 hands it. The authoritative conflict determination and the
alternative slots both come from deterministic code (commitments.py /
time_planner.py), never from the model's own arithmetic.
"""
import actions_store
import commitments
import memory_store
import time_conflict_store
import time_planner
import trace


def logConflictAndGetAlternatives(
    message_id: str,
    is_time_request: bool,
    requested_date: str = None,
    requested_start_time: str = None,
    requested_end_time: str = None,
    duration_minutes: int = 60,
) -> str:
    """Logs whether a message is a meeting/time request and, if it
    conflicts with a standing preference or an existing commitment,
    computes 3 non-colliding alternative slots deterministically.

    Args:
        message_id: The id of the message being checked.
        is_time_request: True if this message proposes or asks for a
            specific meeting/appointment time.
        requested_date: ISO date 'YYYY-MM-DD' the message proposes, if any.
        requested_start_time: 24h 'HH:MM' the message proposes, if any.
        requested_end_time: 24h 'HH:MM' if explicitly stated, else None.
        duration_minutes: Meeting length if stated (e.g. "20 minutes"),
            defaults to 60 if not stated.

    Returns:
        A description of the outcome -- including the 3 alternative slots
        if there was a conflict, so a reply can be drafted next.
    """
    if not is_time_request:
        time_conflict_store.log_check(message_id, is_time_request=False)
        return "Not a time request -- no further action needed."

    if not requested_date or not requested_start_time:
        time_conflict_store.log_check(message_id, is_time_request=True)
        return "Time request noted, but no specific date/time could be extracted -- no conflict check possible."

    candidate = {
        "message_id": message_id,
        "date": requested_date,
        "start_time": requested_start_time,
        "end_time": requested_end_time or None,
    }
    prefs = memory_store.get_all()
    conflict, conflict_with, conflict_reason = commitments.find_conflicts(
        candidate, commitments.all_commitments(), prefs
    )

    if not conflict:
        time_conflict_store.log_check(
            message_id,
            is_time_request=True,
            requested_date=requested_date,
            requested_start_time=requested_start_time,
            requested_end_time=requested_end_time,
            duration_minutes=duration_minutes,
            conflict=False,
        )
        return "Time request noted -- no conflict found. No reply needed."

    slots = time_planner.find_alternative_slots(
        requested_date,
        requested_start_time,
        duration_minutes,
        commitments.all_commitments(),
        prefs,
        time_conflict_store.all_proposed_slots(),
    )
    time_conflict_store.log_check(
        message_id,
        is_time_request=True,
        requested_date=requested_date,
        requested_start_time=requested_start_time,
        requested_end_time=requested_end_time,
        duration_minutes=duration_minutes,
        conflict=True,
        conflict_with=conflict_with,
        conflict_reason=conflict_reason,
        proposed_slots=slots,
    )
    trace.append_event(
        event="action",
        message_id=message_id,
        source="time_conflict_agent",
        payload={"type": "x3_conflict", "conflict_reason": conflict_reason, "proposed_slots": slots},
    )
    slots_text = "; ".join(f"{s['date']} {s['start_time']}-{s['end_time']}" for s in slots)
    return (
        f"Conflict found: requested {requested_date} {requested_start_time} -- {conflict_reason}. "
        f"Propose these alternatives instead: {slots_text}. "
        f"Now call draftAlternativesReply with a courteous reply presenting them."
    )


def draftAlternativesReply(message_id: str, to: str, subject: str, draft_text: str) -> str:
    """Persists a drafted reply presenting the 3 alternative times,
    pending human approval -- never sent directly.

    Args:
        message_id: The id of the message being replied to.
        to: Recipient email address.
        subject: Reply subject line.
        draft_text: The drafted reply body, presenting the 3 already-
            computed alternative slots exactly as given.
    """
    entry = time_conflict_store.get(message_id)
    slots = entry.get("proposed_slots") if entry else []

    actions_store.add_action(
        message_id,
        type="reply",
        to=to,
        cc=[],
        subject=subject,
        body=draft_text,
        cited_message_ids=[message_id],
        summary=f"Proposed {len(slots)} alternative time(s) due to a conflict.",
        status="pending_approval",
    )
    trace.append_event(
        event="action",
        message_id=message_id,
        source="time_conflict_agent",
        payload={"type": "x3_draft_reply", "slots": slots},
    )
    return f"Draft reply for {message_id} recorded, pending approval."
