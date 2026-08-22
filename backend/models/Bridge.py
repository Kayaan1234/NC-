"""Tables for the Bridge feasibility engine (bridge-plan-v3.md).

Seven tables, one subsystem, so they live in one module:

  - bridge_jobs            the live-path queue (the table IS the queue, like
                           training_jobs)
  - bridge_verdicts        the stored verdict artefacts, keyed (topic_slug,
                           model_id) — the library is the `published` subset
  - bridge_candidate_pools scout results, keyed (topic_slug, modality) so every
                           step sharing a modality reuses one search
  - bridge_dataset_cards   chunked HF/Kaggle card text + pgvector embeddings,
                           the one RAG index (scout recall + nearest-domain)
  - bridge_query_plans     per-step query-plan template cache (§14.6) — keyed by
                           model_id alone because capability/modality are
                           properties of the spec, not the topic
  - bridge_llm_cache       exact-request response cache for LLM and embedding
                           calls, so a re-claimed job or a repeated local run
                           re-spends nothing
  - bridge_recent_searches the only per-user, per-step table: which topics this
                           student looked up, newest three, so a finished search
                           has somewhere to land
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base
from backend.models.TrainingJob import utcnow

# Dimension of the card-embedding index. Fixed in the schema, so changing the
# embedding model to one with a different dimension is a migration, not a config
# edit. 1024 is voyage-4-lite's default output.
EMBEDDING_DIM = 1024

# How many searched topics the finder remembers per student, per step. The
# eviction rule lives here alone so "up to three" is one edit, not a hunt through
# a router, a service and a stylesheet.
RECENT_SEARCH_LIMIT = 3


class BridgeJobStatus(str, PyEnum):
    """Same lifecycle as JobStatus; queued/running are the active states the
    partial unique index counts.

    CANCELLED is this queue's one addition, and it is not a synonym for FAILED:
    failure means the pipeline broke and the student should be told, while
    cancellation means they chose to stop waiting. Keeping them apart is what
    lets the UI stay quiet about the second one. The column is a plain String,
    so a new member costs no migration."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BridgeJobSource(str, PyEnum):
    LIVE = "live"    # a learner asked, a worker answers while they wait
    SEED = "seed"    # offline library seeding (CLI / Batch API); no user attached


class BridgeVerdictStatus(str, PyEnum):
    DRAFT = "draft"          # produced by a run; visible only to its requester
    PUBLISHED = "published"  # promoted into the public library after review


class BridgeJob(Base):
    """One requested feasibility run. Claimed by the bridge drain thread in the
    worker with SELECT ... FOR UPDATE SKIP LOCKED, exactly like training_jobs.
    """

    __tablename__ = "bridge_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    # Nullable: seed jobs come from the CLI, not a user. NULLs don't collide in
    # the partial unique index below, so seeding never occupies anyone's slot.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # The topic as typed, kept for display; topic_slug is the cache key
    # (services/bridge/slug.py) and the only form ever joined on.
    topic_input: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # Key into bridge registry BRIDGE_SPECS — same identifier discipline as
    # TrainingJob.model_id: not a path, never joined onto one.
    model_id: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default=BridgeJobSource.LIVE.value)

    # String holding the enum VALUE, never Enum() — see TrainingJob.status for
    # why (Enum persists the member NAME and silently defeats the partial index).
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BridgeJobStatus.QUEUED.value, index=True
    )
    # Which pipeline stage the run is in ("planning", "scouting", "gating",
    # "probing", ...). Coarser than progress below; useful for the reclaim log.
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Append-only narrative events [{"t": iso, "text": "..."}] — the learner-facing
    # half of the §13 event stream, polled by the frontend. TrainingJob
    # deliberately has no progress column; this table deliberately does.
    progress: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Running LLM+embedding spend for this run, in dollars. Checked against
    # BRIDGE_VERDICT_SPEND_CEILING_USD before each paid batch (§14.8), and summed
    # per day for the global cap.
    cost_usd: Mapped[object] = mapped_column(Numeric(8, 4), nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # One active bridge run per user, database-enforced (same rationale and
        # shape as uq_training_jobs_active_per_user). Independent of the training
        # slot: a user may train and bridge at once, but never two bridges.
        Index(
            "uq_bridge_jobs_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running')"),
            sqlite_where=text("status IN ('queued','running')"),
        ),
    )


class BridgeVerdict(Base):
    """One stored verdict artefact (§8), the cache and the library in one table.

    The artefact itself is a JSON document assembled from records; this row adds
    the key, the review state, and freshness metadata.
    """

    __tablename__ = "bridge_verdicts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    topic_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    model_id: Mapped[str] = mapped_column(String(50), nullable=False)
    topic_display: Mapped[str] = mapped_column(String(200), nullable=False)
    verdict: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BridgeVerdictStatus.DRAFT.value, index=True
    )
    # Set on an INHERITS_VERDICT step's artefact (step2 copies step1's assessment).
    inherited_from: Mapped[str | None] = mapped_column(String(50), nullable=True)
    produced_by_job: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bridge_jobs.id", ondelete="SET NULL"), nullable=True
    )
    # Dataset links rot. Stamped when the pipeline (or a revalidation sweep) last
    # confirmed the cited dataset still resolves.
    last_verified: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("topic_slug", "model_id", name="uq_bridge_verdicts_topic_model"),
    )


class BridgeCandidatePool(Base):
    """The scout output for one (topic, modality): candidates plus per-gate
    rejections. Keyed by modality, NOT by step — no step owns a search, so
    adding step6 beside step5 re-probes an existing pool instead of re-searching.
    """

    __tablename__ = "bridge_candidate_pools"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    topic_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    modality: Mapped[str] = mapped_column(String(20), nullable=False)
    pool: Mapped[dict] = mapped_column(JSON, nullable=False)
    last_verified: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("topic_slug", "modality", name="uq_bridge_pools_topic_modality"),
    )


class BridgeDatasetCard(Base):
    """One chunk of one dataset card, embedded for vector recall (§10).

    Serves two queries keyword search can't: scout recall for topics nobody
    phrased the way the learner did, and the nearest-domain fallback for topics
    with no data at all. With modality stored, the fallback redirects within the
    right modality.

    No ANN index on purpose: at this corpus size (thousands of chunks) pgvector's
    exact scan is fast and correct. Add an HNSW index in a migration when the
    corpus is large enough for exact search to hurt — not before.
    """

    __tablename__ = "bridge_dataset_cards"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False)       # "hf" | "kaggle"
    dataset_id: Mapped[str] = mapped_column(String(300), nullable=False)  # e.g. "user/name"
    modality: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[object] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    # Card facts captured at embed time (license, size, url). `metadata` is a
    # reserved name on declarative models, hence `meta`.
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source", "dataset_id", "chunk_index", name="uq_bridge_cards_chunk"),
    )


class BridgeQueryPlan(Base):
    """The planner's query-plan template for one step (§14.6). More stable than
    any verdict because capability and modality come from the BridgeSpec, not the
    topic — a fresh planner call is seeded from this instead of a blank page."""

    __tablename__ = "bridge_query_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    model_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    plan: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, server_default=func.now())


class BridgeLLMCache(Base):
    """Exact-request cache for paid API calls (LLM and embeddings).

    The key is a SHA-256 over (call_site, model, canonical request body), so a
    byte-identical call is served from here and costs nothing. This is what makes
    repeated local runs ~free, and it bounds the duplicate-spend cost of the
    queue's at-least-once delivery: a re-claimed job replays its calls as hits.
    """

    __tablename__ = "bridge_llm_cache"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    call_site: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    usage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())


class BridgeRecentSearch(Base):
    """The topics one student looked up for one step — newest RECENT_SEARCH_LIMIT.

    Everything else in this module is global: a verdict, a pool and a card are the
    same for everyone, which is what makes the cache worth having. This table is
    the exception, and it exists because a finished search previously had nowhere
    to land. A live run's verdict is stored DRAFT and the shelf serves PUBLISHED
    only, so a student's own result could never appear there without a curator
    running `cli promote`.

    Pruned on write rather than limited on read, so the table holds at most
    RECENT_SEARCH_LIMIT rows per (user, step) and "the fourth replaces the oldest"
    is a fact about storage, not about presentation.
    """

    __tablename__ = "bridge_recent_searches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    # NOT NULL, unlike BridgeJob.user_id. A seed run has no student behind it and
    # must never occupy a slot in anybody's list.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Key into BRIDGE_SPECS, same discipline as BridgeJob.model_id: a dict key,
    # never a path.
    model_id: Mapped[str] = mapped_column(String(50), nullable=False)
    # Joined against bridge_verdicts to draw the card. Stored slugified, so
    # "Wine  Quality!" and "wine quality" are one row, exactly as they are one
    # verdict.
    topic_slug: Mapped[str] = mapped_column(String(120), nullable=False)

    # Written explicitly from Python on insert AND on every bump, with no
    # server_default. The dev database runs Europe/London, so func.now() would be
    # BST while utcnow() is UTC — an hour apart in summer, zero in winter. This
    # column IS the eviction order, so a timestamp arriving from two different
    # clocks would silently reorder the list and drop the wrong row.
    searched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        # What turns a repeat search into a bump instead of a duplicate.
        UniqueConstraint(
            "user_id", "model_id", "topic_slug", name="uq_bridge_recent_user_model_topic"
        ),
        # Covers the only read: this user's rows for this step, newest first.
        Index("ix_bridge_recent_user_model_time", "user_id", "model_id", "searched_at"),
    )
