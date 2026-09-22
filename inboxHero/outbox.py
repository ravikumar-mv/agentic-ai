"""Part 4.3 -- sending writes to outbox/, one file per message, nowhere else.

Single-caller invariant by code discipline (decided): only gate.py's
approved branch imports/calls write_message. No token or runtime
enforcement added -- kept simple.

Delete is out of scope here -- see inbox_state.py / gate.py for that.
"""
import json
from datetime import datetime, timezone

import config


def write_message(original_message_id, to, subject, body, cited_message_ids, cc=None):
    config.OUTBOX_DIR.mkdir(exist_ok=True)
    payload = {
        "original_message_id": original_message_id,
        "to": to,
        "cc": cc or [],
        "subject": subject,
        "body": body,
        "cited_message_ids": cited_message_ids,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    path = config.OUTBOX_DIR / f"{original_message_id}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path
