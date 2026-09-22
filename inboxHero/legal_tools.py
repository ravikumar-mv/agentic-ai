"""The Legal Agent's only tool (Part 8, X1). It cannot send, forward, or
delete anything -- the only thing it can do is record a classification."""
import legal_store
import trace


def setLegalFlag(message_id: str, is_legal: bool, reason: str) -> str:
    """Records whether a message is legal-related.

    Args:
        message_id: The id of the message being classified.
        is_legal: True if the message is genuinely legal-related --
            correspondence from a law firm or lawyer, a contract/IP-
            assignment/signature request, a compliance or legal-deadline
            mention, or a standing preference about legal correspondents.
        reason: A short, specific reason for the judgment.
    """
    if not isinstance(is_legal, bool):
        raise ValueError(f"is_legal must be a boolean, got {type(is_legal)}")

    legal_store.set_flag(message_id, is_legal, reason, source="agent")
    trace.append_event(
        event="action",
        message_id=message_id,
        source="legal_agent",
        payload={"type": "x1_legal", "is_legal": is_legal, "reason": reason},
    )
    return f"Recorded {message_id} as {'legal-related' if is_legal else 'not legal-related'}."
