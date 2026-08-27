"""One event stream, two consumers (bridge-plan-v3.md §13).

Every pipeline event goes two places:

  - Langfuse, when LANGFUSE_PUBLIC_KEY/SECRET_KEY are configured — spans and
    generations with tokens, latency and cost attached. Unset keys mean every
    Langfuse call here is a clean no-op, so a missing account never blocks a
    run.
  - The job row's `progress` JSON column, which the frontend polls to narrate
    the run to the learner ("8 searches dispatched → 34 candidates → 11
    rejected: no license…").

Langfuse v4 is OTel-based: the old .trace()/.generation()/.span() methods do
not exist. The real API is start_as_current_observation(as_type=...) used as a
context manager, with usage/cost attached via update(). Anything beyond that
shape will AttributeError against langfuse==4.14.4.
"""

import logging
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone

from backend.core.config import settings

logger = logging.getLogger("backend.bridge.tracing")

_client = None
_client_initialised = False


def _langfuse():
    """The Langfuse client, or None when not configured. Lazy so the worker can
    boot (and the whole pipeline can run) with no Langfuse account."""
    global _client, _client_initialised
    if _client_initialised:
        return _client
    _client_initialised = True
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        logger.info("Langfuse keys not set; tracing to the progress column only")
        return None
    from langfuse import Langfuse

    _client = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )
    return _client


@contextmanager
def span(name: str, *, input: object = None, metadata: dict | None = None):
    """A traced span around one pipeline stage; no-op without Langfuse."""
    client = _langfuse()
    ctx = (
        client.start_as_current_observation(
            name=name, as_type="span", input=input, metadata=metadata
        )
        if client
        else nullcontext()
    )
    with ctx as observation:
        yield observation


@contextmanager
def generation(name: str, *, model: str, input: object = None):
    """A traced LLM/embedding call. The caller attaches usage via
    record_generation() on the yielded observation (None without Langfuse)."""
    client = _langfuse()
    ctx = (
        client.start_as_current_observation(
            name=name, as_type="generation", model=model, input=input
        )
        if client
        else nullcontext()
    )
    with ctx as observation:
        yield observation


def record_generation(observation, *, output: object, usage: dict, cost_usd: float) -> None:
    """Attach the outcome of a paid call to its observation. usage keys follow
    the Anthropic naming (input_tokens/output_tokens/...)."""
    if observation is None:
        return
    observation.update(
        output=output,
        usage_details={k: v for k, v in usage.items() if isinstance(v, int)},
        cost_details={"total": cost_usd},
    )


def flush() -> None:
    """Push buffered traces before a short-lived process (the CLI) exits. The
    long-lived worker doesn't need this — the client flushes in the background."""
    client = _langfuse()
    if client:
        client.flush()


class ProgressLog:
    """The learner-facing narrative: appends events to a BridgeJob's progress
    column. One instance per run; the CLI passes a job row too (seed jobs keep
    their narrative for the audit)."""

    def __init__(self, db, job) -> None:
        self._db = db
        self._job = job

    def event(self, text: str, *, stage: str | None = None) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # JSON columns don't track in-place mutation; reassign the list.
        self._job.progress = [*self._job.progress, {"t": now.isoformat(timespec="seconds"), "text": text}]
        if stage:
            self._job.stage = stage
        self._job.heartbeat_at = now
        self._db.commit()
        logger.info("job %s: %s", self._job.id, text)
