"""Part 3 -- hybrid retrieval (plan.md 3c). Thread-walk first (structural,
zero cost, exact), embeddings for cross-thread grounding, keyword search as
a final deterministic fallback when the embedding call is unavailable.
Schema-generic: works off thread_id/subject/body, never a literal id.
"""
import embeddings
import inbox_state
from citation_checker import _TRAILING_PUNCTUATION


def thread_walk(message):
    """Every other message in the same thread, chronologically ordered,
    excluding the message itself."""
    thread = inbox_state.messages_by_thread(message.get("thread_id"))
    return [m for m in thread if m["id"] != message["id"]]


def keyword_search(message, all_messages, k=3):
    """Cheap deterministic fallback: score by shared significant words."""
    query_words = set(w for w in _words(message) if len(w) > 3)
    scored = []
    for m in all_messages:
        if m["id"] == message["id"]:
            continue
        words = set(w for w in _words(m) if len(w) > 3)
        overlap = len(query_words & words)
        if overlap:
            scored.append((m, overlap))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [m for m, _ in scored[:k]]


def _words(message):
    # Verified real: "review?" and "review" never matched as the same
    # word before this strip, which is exactly why m040's keyword search
    # missed m038 (the two share only "board" as a result). Reuses
    # citation_checker's own punctuation set rather than a second one.
    text = f"{message.get('subject', '')} {message.get('body', '')}".lower()
    return [w.strip(_TRAILING_PUNCTUATION) for w in text.replace("\n", " ").split()]


def find_grounding_candidates(message, k=3):
    """Returns candidate messages to ground a reply to `message`, trying
    thread-walk, then embeddings, then keyword search, in that order.
    Returns (candidates, method_used)."""
    thread_candidates = thread_walk(message)
    if thread_candidates:
        return thread_candidates, "thread-walk"

    all_messages = inbox_state.all_messages()
    query_text = f"{message.get('subject', '')}\n{message.get('body', '')}"

    try:
        scored = embeddings.top_k_similar(
            query_text, all_messages, k=k, exclude_ids={message["id"]}
        )
        if scored:
            return [m for m, _ in scored], "embeddings"
    except Exception:
        pass  # embedding API unavailable -- fall through to keyword search

    keyword_candidates = keyword_search(message, all_messages, k=k)
    if keyword_candidates:
        return keyword_candidates, "keyword"

    return [], "none"
