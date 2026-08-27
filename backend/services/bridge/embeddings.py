"""Voyage AI embeddings for the dataset-card index (bridge-plan-v3.md §10).

Same discipline as llm.py: per-text caching in bridge_llm_cache (so re-embedding
a card costs nothing), spend charged to the run's ledger, batches capped at the
SDK's 128-text limit. The client gets its key explicitly from settings
(VOYAGER_API_KEY — the name already provisioned in backend/.env), so the SDK's
own VOYAGE_API_KEY env lookup never runs.

Worker-only: the web image ships no voyageai SDK.
"""

import hashlib
import logging

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.services.bridge import tracing
from backend.services.bridge.llm import SpendLedger, cache_get, cache_put, cost_from_usage

logger = logging.getLogger("backend.bridge.embeddings")

EMBED_MODEL = "voyage-4-lite"
_BATCH = 128

_client = None


def _voyage():
    global _client
    if _client is None:
        import voyageai

        if not settings.VOYAGER_API_KEY:
            raise RuntimeError("VOYAGER_API_KEY is not set — the bridge pipeline cannot run")
        _client = voyageai.Client(api_key=settings.VOYAGER_API_KEY)
    return _client


def _key(text: str, input_type: str) -> str:
    return hashlib.sha256(f"embedding|{EMBED_MODEL}|{input_type}|{text}".encode()).hexdigest()


def embed_texts(
    db: Session,
    ledger: SpendLedger,
    texts: list[str],
    *,
    input_type: str,  # "document" for cards going into the index, "query" for lookups
) -> list[list[float]]:
    """Embed texts, serving repeats from the cache and batching the rest."""
    vectors: list[list[float] | None] = [None] * len(texts)
    misses: list[int] = []
    for i, text in enumerate(texts):
        cached = cache_get(db, _key(text, input_type))
        if cached is not None:
            vectors[i] = cached.response["embedding"]
        else:
            misses.append(i)

    for start in range(0, len(misses), _BATCH):
        batch = misses[start : start + _BATCH]
        ledger.check("embedding batch")
        batch_texts = [texts[i] for i in batch]
        with tracing.generation("embedding", model=EMBED_MODEL,
                                input=f"{len(batch_texts)} texts") as observation:
            result = _voyage().embed(batch_texts, model=EMBED_MODEL, input_type=input_type)
            usage = {"input_tokens": result.total_tokens, "output_tokens": 0}
            cost = cost_from_usage(EMBED_MODEL, usage)
            ledger.charge(cost)
            tracing.record_generation(
                observation, output=f"{len(batch_texts)} vectors", usage=usage, cost_usd=cost
            )
        for i, embedding in zip(batch, result.embeddings):
            vectors[i] = list(embedding)
            cache_put(db, _key(texts[i], input_type), "embedding", EMBED_MODEL,
                      {"embedding": list(embedding)}, {})
        logger.info("embedded %d texts, %d tokens, $%.5f",
                    len(batch_texts), result.total_tokens, cost)

    return vectors  # type: ignore[return-value]
