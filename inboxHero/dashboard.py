"""Part 7 -- the dashboard (plan.md 3i). Reproducible from a run: reads the
three stores and writes dashboard.json + a static dashboard.html. No JS
required -- <details>/<summary> handles click-to-expand.
"""
import calendar as calendar_module
import html
import json
from datetime import datetime

import actions_store
import commitments
import config
import guard


def build_data():
    # commitments.json is the authoritative record for any message that has
    # one -- its own conflict flag is how that message's "needs a decision"
    # status is already surfaced (in the Commitments tab). An "attention"
    # entry in actions.json for the SAME message id is either a stale
    # fallback artifact or a redundant second tool call, never a second
    # legitimate outcome -- verified real for m043/m086/m061/m095, all of
    # which had a genuine commitments.json entry AND a stray attention
    # entry. Two JSON stores can each be individually correct and still
    # disagree about the same message; this is the precedence rule between
    # them, not a "read logs instead of JSON" bug.
    committed_ids = {c["message_id"] for c in commitments.all_commitments()}

    pending = [
        {
            "message_id": e["message_id"],
            "kind": "attention",
            "proposed_action": e.get("action_needed"),
            "why": e.get("decided_from"),
        }
        for e in actions_store.all_actions("attention")
        if e["message_id"] not in committed_ids
    ] + [
        {
            "message_id": e["message_id"],
            "kind": "reply",
            "proposed_action": f"Send to {e.get('to')}: {e.get('subject')}\n{e.get('body')}",
            "why": e.get("summary"),
        }
        for e in actions_store.pending_replies()
    ]

    flagged = guard.run_summary_flags()

    commitment_entries = sorted(
        commitments.all_commitments(), key=lambda c: (c.get("date") or "", c.get("start_time") or "")
    )

    return {"pending": pending, "flagged": flagged, "commitments": commitment_entries}


def _row_pending(item):
    return (
        f"<tr><td>{html.escape(item['message_id'])}</td>"
        f"<td>{html.escape(item['kind'])}</td>"
        f"<td><details><summary>{html.escape((item['proposed_action'] or '')[:60])}...</summary>"
        f"<pre>{html.escape(item['proposed_action'] or '')}</pre></details></td>"
        f"<td>{html.escape(item['why'] or '')}</td></tr>"
    )


def _row_flagged(item):
    return (
        f"<tr><td>{html.escape(item['message_id'])}</td>"
        f"<td>{html.escape(item['flag_reason'] or '')}</td>"
        f"<td>{html.escape(item['attempted_action'] or '')}</td>"
        f"<td>not complied with; message left in place, not deleted</td></tr>"
    )


def _entry_html(item):
    css = "conflict" if item.get("conflict") else "ok"
    time_str = html.escape(item.get("start_time") or "")
    title = html.escape(item.get("title") or "(untitled)")
    detail = (
        f"message: {item['message_id']}, "
        f"source: {item.get('source_message_ids')}, "
        f"conflict_with: {item.get('conflict_with')}, "
        f"reason: {item.get('conflict_reason')}"
    )
    label = f"{time_str} {title}".strip()
    return (
        f"<details class='entry {css}'><summary>{label}</summary>"
        f"<pre>{html.escape(detail)}</pre></details>"
    )


def _render_month_grid(year, month, day_entries):
    """day_entries: {day-of-month: [commitment entry, ...]}. Built with
    the stdlib calendar module -- no date range hardcoded, works for
    whatever month(s) the actual commitments fall in."""
    cal = calendar_module.Calendar(firstweekday=6)  # weeks start Sunday
    headers = "".join(f"<th>{d}</th>" for d in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])

    rows = []
    for week in cal.monthdayscalendar(year, month):
        cells = []
        for day in week:
            if day == 0:
                cells.append("<td class='empty'></td>")
                continue
            entries_html = "".join(_entry_html(e) for e in day_entries.get(day, []))
            cells.append(f"<td><div class='daynum'>{day}</div>{entries_html}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    month_label = f"{calendar_module.month_name[month]} {year}"
    return f"<h3>{month_label}</h3><table class='calendar-grid'><tr>{headers}</tr>{''.join(rows)}</table>"


def render_commitments_calendar(commitment_entries):
    """Part 7 asks for the Commitments pane to be shown as a calendar, not
    a list -- one real month grid per month the commitments actually fall
    in, generic over whatever date range that turns out to be."""
    by_month = {}
    for e in commitment_entries:
        if not e.get("date"):
            continue
        dt = datetime.strptime(e["date"], "%Y-%m-%d")
        by_month.setdefault((dt.year, dt.month), {}).setdefault(dt.day, []).append(e)

    if not by_month:
        return "<p>No commitments.</p>"

    return "\n".join(_render_month_grid(y, m, by_month[(y, m)]) for y, m in sorted(by_month))


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>inboxHero Dashboard</title>
<style>
  body {{ font-family: system-ui, Arial, sans-serif; margin: 24px; color: #1a1a1a; }}
  h1 {{ margin-bottom: 4px; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; }}
  .tab-btn {{ padding: 8px 16px; border: 1px solid #ccc; background: #f5f5f5; cursor: pointer; border-radius: 6px; }}
  .tab-btn.active {{ background: #2b5fad; color: white; }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; }}
  th {{ background: #f0f0f0; }}
  tr.conflict {{ background: #ffe0e0; }}
  pre {{ white-space: pre-wrap; margin: 4px 0; }}
  .calendar-grid {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
  .calendar-grid th {{ background: #f0f0f0; padding: 6px; font-size: 12px; }}
  .calendar-grid td {{ border: 1px solid #ddd; vertical-align: top; padding: 4px; width: 14.28%; height: 90px; font-size: 12px; }}
  .calendar-grid td.empty {{ background: #fafafa; }}
  .daynum {{ font-weight: bold; color: #555; margin-bottom: 2px; }}
  .entry {{ display: block; margin: 2px 0; border-radius: 3px; padding: 2px 4px; font-size: 11px; }}
  .entry summary {{ cursor: pointer; }}
  .entry.ok {{ background: #e8f0fe; }}
  .entry.conflict {{ background: #ffb3b3; color: #7a0000; font-weight: bold; }}
</style>
</head>
<body>
<h1>inboxHero -- Run Dashboard</h1>
<div class="tabs">
  <div class="tab-btn active" onclick="showTab('pending')">Pending Actions ({pending_count})</div>
  <div class="tab-btn" onclick="showTab('flagged')">Flagged ({flagged_count})</div>
  <div class="tab-btn" onclick="showTab('commitments')">Commitments ({commitments_count})</div>
</div>

<div id="pending" class="tab-panel active">
  <table>
    <tr><th>Message</th><th>Kind</th><th>Proposed action</th><th>Why it needs a human</th></tr>
    {pending_rows}
  </table>
</div>

<div id="flagged" class="tab-panel">
  <table>
    <tr><th>Message</th><th>Why flagged</th><th>What was attempted</th><th>What the system did</th></tr>
    {flagged_rows}
  </table>
</div>

<div id="commitments" class="tab-panel">
  {commitments_calendar}
</div>

<script>
function showTab(id) {{
  document.querySelectorAll('.tab-panel').forEach(function(p) {{ p.classList.remove('active'); }});
  document.querySelectorAll('.tab-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  document.getElementById(id).classList.add('active');
  event.target.classList.add('active');
}}
</script>
</body>
</html>
"""


def render_html(data):
    return HTML_TEMPLATE.format(
        pending_count=len(data["pending"]),
        flagged_count=len(data["flagged"]),
        commitments_count=len(data["commitments"]),
        pending_rows="\n".join(_row_pending(i) for i in data["pending"]) or "<tr><td colspan=4>none</td></tr>",
        flagged_rows="\n".join(_row_flagged(i) for i in data["flagged"]) or "<tr><td colspan=4>none</td></tr>",
        commitments_calendar=render_commitments_calendar(data["commitments"]),
    )


def generate():
    data = build_data()
    config.DASHBOARD_JSON_PATH.write_text(json.dumps(data, indent=2) + "\n")
    config.DASHBOARD_HTML_PATH.write_text(render_html(data))
    return data
