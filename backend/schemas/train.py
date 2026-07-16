from typing import Any

from pydantic import BaseModel, Field

from uuid import UUID

from datetime import datetime


class TrainRequest(BaseModel):
    """Parameters for one training run.

    The bounds here are a denial-of-service control, not input tidiness: every
    accepted request spawns a real process, so `epochs: 1_000_000_000` would be a
    free way to burn a worker. They are the absolute ceiling across all models —
    Field needs literal values, and a model's own (possibly tighter) limits live
    in its ModelSpec, which the router checks as well.

    `dataset` is validated in the router rather than here: the valid set depends
    on which model is being run, and the body can't see the model_id path param.
    """

    dataset: str = Field(min_length=1, max_length=50)
    lr: float = Field(default=0.5, gt=0, le=10)
    epochs: int = Field(default=500, ge=1, le=5000)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)

    model_config = {"str_strip_whitespace": True}


class ModelParamsSpec(BaseModel):
    """The bounds the UI should render a parameter form from."""

    datasets: list[str]
    lr_min: float
    lr_max: float
    lr_default: float
    epochs_max: int
    epochs_default: int


class ModelSpecResponse(BaseModel):
    model_id: str
    name: str
    description: str
    params: ModelParamsSpec

    # Pydantic v2 reserves the `model_` prefix for its own attributes and warns
    # on any field that starts with it. `model_id` is our domain language and
    # matches the column, so opt out of the protection rather than rename.
    model_config = {"protected_namespaces": ()}


class JobCreatedResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClearedJobsResponse(BaseModel):
    deleted: int


class JobStatusResponse(BaseModel):
    id: UUID
    model_id: str
    params: dict[str, Any]
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    # 0 = next to run. None unless the job is still queued.
    queue_position: int | None = None
    # Whether GET .../report will return a file rather than a 409.
    report_available: bool = False

    model_config = {"from_attributes": True, "protected_namespaces": ()}
