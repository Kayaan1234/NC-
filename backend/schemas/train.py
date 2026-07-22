from typing import Any

from pydantic import BaseModel

from uuid import UUID

from datetime import datetime


# There is deliberately NO request schema for a training run. The parameters a
# model accepts are per-model (Step0 takes four flags, Step1 takes eight), so the
# router takes a raw dict and hands it to services/params.validate, which checks
# it against that model's ParamSpec descriptors — and, crucially, against the
# absolute HARD_LIMITS ceiling that lives there. A fixed pydantic model could
# only express the intersection of every model's parameters.


class ParamSpecResponse(BaseModel):
    """One parameter, as the UI needs to render an input for it.

    Mirrors services/registry.ParamSpec field for field (minus `flag`, which is a
    server-side detail the client has no use for). The form is generated from
    this, so it cannot offer a value the server would reject.
    """

    name: str
    kind: str                       # "choice" | "float" | "int" | "int_list"
    label: str
    default: Any
    choices: list[str] = []
    minimum: float | None = None
    maximum: float | None = None
    max_items: int | None = None
    item_min: int | None = None
    item_max: int | None = None
    help: str = ""


class ResultFieldResponse(BaseModel):
    """One key of the run's RESULT line worth showing, and how to format it."""

    key: str
    label: str
    format: str                     # "percent" | "number" | "text"


class ModelSpecResponse(BaseModel):
    model_id: str
    name: str
    description: str
    params: list[ParamSpecResponse]
    result_fields: list[ResultFieldResponse]
    # {dataset: {param_name: value}} — what the form should snap the other fields
    # to when the dataset selection changes. Advisory: the server validates
    # whatever finally arrives regardless.
    dataset_defaults: dict[str, dict[str, Any]] = {}

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
