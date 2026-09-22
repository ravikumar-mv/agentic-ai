"""The Thread Agent's only tool (Part 8, X2). Self-verifying before it
persists, same pattern as action_tools.draftReply: a hallucinated open
question never gets written, it just looks like the tool wasn't called,
and the retry loop handles it the same way either way.
"""
import citation_checker
import inbox_state
import thread_summary_store
import trace


def recordThreadSummary(
    thread_id: str,
    summary: str,
    open_question: str,
    resolved: bool,
    source_message_ids: list,
) -> str:
    """Records a thread's summary and its open question, if any.

    Args:
        thread_id: The thread being summarized.
        summary: A short summary of what's been discussed/decided.
        open_question: The specific question or request that was raised in
            the thread and never subsequently answered by a later message
            in the same thread. Empty string if resolved is True.
        resolved: True if everything raised in the thread has already been
            addressed by a later message -- no open question remains.
        source_message_ids: Every message id the open_question (or, if
            resolved, the summary) is grounded in. Must belong to this
            thread.
    """
    thread_ids = {m["id"] for m in inbox_state.messages_by_thread(thread_id)}
    unknown = set(source_message_ids) - thread_ids
    if unknown:
        raise ValueError(
            f"source_message_ids {sorted(unknown)} are not part of thread '{thread_id}'"
        )

    if not resolved and open_question:
        ok, reason = citation_checker.verify(open_question, source_message_ids)
        if not ok:
            return f"Not recorded -- open_question failed grounding check: {reason}"

    thread_summary_store.add_summary(
        thread_id, summary, open_question or None, resolved, source_message_ids
    )
    trace.append_event(
        event="action",
        message_id=thread_id,
        source="thread_agent",
        payload={"type": "x2_thread_summary", "resolved": resolved, "open_question": open_question},
    )
    return f"Recorded summary for thread '{thread_id}'."
