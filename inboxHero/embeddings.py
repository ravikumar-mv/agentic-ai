"""Cross-thread grounding support (plan.md 3c). Reuses the *technique* from
Assignment 3 (asymmetric retrieval_document/retrieval_query embeddings,
cosine similarity) via the new unified google-genai SDK client (confirmed
signature: client.models.embed_content(model=, contents=[...], config=...)).
Plain NumPy cosine similarity -- FAISS is overkill at 100 messages.

Document vectors are embedded once and cached to disk so re-runs don't
re-hit the embedding API and burn into the free-tier rate limit.
"""
import json

import numpy as np
from google import genai
from google.genai import types

import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _embed(texts, task_type):
    client = _get_client()
    response = client.models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return [e.values for e in response.embeddings]


def _load_cache():
    if not config.EMBEDDINGS_CACHE_PATH.exists():
        return {}
    return json.loads(config.EMBEDDINGS_CACHE_PATH.read_text())


def _save_cache(cache):
    config.EMBEDDINGS_CACHE_PATH.write_text(json.dumps(cache))


def ensure_document_embeddings(messages):
    """Embeds every message body once (task_type=RETRIEVAL_DOCUMENT) and
    caches the vectors, keyed by message id. Returns {id: vector}."""
    cache = _load_cache()
    missing = [m for m in messages if m["id"] not in cache]
    if missing:
        texts = [f"{m.get('subject', '')}\n{m.get('body', '')}" for m in missing]
        vectors = _embed(texts, task_type="RETRIEVAL_DOCUMENT")
        for m, v in zip(missing, vectors):
            cache[m["id"]] = v
        _save_cache(cache)
    return cache


def embed_query(text):
    return _embed([text], task_type="RETRIEVAL_QUERY")[0]


def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def top_k_similar(query_text, messages, k=3, exclude_ids=None):
    """Returns [(message, score), ...] sorted by similarity, descending."""
    exclude_ids = exclude_ids or set()
    doc_vectors = ensure_document_embeddings(messages)
    query_vector = embed_query(query_text)

    scored = []
    for m in messages:
        if m["id"] in exclude_ids:
            continue
        vec = doc_vectors.get(m["id"])
        if vec is None:
            continue
        scored.append((m, cosine_similarity(query_vector, vec)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]
