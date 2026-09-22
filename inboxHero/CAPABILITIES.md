# CAPABILITIES.md

**Student:** Ravikumar MV, cert-aai-2026-06-0043
**Repository:** https://github.com/ravikumar-mv/agentic-ai (project lives in the `inboxHero/` subfolder)

Run everything through one entry point:

```
python demo.py --reset          # bootstrap inbox_state.json from inbox.json
python demo.py --cap R1         # one capability
python demo.py --all            # the required six, in order
```

`--cap R4` and Part 5's demo specifically need to be run **twice**, as two
separate process invocations — see R4 below.

---

## The system, in one paragraph

`rules.py` disposes of unambiguous noise (40 of 100 messages) with plain
substring checks, no model call. Everything else goes to a Disposition
Agent (ADK `LlmAgent`, one message per turn), which also carries all Part 6
hostile/phishing judgment — no regex detector, by design. Messages disposed
`reply`/`attention`/`commitment` then go to an Action Agent, which drafts
replies (citation-checked against the mail store before anything is
persisted), marks attention items, or records commitments (checked for
conflicts against standing preferences and each other). Three Part 8
capabilities layer on top: a legal-mail classifier, a thread summarizer,
and a meeting-conflict resolver that plans alternatives in deterministic
Python and only uses the model for extraction and drafting. Orchestration
between all of these is plain Python in `demo.py` — there is no ADK
Workflow/graph object anywhere in this system; every stage is a function
call. State that must outlive a run (preferences, every capability's own
findings) lives in small JSON files on disk, `inbox.json` itself is never
mutated, and `trace.jsonl` is an append-only audit log.

## Design choices you were asked to state

- **Framework: Google ADK**, specifically `LlmAgent` + the `LiteLlm` model
  wrapper (for routing to a local Ollama model) — used for every agent in
  the system, required six and Part 8 capabilities alike. Deliberately
  **not** used: ADK 2.0's `Workflow`/graph API. It exists and was inspected
  directly in the installed package, but its actual Python surface (private
  submodules, pydantic edge/state-schema validation, no accessible worked
  example) wasn't something I could get right on the first pass with
  confidence, so orchestration is hand-rolled Python in `demo.py` instead.
  What ADK gave for free: automatic function-calling from plain Python
  functions, and the `LiteLlm` wrapper that made switching every agent from
  a hosted model to a local one a one-line change per agent. What it didn't
  give: the approval gate, the citation checker, the hostile-content
  enforcement layer, the retry/fallback logic for a model that sometimes
  narrates a tool call instead of invoking it — all hand-rolled, and all of
  it turned out to matter more than the framework choice itself.
- **Model routing.** Every LLM call except embeddings uses a **local**
  Ollama model (`gemma4:12b`, via `litellm`'s `ollama_chat/` provider) — no
  API key, no rate limit, no per-call cost. Only `embeddings.py`/
  `retrieval.py` use Google's `text-embedding-004`, since there's no local
  equivalent worth standing up for this. This is a deliberate trade of
  wall-clock time for zero cost and zero external dependency on anything
  but embeddings.
- **Retrieval: thread-walk primary**, since the inbox already carries
  `thread_id` — cheaper and exact for the common "answer is earlier in
  this exact conversation" case. Embeddings (reusing Assignment 3's
  asymmetric `retrieval_document`/`retrieval_query` technique, cached to
  disk) are the fallback for cross-thread grounding; keyword search is the
  final fallback if the embedding call itself is unavailable.
- **Reversible vs irreversible.** `send` and `delete` are irreversible and
  gated; `draft`, `archive`, `defer`, `attention`, and `commitment` are
  reversible and run without a prompt. Deleting is irreversible in this
  design because the mock store has no trash. **Disclosed gap:** nothing
  in the required six or the three Part 8 capabilities currently triggers
  an actual delete — the gate mechanism supports it (`gate.py` and
  `guard.assert_not_deletable`), but no built capability exercises that
  path. Judged as it is: a real gap, not something to paper over.
- **Where the gate sits.** `outbox.write_message` has exactly one caller in
  the entire codebase — `gate.py`'s approved branch. Gating policy is
  **uniform**: every send goes through the same prompt-or-`--dry-run` gate,
  no internal-vs-external exception. Trade-off: more prompts, in exchange
  for zero irreversible action ever executing without either an explicit
  approval or a dry-run showing it first.
- **Escalation line for hostile content.** Detection is 100% the
  Disposition Agent's judgment — no regex primary detector, per an
  explicit design decision partway through the build. `guard.py`'s job is
  not detection but enforcement: framing raw message content as untrusted
  data in every prompt, logging refusals, and making sure a flagged
  message's *current* state — not a stale entry from an earlier, corrected
  run — is what the Flagged pane and refusal reports actually reflect.
- **A finding worth stating plainly, since it shaped most of the later
  build:** a ~12B local model reliably handles exactly one required tool
  call per turn, and reliably degrades once more than one is asked for in
  the same turn — sometimes by exhausting its output budget narrating
  before ever calling the tool, sometimes by describing a call correctly
  in prose without actually issuing it. Every agent in this system reflects
  that: one message per turn everywhere, a retry with an explicit nudge,
  and a deterministic fallback if the tool still wasn't called — so "no
  message left without a disposition" (Part 2.2) and "no message flagged
  incorrectly stays flagged" hold as architectural guarantees, not as a
  hope that the model complies. The one deliberate exception (X3's Time
  Conflict Agent, two dependent tool calls in one turn) was treated as a
  genuine experiment, not an assumption — tested live before being trusted,
  and it held up.
- **Preference key naming.** `capturePreference`'s key is free text the
  model chooses, not an enforced enum — anchored with a couple of concrete
  worked examples (`cc_on_legal_mail`, `no_meetings_before`) in the
  Disposition Agent's instruction so the same *kind* of preference reliably
  gets the same key across runs, which is what lets `commitments.py`'s
  conflict check and X3's slot search both find it later.

## Capabilities

| id | name | tier | one-line claim |
|----|------|------|----------------|
| R1 | Zero the inbox | B | every message gets one disposition + reason, none left |
| R2 | Grounded reply | B | drafts cite the earlier message they used, verified not hallucinated |
| R3 | Gate the irreversible | C | no send without approval or --dry-run; outbox has one caller |
| R4 | Persistent preference | C | a preference stated in a message survives a restart, schema-generic |
| R5 | Refuse embedded instructions | C | detects, refuses, flags, reports injections and phishing -- pure LLM judgment |
| R6 | Dashboard | C | three panes, commitments cited, conflicts surfaced, no duplicate outcomes |
| X1 | Legal-related mail | A | one classification per message, one filtered list, judged by substance |
| X2 | Thread summary and open question | B | reasons across a whole thread in one pass, cites its source |
| X3 | Meeting-conflict resolver | C | plans alternatives deterministically, drafts and gates the reply |

The exact command, observable outcome and evidence for each is in
`capabilities.json`. That file is the machine-readable version and is what
a marking script reads; this file is for a human. Keep the two in step.

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
