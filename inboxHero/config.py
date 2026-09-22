import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# "text-embedding-004" doesn't exist for this API key -- verified via
# client.models.list() that the actually-available embedding models are
# gemini-embedding-001 / gemini-embedding-2-preview / gemini-embedding-2.
# This was silently swallowed by retrieval.py's try/except the whole
# build, degrading every cross-thread grounding attempt to keyword search
# without any visible symptom.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL") or "gemini-embedding-001"

# Embedding/retrieval only uses Google (above). Every other LLM call --
# both ADK agents, and citation_checker's Layer B verifier -- uses a local
# Ollama model via litellm's `ollama_chat/` provider, so no API key or
# network call is needed for triage/drafting/verification, only for
# embeddings.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL") or "gemma4:12b"
OLLAMA_API_BASE = os.environ.get("OLLAMA_API_BASE") or None
LOCAL_LLM_MODEL = f"ollama_chat/{OLLAMA_MODEL}"

INBOX_PATH = PROJECT_ROOT / "inbox.json"
INBOX_STATE_PATH = PROJECT_ROOT / "inbox_state.json"
PREFS_PATH = PROJECT_ROOT / "prefs.json"
ACTIONS_PATH = PROJECT_ROOT / "actions.json"
COMMITMENTS_PATH = PROJECT_ROOT / "commitments.json"
TRACE_PATH = PROJECT_ROOT / "trace.jsonl"
OUTBOX_DIR = PROJECT_ROOT / "outbox"
EMBEDDINGS_CACHE_PATH = PROJECT_ROOT / "embeddings_cache.json"
DASHBOARD_JSON_PATH = PROJECT_ROOT / "dashboard.json"
DASHBOARD_HTML_PATH = PROJECT_ROOT / "dashboard.html"
X1_LEGAL_PATH = PROJECT_ROOT / "x1_legal.json"
X2_THREAD_SUMMARIES_PATH = PROJECT_ROOT / "x2_thread_summaries.json"
X3_TIME_CONFLICTS_PATH = PROJECT_ROOT / "x3_time_conflicts.json"

# "escalate" retired (plan.md 3w): it was never produced by any rule, the
# Disposition Agent's instruction gave it no content-based meaning, and
# nothing downstream (Action Agent eligibility, dashboard panes) routed on
# it -- a message landing there was invisible forever. The disposeMessage
# fallback now targets "attention" instead, which IS wired into the
# Action Agent's eligible set and therefore actually surfaces.
DISPOSITIONS = {"reply", "archive", "attention", "defer", "commitment"}
