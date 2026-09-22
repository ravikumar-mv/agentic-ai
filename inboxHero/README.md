# inboxHero

**Repository:** https://github.com/ravikumar-mv/agentic-ai/tree/master/inboxHero

An agentic inbox-triage system (FN_Assignment_06_InboxHero) that takes a
100-message mock inbox from unread to zero: disposing of every message,
drafting grounded replies, gating irreversible sends behind human
approval, honoring a persistent standing preference across a process
restart, refusing hostile/phishing content, and surfacing everything on a
three-pane dashboard — plus three additional capabilities (Part 8).

## Setup

```
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY (embeddings only)
```

- **Embeddings/retrieval** use Google's embedding endpoint
  (`gemini-embedding-001`) — needs `GEMINI_API_KEY` in `.env`.
- **Every other LLM call** (both required agents, the three Part 8 agents,
  `citation_checker.py`'s semantic layer) uses a **local Ollama model**, no
  API key needed:
  ```
  ollama pull gemma4:12b
  ```
  (requires the Ollama server running locally; override with `OLLAMA_MODEL`
  / `OLLAMA_API_BASE` in `.env` if needed.)

## Running

```
./.venv/bin/python demo.py --reset        # bootstrap inbox_state.json from inbox.json
./.venv/bin/python demo.py --cap R1       # zero the inbox
./.venv/bin/python demo.py --cap R2 --msg m008
./.venv/bin/python demo.py --cap R3 --dry-run
./.venv/bin/python demo.py --cap R4       # run twice, fresh process each time
./.venv/bin/python demo.py --cap R5
./.venv/bin/python demo.py --cap R6       # writes dashboard.html / dashboard.json
./.venv/bin/python demo.py --cap X1       # legal-mail classifier (Tier A)
./.venv/bin/python demo.py --cap X2 --thread t-launch   # thread summary (Tier B)
./.venv/bin/python demo.py --cap X3       # meeting-conflict resolver (Tier C)
./.venv/bin/python demo.py --all
```

Both agents process one message per LLM turn (see "reliability findings"
below), so a full run over the ~60 LLM-routed messages takes real
wall-clock time against a local 12B model — budget several minutes, not
seconds. `capabilities.json` is the machine-readable, authoritative version
of every command/observable/evidence triple; this file is for a human.

## Architecture

`rules.py` disposes of unambiguous noise (40 of 100 messages) with plain
substring checks, no model call — every rule requires a positive match, no
rule is an `else` default. Everything else goes to a Disposition Agent
(ADK `LlmAgent`, one message per turn), which also carries all Part 6
hostile/phishing judgment — no regex primary detector, by design. Messages
disposed `reply`/`attention`/`commitment` then go to an Action Agent, which
drafts replies (citation-checked against the mail store before anything is
persisted), marks attention items, or records commitments (checked for
conflicts against standing preferences and other commitments). Three Part 8
capabilities layer on top, each with its own dedicated agent and store:
a legal-mail classifier (Tier A), a thread summarizer that reasons across
an entire thread in one pass (Tier B), and a meeting-conflict resolver that
plans alternatives in deterministic Python and only uses the model for
extraction and drafting (Tier C). Orchestration between all of these is
plain Python in `demo.py` — there is no ADK Workflow/graph object anywhere
in this system; every stage is a function call. `inbox.json` is never
mutated; all derived state (dispositions, actions, commitments, each Part 8
capability's findings, preferences) lives in small JSON files, created on
first use and never reset mid-run. `trace.jsonl` is an append-only audit
log of every tool call, tagged by which capability produced it.

## Design choices you were asked to state

- **Framework: Google ADK** — `LlmAgent` + the `LiteLlm` model wrapper (for
  routing to a local Ollama model), used for every agent in the system,
  required six and Part 8 capabilities alike. Deliberately **not** used:
  ADK 2.0's `Workflow`/graph API — it exists and was inspected directly in
  the installed package, but its actual surface (private submodules,
  pydantic edge/state-schema validation, no accessible worked example)
  wasn't something to trust on a first pass, so orchestration is hand-rolled
  Python in `demo.py` instead. What ADK gave for free: automatic
  function-calling from plain Python functions, and a one-line-per-agent
  switch from a hosted model to a local one via `LiteLlm`. What it didn't
  give: the approval gate, the citation checker, the hostile-content
  enforcement layer, or any guarantee that a model actually invokes a tool
  it decided to call — all hand-rolled, and all of it mattered more than
  the framework choice itself (see Final Report Q4).
- **Disposition vocabulary (5 values): `reply`, `archive`, `attention`,
  `defer`, `commitment`.** `escalate` was in this vocabulary for most of
  the build but was retired: no rule ever produced it, the Disposition
  Agent's instruction gave it no content-based meaning, and nothing
  downstream routed on it — a message landing there was invisible
  everywhere, permanently. The `disposeMessage` retry-fallback now targets
  `attention` instead, which *is* wired into the Action Agent's eligible
  set. Every message gets exactly one disposition plus a mandatory reason
  string; a run is checked for zero undecided messages.
- **Retrieval: thread-walk primary**, since the inbox already carries
  `thread_id` — cheaper and exact for the common "answer is earlier in
  this exact conversation" case. Embeddings (Google's
  `gemini-embedding-001`, asymmetric `retrieval_document`/
  `retrieval_query` task types, cached to disk) are the fallback for
  cross-thread grounding; keyword search is the final fallback if the
  embedding call itself is unavailable.
- **Reversible vs irreversible.** `send` and `delete` are irreversible and
  gated; `draft`, `archive`, `defer`, `attention`, and `commitment` are
  reversible and run without a prompt. Deleting is irreversible in this
  design because the mock store has no trash. **Disclosed gap:** nothing
  in the required six or the three Part 8 capabilities currently triggers
  an actual delete — the gate mechanism supports it (`gate.py` and
  `guard.assert_not_deletable`), but no built capability exercises that
  path.
- **Where the gate sits.** `outbox.write_message` has exactly one caller in
  the entire codebase — `gate.py`'s approved branch. Gating policy is
  **uniform**: every send goes through the same prompt-or-`--dry-run` gate,
  no internal-vs-external exception. Trade-off: more prompts, in exchange
  for zero irreversible action ever executing without either an explicit
  approval or a dry-run showing it first.

## What's been live-tested against the real 100-message inbox

- `rules.py`: 40 rule-handled, 60 routed to the Disposition Agent; every
  hostile/phishing message and every free-prose commitment candidate
  correctly falls through rather than being rule-resolved.
- `retrieval.py`'s thread-walk finds `m003` (the real AMQP URL) for `m008`;
  its embeddings fallback correctly ranks `m038` #1 for `m040`'s query
  (0.771 similarity) once the embedding model bugs below were fixed.
- `citation_checker.py` accepts a genuinely grounded draft and rejects both
  a fabricated detail and a hallucinated citation id.
- `commitments.py`'s conflict detection correctly flags `m010`/`m061`
  (same slot) and `m043`/`m038` against the `no_meetings_before`
  preference, and correctly does not flag unrelated commitments.
- The Disposition Agent, live: correctly flagged 8 hostile/phishing
  messages (`m008`, `m017`, `m021`, `m045`, `m023`, `m039`, `m024`,
  `m047`) as of the current run; correctly distinguished `m039` (hostile,
  self-addressed) from `m041` (a legitimate preference note, same domain,
  same self-addressed shape) — sender domain is never treated as a trust
  signal.
- `x1` (legal-mail classifier): 4 correctly identified (`m048`, `m055`,
  `m015`, `m018`); a real false positive (`m019`, a venue booking that
  merely uses the word "contract") was caught and fixed.
- `x2` (thread summarizer): correctly extracted `m030`'s buried question
  ("approve the final pricing copy by the 12th") as the `t-launch`
  thread's open question, independently verified against the real
  message text.
- `x3` (meeting-conflict resolver): found 2 real conflicts (`m043`,
  `m038`), computed non-colliding 3-slot alternatives for each (never
  repeating a slot already offered to the other), and held both drafts
  for approval.
- `commitments.json` now has a genuine multi-message entry:
  `m040`, `source_message_ids: ["m040", "m038"]`, date correctly resolved
  to 2026-09-16 (the 18th minus the stated "two days before") — the
  cross-message commitment case Part 7 specifically asks for.

## Reliability findings from live testing (not design guesses)

1. **Batch size.** A ~12B local model reliably calls its tool for a single
   message per turn, but given several messages in one prompt it reliably
   fails to ever reach the tool call at all — it exhausts its output
   budget on chain-of-thought narration first. Fixed by processing one
   message per turn everywhere. Costs wall-clock time, not API cost — the
   right trade for a local model.
2. **Narrated-not-invoked tool calls.** Even one message per turn, the
   model sometimes writes out "Call disposeMessage(...)" as prose with
   entirely correct reasoning, but never issues the real function call.
   Every agent retries once with an explicit nudge, then falls back to a
   deterministic decision if the tool still wasn't called — so "no message
   left without a disposition" is an architectural guarantee, not a hope
   that the model complies. The fallback itself needed a second fix: it
   has to inspect its own failed narration for hostile language
   (`m024`, `m047`) or it silently loses a correct verdict the model
   already reached.
3. **A completion check watching only one of several possible stores.**
   `markTimeCommitment` writes to `commitments.json`, not `actions.json` —
   a retry loop that only checked the latter saw a correctly-recorded
   commitment as "no tool was called," retried pointlessly, and eventually
   fired the wrong fallback on top of an already-correct result. Fixed by
   checking every store a given tool call could have written to.
4. **The embedding model name was simply wrong.** `text-embedding-004`
   doesn't exist for this API key; `client.models.list()` was used to find
   the actual available models (`gemini-embedding-001`, etc.). This had
   been silently swallowed by a bare `except Exception: pass` for the
   entire build, degrading every cross-thread grounding case to a weaker
   keyword search with no visible symptom. A second, compounding bug in
   the keyword tokenizer (no punctuation stripping, so `"review?"` and
   `"review"` never matched) made that fallback itself unreliable too.

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
