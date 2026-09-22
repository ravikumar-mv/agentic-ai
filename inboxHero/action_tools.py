"""The Action Agent's three tools (plan.md 3b). Only reachable for messages
disposed reply/commitment/attention -- enforced by demo.py's orchestration,
which is the only thing that decides which messages this agent ever sees.
"""
import actions_store
import citation_checker
import commitments
import memory_store
import trace


def draftReply(
    message_id: str,
    to: str,
    subject: str,
    draft_text: str,
    cited_message_ids: list,
    summary: str,
    cc: list = None,
) -> str:
    """Drafts a reply grounded in specific earlier messages, held pending
    human approval (never sent directly -- that's gate.py's job). If the
    citation check fails, falls back to markForAttention instead of
    persisting an ungrounded draft.

    Args:
        message_id: The id of the message being replied to.
        to: Recipient email address.
        subject: Reply subject line.
        draft_text: The drafted reply body.
        cited_message_ids: Ids of the earlier messages this draft is
            grounded in. Must be real, checked against the mail store.
        summary: One-line summary of what this reply is based on.
        cc: Optional list of addresses to CC (e.g. per a standing preference).
    """
    ok, reason = citation_checker.verify(draft_text, cited_message_ids)
    if not ok:
        return markForAttention(
            message_id,
            f"needs a personal reply -- could not ground a safe draft ({reason})",
            summary,
        )

    actions_store.add_action(
        message_id,
        type="reply",
        to=to,
        cc=cc or [],
        subject=subject,
        body=draft_text,
        cited_message_ids=cited_message_ids,
        summary=summary,
        status="pending_approval",
    )
    trace.append_event(
        event="action",
        message_id=message_id,
        source="action_agent",
        payload={"type": "reply", "cited_message_ids": cited_message_ids, "summary": summary},
    )
    return f"Draft reply for {message_id} recorded, pending approval."


def markForAttention(message_id: str, action_needed: str, decided_from: str) -> str:
    """Records that this message needs the owner's personal attention --
    the system identified something to do but cannot do it itself.

    Args:
        message_id: The id of the message needing attention.
        action_needed: One-sentence description of the exact action needed.
        decided_from: Summary of how this was determined, and source
            message id(s) it was reasoned from.
    """
    actions_store.add_action(
        message_id, type="attention", action_needed=action_needed, decided_from=decided_from
    )
    trace.append_event(
        event="action",
        message_id=message_id,
        source="action_agent",
        payload={"type": "attention", "action_needed": action_needed, "decided_from": decided_from},
    )
    return f"Marked {message_id} for attention."


def markTimeCommitment(
    message_id: str,
    date: str,
    title: str,
    source_message_ids: list,
    start_time: str = None,
    end_time: str = None,
) -> str:
    """Records a dated obligation (meeting/appointment/deadline), checked
    for conflicts against other commitments and standing preferences.

    Args:
        message_id: The id of the message this commitment comes from.
        date: ISO date, e.g. '2026-09-15'.
        title: Short human-readable title.
        source_message_ids: Every message id this commitment was resolved
            from -- supports the multi-message case (date in one message,
            obligation in another).
        start_time: 24h 'HH:MM' if a specific time is stated, else None.
        end_time: 24h 'HH:MM' if known, else None.
    """
    prefs = memory_store.get_all()
    entry = commitments.add_commitment(
        message_id, date, title, source_message_ids, start_time, end_time, preferences=prefs
    )
    trace.append_event(
        event="action",
        message_id=message_id,
        source="action_agent",
        payload={"type": "commitment", **entry},
    )
    return f"Commitment recorded for {message_id}, conflict={entry['conflict']}."
