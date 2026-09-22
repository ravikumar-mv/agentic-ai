"""Shared helper for running one ADK agent turn synchronously. Each call
gets its own fresh in-memory session -- these are independent batch
classification turns, not a continuous conversation.
"""
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


def run_agent_turn(agent, prompt, app_name="inboxHero", user_id="sam"):
    session_id = uuid.uuid4().hex
    session_service = InMemorySessionService()
    session_service.create_session_sync(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    runner = Runner(app_name=app_name, agent=agent, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    final_text = []
    for event in runner.run(user_id=user_id, session_id=session_id, new_message=message):
        content = getattr(event, "content", None)
        if content and content.parts:
            for part in content.parts:
                if getattr(part, "text", None):
                    final_text.append(part.text)
    return "\n".join(final_text)
