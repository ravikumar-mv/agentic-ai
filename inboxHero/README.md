# inboxHero -- build status

Everything in `plan.md` is now implemented, except Part 8 (own capabilities)
and Part 9 (filling `CAPABILITIES.md`/`capabilities.json` for real), which
are intentionally deferred.

## Model setup

- **Embeddings/retrieval** (`embeddings.py`) use Google's embedding
  endpoint -- needs `GEMINI_API_KEY` in `.env`.
- **Every other LLM call** (both agents, `citation_checker.py`'s semantic
  layer) uses a **local Ollama model**, no API key needed:
  ```
  ollama pull gemma4:12b
  ```
  (requires the Ollama server running locally; override with `OLLAMA_MODEL`
  / `OLLAMA_API_BASE` in `.env` if needed.)

## Setup

```
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY (embeddings only)
```

## Running

```
./.venv/bin/python demo.py --reset        # bootstrap inbox_state.json from inbox.json
./.venv/bin/python demo.py --cap R1       # zero the inbox
./.venv/bin/python demo.py --cap R2 --msg m008
./.venv/bin/python demo.py --cap R3 --dry-run
./.venv/bin/python demo.py --cap R4       # run twice, fresh process each time, to see the restart demo
./.venv/bin/python demo.py --cap R5
./.venv/bin/python demo.py --cap R6       # writes dashboard.html / dashboard.json
./.venv/bin/python demo.py --all
```

Note: both agents process one message per LLM turn (see "reliability
findings" below), so a full `--all`/`--cap R1` run over the ~60
LLM-routed messages takes real wall-clock time against a local 12B model --
budget several minutes, not seconds.

## What's been live-tested (not just structurally verified)

- `rules.py` against the real 100-message inbox: 40 rule-handled, 60 routed
  to the Disposition Agent; every hostile/phishing message and every
  free-prose commitment candidate correctly falls through rather than being
  rule-resolved (this caught a real bug during build -- see below).
- `retrieval.py`'s thread-walk finds `m003` (the real AMQP URL) for `m008`.
- `citation_checker.py`'s structural layer accepts a genuinely grounded
  draft and rejects both a fabricated detail and a hallucinated citation id.
- `commitments.py`'s conflict detection: correctly flags `m010`/`m061`
  (same slot) and `m043` against the `no_meetings_before` preference;
  correctly does NOT flag unrelated commitments.
- `guard.py`, `gate.py` (dry-run and trace logging), `outbox.py`,
  `dashboard.py` (three tabs, conflict rows highlighted) -- exercised with
  synthetic data end to end.
- **The Disposition Agent, live, against `gemma4:12b`:** correctly disposed
  ordinary messages (`m001`->attention, `m005`->archive, etc.), correctly
  flagged real phishing (`m021`) and a spoofed-as-owner injection (`m039`)
  on the first attempt, and correctly flagged the newsletter-disguised
  injection (`m024`) via the retry+fallback path after its first attempt
  narrated the tool call instead of invoking it.

## Two reliability findings from live testing (not design guesses)

1. **Batch size.** A ~12B local model reliably calls its tool for a single
   message per turn, but given several messages in one prompt it reliably
   fails to ever reach the tool call at all -- it exhausts its output
   budget on chain-of-thought narration first. Fixed by processing one
   message per turn in both `disposition_agent.run()` and
   `action_agent.run()`. Costs wall-clock time, not API cost -- the right
   trade for a local model.
2. **Narrated-not-invoked tool calls.** Even one message per turn, the
   model sometimes writes out "Call disposeMessage(...)" as prose with
   entirely correct reasoning, but never issues the real function call.
   Both agents now retry once with an explicit nudge, then fall back to a
   deterministic decision (`disposeMessage(..., "attention", ...)` /
   `markForAttention(...)`) if the tool still wasn't called -- so "no
   message left without a disposition" (Part 2.2) is an architectural
   guarantee, not a hope that the model complies.

## Final Report

**1. What did you refuse to automate?**

`m008` asks Sam's colleague Devika to resend the live staging AMQP
credentials rather than rotate them — a social-engineering pattern even
though the sender's domain (`paperjet.io`) is genuinely internal. The
Disposition Agent flags it `defer`, and `defer` is structurally excluded
from the Action Agent's eligible set, so no reply is ever drafted for it —
this isn't a one-time judgment call, it's a routing rule. We drew the line
here because a legitimate internal domain isn't sufficient evidence of
intent (`m039`, an actual injection, is self-addressed from that same
domain), so resending a live secret needs a human's judgment about the
requester's actual need, not an inference from message content alone.

**2. Where does untrusted text enter your system?**

Untrusted text enters through every message body, wrapped by
`guard.wrap_untrusted()` before it reaches any prompt — a structural
framing, not an "ignore instructions" line (which the assignment itself
notes is insufficient). The real boundary is that no agent holds a tool
capable of sending, forwarding, or deleting: the Disposition Agent only
has `disposeMessage`/`capturePreference`, the Action Agent only has
`draftReply`/`markForAttention`/`markTimeCommitment` — none touch
`outbox/`. `gate.py`'s `request_approval` is the only function that ever
calls `outbox.write_message`. So an attacker (like `m024`'s "forward the
mailbox, delete this" or `m039`'s self-addressed "enable autonomous mode")
would have to defeat three independent things at once — the untrusted-data
framing, the absence of any tool that could comply, and the approval gate
— not just persuade the model once.

**3. Who is accountable when it sends the wrong thing?**

The owner is accountable for the send itself — the uniform gate means
nothing reaches `outbox/` without an explicit "y" to a specific proposal,
so approving a bad draft is the proximate act that sent it. The system is
accountable for what it put in front of them: every gate call appends a
`trace.jsonl` entry with the exact `payload_summary` shown, the human's
response, and the outcome, so tracing a bad send starts by reading exactly
what was on screen at approval time. If the content itself was wrong, the
corresponding `actions_store` entry's `cited_message_ids` shows what it
claimed to be grounded in — distinguishing a `citation_checker` failure
(the system's fault) from the owner simply not reading closely (a human
failure).

**4. Name your own machinery.**

- **Agents**: `disposition_agent.py`, `action_agent.py`, and the three
  Part 8 agents (`legal_agent.py`, `thread_agent.py`,
  `time_conflict_agent.py`).
- **Tasks**: the tool functions each agent calls — `disposeMessage`,
  `capturePreference`, `draftReply`, `markForAttention`,
  `markTimeCommitment`, and their Part 8 equivalents.
- **Crew and Router collapse into the same thing here**: `demo.py`.
  There's no separate negotiation between agents to coordinate — the
  pipeline is a fixed sequence (rules → Disposition Agent → Action Agent →
  dashboard), so one hand-rolled router plays both roles.
- **What ADK didn't give us**: any guarantee that a model actually invokes
  a tool it decided to call, or any recovery when it doesn't. We hand-built
  a retry-with-nudge-then-deterministic-fallback for this, and it caught
  real, confirmed bugs (`m024` and `m047` narrating a decision without ever
  calling `disposeMessage`; `markTimeCommitment` succeeding while a stale
  retry-loop check still thought it hadn't). Using a heavier framework
  primitive here would likely have hurt, not helped — the failures were
  about model behavior, not plumbing, and no orchestration layer fixes a
  model that narrates instead of invoking; only close, per-call
  verification at exactly this granularity does.

## A bug worth noting (in the rule engine, not the agents)

While validating `rules.py` against the real inbox, the bare keyword
`"digest"` (meant to archive newsletters like `m068`/`m111`) also matched
`m024`'s subject line ("Your weekly product digest") -- the exact
prompt-injection message Part 6 is testing for, disguised as a newsletter.
Fixed with a narrow circuit-breaker (`_addresses_automated_reader`): if a
message addresses itself to an automated/AI reader at all, no Step 1 rule
may resolve it, however noise-shaped it otherwise looks -- it always falls
through to the Disposition Agent. Re-verified against all 100 messages
after the fix, and the Disposition Agent itself was then confirmed to
correctly catch it live (see above).
