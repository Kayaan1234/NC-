"""Wire shapes for the bridge router. Mirrored by frontend/src/bridge.ts —
change one, change both."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BridgeSpecResponse(BaseModel):
    """One rung of the ladder as the UI sees it. Served for ALL ten steps —
    `available` says whether it can train today, which is exactly the
    MODELS ⊆ BRIDGE_SPECS containment made visible."""

    model_id: str
    ordinal: int
    display_name: str
    capability: str
    modality: str
    data_requirement: str
    has_probe: bool
    available: bool  # model_id in MODELS — derived, never hand-synced


class BridgeRunRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    model_id: str


class BridgeJobResponse(BaseModel):
    id: UUID
    topic_input: str
    topic_slug: str
    model_id: str
    status: str
    stage: str | None
    progress: list[dict]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    queue_position: int | None
    verdict_ready: bool
    # Derived at serve time, never stored: the run is queued and the queue is
    # not moving, which in practice means no worker is draining it. The UI uses
    # it to stop claiming the run is "starting up" and to back its poll off.
    stalled: bool = False


class BridgeRunAccepted(BaseModel):
    """POST /bridge/runs result: either a fresh job (202-style) or an instant
    library hit that cost nothing and created nothing."""

    library_hit: bool
    topic_slug: str
    model_id: str
    job: BridgeJobResponse | None = None


class BridgeVerdictResponse(BaseModel):
    topic_slug: str
    model_id: str
    topic_display: str
    status: str
    verdict: dict
    last_verified: datetime
    # Plain-language projections of fields inside `verdict`, computed at serve
    # time (services/bridge/plain.py). They live here rather than in the stored
    # artefact so better wording reaches every existing verdict for free.
    plain_fit: str | None = None
    plain_license: str | None = None
    plain_difficulty: str | None = None
    plain_done: str | None = None
    step_name: str | None = None


class BridgeLibraryEntry(BaseModel):
    topic_slug: str
    topic_display: str
    model_id: str
    verdict_value: str
    summary: str
    # Enough to render a card without fetching the whole artefact.
    dataset_title: str | None = None
    rows: int | None = None
    # False for a cached-but-unreviewed topic, which is still instant to open.
    published: bool = False


class BridgeRecentEntry(BridgeLibraryEntry):
    """One of the student's own remembered searches: a library card plus when
    they last looked it up. Subclassed rather than adding the field upstream so
    /library and /topics, which have no such timestamp, do not grow a null one."""

    searched_at: datetime


class BridgeRecentLookup(BaseModel):
    """POST /bridge/recent result: whether a verdict is already on the shelf for
    this topic, and the slug it normalised to.

    `exists: false` means nothing was recorded — there would be no verdict for the
    card to open. The caller's next move is POST /bridge/runs, which is the
    endpoint that spends money and carries the hourly limit.
    """

    topic_slug: str
    exists: bool
