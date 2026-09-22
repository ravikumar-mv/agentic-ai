"""Part 3.2 / 3.4 -- the citation checker (plan.md 3g). Two layers,
mirroring the rule-then-LLM pattern used everywhere else in this design.
Called by the Action Agent BEFORE it calls draftReply -- a failed check
never produces a persisted draft.
"""
import os
import re

# Must be set before litellm is imported -- it fetches a pricing map from
# GitHub at import time otherwise, which is pointless (and slow/noisy on a
# flaky connection) for a local Ollama model we already know the cost of
# (free). This is the earliest point litellm gets imported in this
# codebase's dependency graph, so it's the one place that reliably runs
# before litellm's own module-level fetch.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm

import config
import inbox_state

HARD_FACT_PATTERNS = [
    r"https?://\S+",
    r"\bamqp://\S+",
    r"\$[\d,]+(?:\.\d+)?",
    r"\b\d{1,2}:\d{2}\s?(?:am|pm)?\b",
]

_TRAILING_PUNCTUATION = ".,;:!?)]}\"'"


def _extract_hard_facts(text):
    facts = []
    for pattern in HARD_FACT_PATTERNS:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            # A URL/amqp match greedily includes a trailing sentence period
            # or comma that isn't actually part of the fact -- strip it, or
            # a perfectly correct draft gets rejected for punctuation, not
            # content. Verified against the real m008/m003 case.
            facts.append(match.rstrip(_TRAILING_PUNCTUATION))
    return facts


def check_structural(draft_text, cited_message_ids):
    """Layer A: every cited id must exist, and every hard fact in the draft
    must appear verbatim in the concatenated cited bodies."""
    cited_bodies = []
    for mid in cited_message_ids:
        m = inbox_state.get_message(mid)
        if m is None:
            return False, f"cited message id '{mid}' does not exist in the mail store"
        cited_bodies.append(f"{m.get('subject', '')}\n{m.get('body', '')}")
    cited_text = "\n".join(cited_bodies)

    for fact in _extract_hard_facts(draft_text):
        if fact not in cited_text:
            return False, f"draft contains '{fact}', not found in any cited message"

    return True, None


def check_semantic(draft_text, cited_message_ids):
    """Layer B: only runs if Layer A passes. Independent LLM call given
    ONLY the cited bodies + draft, asked to list unsupported claims."""
    cited_bodies = []
    for mid in cited_message_ids:
        m = inbox_state.get_message(mid)
        cited_bodies.append(f"[{mid}] {m.get('subject', '')}\n{m.get('body', '')}")
    cited_text = "\n\n".join(cited_bodies)

    prompt = (
        "You are a fact-checker focused ONLY on substantive factual claims -- "
        "specific facts, numbers, dates, credentials, decisions, or instructions "
        "that would matter if wrong. IGNORE greetings, who the reply is "
        "addressed to, pleasantries, and narrative connecting phrases (e.g. "
        "'as mentioned', 'per your request', who said what to whom) -- these "
        "do not need independent support. Below are source messages and a "
        "draft reply. List any SUBSTANTIVE factual claim in the draft that is "
        "NOT supported by the source messages. If every substantive claim is "
        "supported, respond with exactly: SUPPORTED\n\n"
        f"SOURCE MESSAGES:\n{cited_text}\n\n"
        f"DRAFT REPLY:\n{draft_text}"
    )
    kwargs = {"api_base": config.OLLAMA_API_BASE} if config.OLLAMA_API_BASE else {}
    response = litellm.completion(
        model=config.LOCAL_LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    text = (response.choices[0].message.content or "").strip()
    if text.upper().startswith("SUPPORTED"):
        return True, None
    return False, text


def verify(draft_text, cited_message_ids, run_semantic=True):
    """Full two-layer check. Returns (ok: bool, reason)."""
    ok, reason = check_structural(draft_text, cited_message_ids)
    if not ok:
        return False, reason
    if not run_semantic:
        return True, None
    return check_semantic(draft_text, cited_message_ids)
