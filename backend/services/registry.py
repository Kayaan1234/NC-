"""The catalogue of trainable models that live under backend/services/.

A ModelSpec is the single source of truth for a model: where its binary is, which
datasets it accepts, and how far its parameters may be pushed. Two callers depend
on that:

  - routers/train.py validates an incoming TrainRequest against the spec, so an
    unknown dataset is rejected before a process is ever spawned.
  - GET /train/models serves the specs to the frontend, so the parameter form is
    generated from the same limits the server enforces. The UI can't drift out of
    sync with validation because there is only one definition.

Adding a rung means adding an entry here and a Makefile next to its source. Only
Step0 exists today; entries are not written ahead of the code they describe.
"""

from dataclasses import dataclass
from pathlib import Path

from backend.core.config import BASE_DIR


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    name: str
    description: str
    binary: Path
    # Built-in datasets the binary's --dataset flag accepts. Validated against,
    # never passed through: the process only ever sees a string from this tuple.
    datasets: tuple[str, ...]
    lr_range: tuple[float, float]
    epochs_max: int
    # Wall-clock kill switch, per-model because sizing differs by orders of
    # magnitude: Step0 is a 200-sample logistic regression that finishes in
    # milliseconds, while a later rung training a real network will legitimately
    # need minutes. This bounds a single run; it is NOT how the worker detects a
    # dead job (that's the heartbeat — see worker.reclaim_stale).
    timeout_seconds: int


MODELS: dict[str, ModelSpec] = {
    "step0": ModelSpec(
        model_id="step0",
        name="Single Neuron (Logistic Regression)",
        description=(
            "One neuron trained by gradient descent on binary cross-entropy. "
            "Separates linearly separable data; provably cannot solve XOR."
        ),
        binary=BASE_DIR / "services" / "Step0" / "nn",
        datasets=("tiny", "blobs", "xor"),
        # Upper bound is generous rather than principled: the sigmoid saturates
        # and the loss is clamped, so a large lr converges or stalls but never
        # blows up. It's here to keep the parameter form honest, not to protect
        # the process.
        lr_range=(0.0001, 10.0),
        epochs_max=5000,
        timeout_seconds=60,
    ),
}


def get_model(model_id: str) -> ModelSpec | None:
    """Look up a spec by id, or None if there's no such model.

    Callers must treat model_id as a key into this dict and nothing else — it
    arrives from a URL path, so it must never reach a filesystem path.
    """
    return MODELS.get(model_id)
