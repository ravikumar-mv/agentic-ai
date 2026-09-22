"""Single entry point: python demo.py --cap R1 | --all | --reset [--dry-run] [--msg <id>]

Orchestration lives here, as plain Python -- not inside an ADK graph (see
plan.md 3k for why: rules.py and dashboard.py do no model reasoning, and
demo.py is the hand-rolled router between the rule engine, the two LLM
agents, and the dashboard render).
"""
import argparse
import json
import os

# Defense in depth: citation_checker.py sets this too (the earliest actual
# import point today), but set it here as well, at the top of the one real
# entry point, so it doesn't silently stop applying if that import order
# ever changes.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import action_agent
import actions_store
import config
import dashboard
import disposition_agent
import gate
import guard
import inbox_state
import legal_agent
import legal_store
import rules
import thread_agent
import thread_summary_store
import time_conflict_agent
import time_conflict_store
import trace


def run_disposition_pipeline():
    messages = inbox_state.undisposed_messages()
    resolved, unresolved = rules.apply_all(messages)

    for m, disposition, reason in resolved:
        inbox_state.update_message(m["id"], disposition=disposition, reason=reason, flagged=False)
        trace.append_event(
            event="decision", message_id=m["id"], source="rule",
            payload={"disposition": disposition, "reason": reason},
        )

    if unresolved:
        disposition_agent.run(unresolved)

    all_msgs = inbox_state.all_messages()
    undecided = [m for m in all_msgs if "disposition" not in m]
    print(f"Rule-handled (no model call): {len(resolved)}")
    print(f"Sent to Disposition Agent: {len(unresolved)}")
    print(f"Undecided at end of run: {len(undecided)}")
    return all_msgs


def run_action_pipeline():
    all_msgs = inbox_state.all_messages()
    actioned_ids = {a["message_id"] for a in actions_store.all_actions()}
    eligible = [
        m for m in all_msgs
        if m.get("disposition") in {"reply", "attention", "commitment"}
        and m["id"] not in actioned_ids
    ]
    if eligible:
        action_agent.run(eligible)
    print(f"Action Agent processed: {len(eligible)}")


def cap_r1_zero_the_inbox(args):
    inbox_state.ensure_state()
    run_disposition_pipeline()


def cap_r2_grounded_reply(args):
    if not args.msg:
        raise SystemExit("R2 requires --msg <message_id>")
    m = inbox_state.get_message(args.msg)
    if m is None:
        raise SystemExit(f"No such message: {args.msg}")

    real_disposition = m.get("disposition")
    if real_disposition != "reply":
        print(
            f"Note: {args.msg}'s real disposition is '{real_disposition}' "
            f"(reason: {m.get('reason')!r}). R2 demonstrates the grounding/"
            f"citation mechanism for this message's content on a LOCAL COPY "
            f"only -- it does not overwrite the Disposition Agent's actual "
            f"judgment in inbox_state.json."
        )

    # A local dict, not a write-back: inbox_state.json (and therefore Part 6/7
    # evidence) must not change just because this targeted demo ran.
    demo_message = {**m, "disposition": "reply"}
    action_agent.run([demo_message])
    result = next((a for a in actions_store.all_actions() if a["message_id"] == args.msg), None)
    print(json.dumps(result, indent=2))


def cap_r3_gate(args):
    run_action_pipeline()
    for entry in actions_store.pending_replies():
        gate.request_approval(
            "send", entry["message_id"],
            {
                "to": entry["to"], "cc": entry.get("cc"),
                "subject": entry["subject"], "body": entry["body"],
                "cited_message_ids": entry.get("cited_message_ids"),
            },
            dry_run=args.dry_run,
        )
    count = len(list(config.OUTBOX_DIR.glob("*.json"))) if config.OUTBOX_DIR.exists() else 0
    print(f"outbox/ writes: {count}")


def cap_r4_persistent_preference(args):
    """Two invocations, fresh process each time (plan.md 3h/3p).

    Schema-generic on purpose: no message id or preference key is
    hardcoded anywhere here. Which message states a preference, what key
    the Disposition Agent gives it, and which later message(s) it affects
    are all discovered at runtime, not known in advance by this function --
    the same code runs unmodified against a differently-populated inbox.
    """
    import memory_store

    prefs_before = memory_store.get_all()
    undisposed = inbox_state.undisposed_messages()

    if undisposed:
        # 1st invocation (or resuming one): run the ordinary disposition
        # pipeline over whatever isn't decided yet. Whichever message(s)
        # state a preference, if any, get captured as a side effect of
        # ordinary processing -- this function never names one.
        print(f"Running the disposition pipeline over {len(undisposed)} "
              f"undisposed message(s).")
        run_disposition_pipeline()
        prefs_after = memory_store.get_all()
        new_keys = sorted(set(prefs_after) - set(prefs_before))
        if new_keys:
            for key in new_keys:
                print(f"Captured this run: {key} = {prefs_after[key]}")
            print("Run this exact command again, as a fresh process, to see it applied.")
        else:
            print("No new standing preference was captured this run.")
        return

    # 2nd invocation: nothing left undisposed, so a prior invocation
    # already covered the backlog. Demonstrate application instead: run
    # the Action stage over whatever's eligible but not yet actioned, then
    # report which action(s), if any, reference a preference's value --
    # found generically by searching output text, not by checking specific
    # message ids.
    print("Nothing left undisposed. Preferences on file from a previous, "
          "fully-exited run:")
    print(memory_store.summary())
    run_action_pipeline()

    prefs = memory_store.get_all()
    applied = []
    for action in actions_store.all_actions():
        blob = json.dumps(action)
        if any(str(v) and str(v) in blob for v in prefs.values()):
            applied.append(action)

    if applied:
        print(f"{len(applied)} action(s) reference a standing preference's value:")
        print(json.dumps(applied, indent=2))
    else:
        print("No action this run referenced a standing preference's value.")


def cap_r5_refuse_injection(args):
    run_disposition_pipeline()
    flags = guard.run_summary_flags()
    if not flags:
        print("No hostile/phishing messages flagged this run.")
    for f in flags:
        print(f"FLAGGED: {f['message_id']} attempted: {f['attempted_action']} ({f['flag_reason']}); not done, left in place.")


def cap_r6_dashboard(args):
    data = dashboard.generate()
    print(f"Wrote dashboard.html and dashboard.json "
          f"(pending={len(data['pending'])}, flagged={len(data['flagged'])}, commitments={len(data['commitments'])})")


def cap_x1_legal(args):
    """Part 8, X1 -- Tier A. Lists every legal-related message. Runs on
    its own (Part 8.2) -- doesn't require R1 to have run first, but reuses
    R1's rule-resolved noise classification as a cheap skip when it's
    already there, instead of re-asking the model something a rule already
    settled."""
    already_processed = legal_store.processed_ids()
    candidates = [m for m in inbox_state.all_messages() if m["id"] not in already_processed]

    skipped, remaining = 0, []
    for m in candidates:
        reason = m.get("reason") or ""
        if m.get("disposition") == "archive" and reason.startswith("rule6:"):
            legal_store.set_flag(
                m["id"], False, "rule-resolved noise, assumed non-legal", source="rule-skip"
            )
            skipped += 1
        else:
            remaining.append(m)

    print(f"Skipped {skipped} already rule-resolved noise message(s) without a model call.")
    if remaining:
        print(f"Classifying {len(remaining)} message(s) via the Legal Agent...")
        legal_agent.run(remaining)

    legal = legal_store.legal_messages()
    print(f"\n{len(legal)} legal-related message(s):")
    for e in legal:
        m = inbox_state.get_message(e["message_id"])
        print(f"  {e['message_id']} | {m['subject'] if m else '?'} | {e['reason']}")


def cap_x2_thread_summary(args):
    """Part 8, X2 -- Tier B. Summarize a thread and extract its open
    question. Works on any thread id -- nothing here is dataset-specific."""
    if not args.thread:
        raise SystemExit("X2 requires --thread <thread_id>")

    thread_agent.run(args.thread)
    entry = thread_summary_store.get_summary(args.thread)
    print(json.dumps(entry, indent=2))


def cap_x3_time_conflicts(args):
    """Part 8, X3 -- Tier C. Detects a meeting-request conflict against a
    standing preference or existing commitment, proposes 3 non-colliding
    alternatives, and holds a drafted reply for approval. Only the
    Rule-6-noise skip survives here (verified real: disposition alone
    can't tell "meeting request" apart from other things needing
    attention -- e.g. m013 is a genuine reschedule request disposed
    "attention," not "commitment") -- every non-noise message goes
    through the Time Conflict Agent from scratch."""
    already_processed = time_conflict_store.processed_ids()
    candidates = [m for m in inbox_state.all_messages() if m["id"] not in already_processed]

    skipped, remaining = 0, []
    for m in candidates:
        reason = m.get("reason") or ""
        if m.get("disposition") == "archive" and reason.startswith("rule6:"):
            time_conflict_store.log_check(m["id"], is_time_request=False)
            skipped += 1
        else:
            remaining.append(m)

    print(f"Skipped {skipped} already rule-resolved noise message(s) without a model call.")
    if remaining:
        print(f"Checking {len(remaining)} message(s) via the Time Conflict Agent...")
        time_conflict_agent.run(remaining)

    conflicts = time_conflict_store.conflicts()
    print(f"\n{len(conflicts)} conflicting meeting request(s):")
    for e in conflicts:
        m = inbox_state.get_message(e["message_id"])
        slots = "; ".join(f"{s['date']} {s['start_time']}-{s['end_time']}" for s in e["proposed_slots"])
        print(f"  {e['message_id']} | {m['subject'] if m else '?'} | {e['conflict_reason']}")
        print(f"    proposed: {slots}")


CAPABILITIES = {
    "R1": cap_r1_zero_the_inbox,
    "R2": cap_r2_grounded_reply,
    "R3": cap_r3_gate,
    "R4": cap_r4_persistent_preference,
    "R5": cap_r5_refuse_injection,
    "R6": cap_r6_dashboard,
    "X1": cap_x1_legal,
    "X2": cap_x2_thread_summary,
    "X3": cap_x3_time_conflicts,
}


def run_all(args):
    run_disposition_pipeline()
    run_action_pipeline()
    cap_r3_gate(args)
    cap_r6_dashboard(args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap", choices=sorted(CAPABILITIES))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--msg")
    parser.add_argument("--thread")
    args = parser.parse_args()

    if args.reset:
        inbox_state.reset_state()
        print("inbox_state.json reset from inbox.json.")
        return

    inbox_state.ensure_state()

    if args.cap:
        with trace.set_active_cap(args.cap):
            CAPABILITIES[args.cap](args)
    elif args.all:
        run_all(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
