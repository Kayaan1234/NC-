"""The one RAG index: dataset cards on pgvector (bridge-plan-v3.md §10).

Two jobs keyword search can't do:

  - scout recall: "morris dancing" fails on HF not because no data exists but
    because nobody wrote that phrase; vector similarity over card text runs
    ALONGSIDE keyword search, never instead of it
  - nearest-domain fallback: when a topic truly has nothing, the honest redirect
    is across topics within the same modality — that's a KNN query

The index grows organically: every candidate a scout returns is embedded and
upserted here, so recall gets better with every run. No ANN index — exact scan
is correct and fast at this corpus size (see models/Bridge.py).
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.Bridge import BridgeDatasetCard
from backend.services.bridge.embeddings import embed_texts
from backend.services.bridge.llm import SpendLedger
from backend.services.bridge.registry import Modality

logger = logging.getLogger("backend.bridge.card_index")


def _card_text(candidate: dict) -> str:
    return f"{candidate['title']}\n{candidate.get('description') or ''}".strip()[:2000]


def upsert_cards(db: Session, ledger: SpendLedger, candidates: list[dict],
                 modality: Modality) -> None:
    """Embed and store any candidate cards not already in the index."""
    new: list[dict] = []
    batch_keys: set[tuple] = set()
    for candidate in candidates:
        key = (candidate["source"], candidate["dataset_id"])
        if key in batch_keys:  # callers can legitimately pass repeats
            continue
        exists = db.execute(
            select(BridgeDatasetCard.id).where(
                BridgeDatasetCard.source == candidate["source"],
                BridgeDatasetCard.dataset_id == candidate["dataset_id"],
                BridgeDatasetCard.chunk_index == 0,
            )
        ).first()
        if exists is None:
            batch_keys.add(key)
            new.append(candidate)
    if not new:
        return

    vectors = embed_texts(db, ledger, [_card_text(c) for c in new], input_type="document")
    for candidate, vector in zip(new, vectors):
        db.add(BridgeDatasetCard(
            source=candidate["source"],
            dataset_id=candidate["dataset_id"],
            modality=modality.value,
            chunk_index=0,
            chunk_text=_card_text(candidate),
            embedding=vector,
            meta=candidate,
        ))
    db.commit()
    logger.info("indexed %d new cards", len(new))


def vector_recall(db: Session, ledger: SpendLedger, query_text: str,
                  modality: Modality, limit: int = 8) -> list[dict]:
    """Candidates similar to the topic by card meaning, within the modality."""
    [query_vector] = embed_texts(db, ledger, [query_text], input_type="query")
    rows = db.execute(
        select(BridgeDatasetCard)
        .where(BridgeDatasetCard.modality == modality.value)
        .order_by(BridgeDatasetCard.embedding.cosine_distance(query_vector))
        .limit(limit)
    ).scalars().all()
    recalled = []
    for row in rows:
        candidate = dict(row.meta)
        candidate["via"] = "vector_recall"
        recalled.append(candidate)
    return recalled


def nearest_domain(db: Session, ledger: SpendLedger, topic_text: str,
                   modality: Modality, limit: int = 3) -> list[dict]:
    """The §8 point-7 fallback: nothing for this topic, but here is the nearest
    usable thing BY SHAPE — constrained to the step's modality, which is what
    makes the redirect useful rather than random."""
    [query_vector] = embed_texts(db, ledger, [topic_text], input_type="query")
    rows = db.execute(
        select(
            BridgeDatasetCard,
            BridgeDatasetCard.embedding.cosine_distance(query_vector).label("distance"),
        )
        .where(BridgeDatasetCard.modality == modality.value)
        .order_by("distance")
        .limit(limit)
    ).all()
    return [
        {
            "source": row.BridgeDatasetCard.source,
            "dataset_id": row.BridgeDatasetCard.dataset_id,
            "url": row.BridgeDatasetCard.meta.get("url"),
            "title": row.BridgeDatasetCard.meta.get("title"),
            "similarity": round(1.0 - float(row.distance), 3),
        }
        for row in rows
    ]
