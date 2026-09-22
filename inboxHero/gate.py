"""Part 4 -- the gate. Uniform policy (decided): every send/delete goes
through the same prompt-or-dry-run gate, no internal-vs-external exception.
Trade-off stated in the manifest: more prompts, but zero irreversible
action ever executes without either an explicit approval or a dry-run
showing it first.

outbox.write_message has exactly one caller in the whole codebase: this
module's approved branch. Nothing else may reach it.
"""
import outbox
import trace


def _describe(action_type, payload):
    if action_type == "send":
        return (
            f"SEND to {payload['to']} (cc: {payload.get('cc') or 'none'})\n"
            f"Subject: {payload['subject']}\n"
            f"Body:\n{payload['body']}\n"
            f"Cites: {payload.get('cited_message_ids')}"
        )
    if action_type == "delete":
        return f"DELETE message {payload['message_id']} -- reason: {payload.get('reason')}"
    raise ValueError(f"Unknown action_type '{action_type}'")


def request_approval(action_type, message_id, payload, dry_run=False):
    description = _describe(action_type, payload)

    if dry_run:
        print(f"[DRY RUN] Would {description}")
        outcome = "dry_run_shown"
        human_response = None
    else:
        print(f"Proposed action for {message_id}:\n{description}")
        answer = input("Approve? [y/n]: ").strip().lower()
        human_response = answer
        if answer == "y":
            if action_type == "send":
                outbox.write_message(
                    original_message_id=message_id,
                    to=payload["to"],
                    subject=payload["subject"],
                    body=payload["body"],
                    cited_message_ids=payload.get("cited_message_ids", []),
                    cc=payload.get("cc"),
                )
            outcome = "approved_executed"
        else:
            outcome = "rejected"

    trace.append_event(
        event="gate",
        message_id=message_id,
        source="gate",
        payload={
            "action_type": action_type,
            "payload_summary": description,
            "mode": "dry_run" if dry_run else "approval",
            "human_response": human_response,
            "outcome": outcome,
        },
    )
    return outcome
