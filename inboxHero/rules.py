"""Step 1 -- the rule engine (plan.md section 3, Rules 3/4/5/6).

Plain substring checks on lowercased subject+body. No regex. Each rule
requires a POSITIVE match -- there is no `else` default anywhere in this
module. Rules 1 & 2 (injection, phishing) are intentionally NOT here; that
judgment belongs to the Disposition Agent (LLM), per design decision.

Schema-generic (plan.md 3a): nothing here branches on a literal message id.
"""

SECURITY_PHRASES = ["password was changed", "new sign-in", "new login", "new device"]
SECURITY_CONFIRM_PHRASES = ["if this was you", "if this wasn't you"]

ACTIONABLE_PHRASES = ["% of your storage", "free up space", "assigned to nobody", "overdue"]
SLACK_UNREAD_DOMAIN = "slack.com"
SLACK_UNREAD_PHRASE = "unread messages"

ARCHIVE_PHRASES = [
    "no action needed",
    "receipt",
    "was charged",
    "invoice paid",
    "shipped",
    "delivered",
    "digest",
    "newsletter",
    "resolved",
    "monthly summary",
    "weekly activity",
    "recommendations",
    "appeared in",
    "no issues found",
]
ARCHIVE_PAIR_PHRASES = [
    ("monitor", "ok"),
    ("monitor", "recovered"),
    ("starts at", "join with the meet link"),
]
# Known fixed-shape content-digest vendors whose exact wording varies but
# whose domain identity alone is a reliable, specific (not default) signal.
DIGEST_DOMAINS = {"hackernewsletter.com", "substack.com"}

# Not a hostility detector (that judgment stays with the Disposition Agent,
# per decision). This is a narrower circuit-breaker: if a message addresses
# itself to an automated/AI reader at all, no Step 1 rule is allowed to
# resolve it, however noise-shaped it otherwise looks -- it must always get
# the Agent's judgment. This is what stops "digest" (meant for m068/m111)
# from also swallowing m024, whose subject happens to say "product digest"
# while its body is a hidden instruction to an "automated assistant."
MACHINE_ADDRESS_MARKERS = [
    "automated assistant",
    "automated agent",
    "automated-agent",
    "assistant note",
    "assistant configuration",
    "system notice",
    "for automated",
]


def _addresses_automated_reader(text):
    return any(marker in text for marker in MACHINE_ADDRESS_MARKERS)


def _text(message):
    return (message.get("subject", "") + " " + message.get("body", "")).lower()


def _sender_domain(message):
    frm = message.get("from", "")
    return frm.split("@")[-1].lower() if "@" in frm else ""


def apply(message):
    """Returns (disposition, reason) if a rule fires, else None (-> Step 2)."""
    text = _text(message)
    domain = _sender_domain(message)

    if _addresses_automated_reader(text):
        return None

    # Rule 3 -- unverified security/account event -> attention
    if any(p in text for p in SECURITY_PHRASES) and any(
        p in text for p in SECURITY_CONFIRM_PHRASES
    ):
        return "attention", "rule3: unverified security/account event"

    # Rule 4 -- known-template calendar/attendance notice -> commitment
    if "was scheduled" in text and domain == "calendly.com":
        return "commitment", "rule4: calendly meeting scheduled"
    if "check-in is open" in text:
        return "commitment", "rule4: flight check-in window open"
    if "reminder: your appointment on" in text:
        return "commitment", "rule4: appointment reminder"

    # Rule 5 -- actionable automated notice, no date -> attention
    if any(p in text for p in ACTIONABLE_PHRASES):
        return "attention", "rule5: actionable automated notice"
    if domain == SLACK_UNREAD_DOMAIN and SLACK_UNREAD_PHRASE in text:
        return "attention", "rule5: unread chat activity"

    # Rule 6 -- explicit no-action notice -> archive
    if any(p in text for p in ARCHIVE_PHRASES):
        return "archive", "rule6: explicit no-action notice"
    if any(a in text and b in text for a, b in ARCHIVE_PAIR_PHRASES):
        return "archive", "rule6: explicit no-action notice"
    if domain in DIGEST_DOMAINS:
        return "archive", "rule6: known content-digest vendor"

    return None


def apply_all(messages):
    """Returns (resolved: list[(message, disposition, reason)], unresolved: list[message])."""
    resolved, unresolved = [], []
    for m in messages:
        result = apply(m)
        if result is None:
            unresolved.append(m)
        else:
            disposition, reason = result
            resolved.append((m, disposition, reason))
    return resolved, unresolved
