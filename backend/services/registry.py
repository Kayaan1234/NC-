"""The catalogue of trainable models that live under backend/services/.

A ModelSpec is the single source of truth for a model: where its binary is, which
parameters it accepts, how far each may be pushed, and which numbers from its
RESULT line are worth showing. Four callers depend on that, and none of them
knows the name of any particular model:

  - services/params.py validates an incoming request body against spec.params, so
    an unknown dataset or an out-of-range epoch count is rejected before a process
    is ever spawned.
  - services/runner.py builds the command line by walking spec.params in order —
    there is no per-model argv code anywhere.
  - GET /train/models serves the specs to the frontend, so the parameter form is
    *generated* from the same limits the server enforces. The UI can't drift out
    of sync with validation because there is only one definition.
  - The frontend job list renders spec.result_fields, so a new model's numbers
    show up without touching React.

Adding a rung means adding an entry here, a Makefile next to its source, and two
lines in the Dockerfile. See ADDING_A_MODEL.md for the full checklist.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.config import BASE_DIR

# The four parameter shapes a driver flag can take. Anything a model needs that
# doesn't fit one of these is a signal to add a kind here (and one renderer in
# TrainingModel.tsx), not to special-case the model.
KIND_CHOICE = "choice"      # a fixed set of strings -> <select>
KIND_FLOAT = "float"        # bounded real          -> <input type=number step=any>
KIND_INT = "int"            # bounded integer       -> <input type=number>
KIND_INT_LIST = "int_list"  # "64,32"               -> <input type=text>


@dataclass(frozen=True)
class ParamSpec:
    """One command-line parameter of a model.

    Deliberately ONE flat dataclass rather than a class per kind: it serialises to
    a single JSON shape for the UI, and the validator/argv builder can switch on
    `kind` instead of isinstance-dispatching. The fields a kind doesn't use stay
    None and are simply ignored.
    """

    name: str                       # request-body key, and the key in job.params
    flag: str                       # CLI flag, e.g. "--lr"
    kind: str                       # one of the KIND_* constants above
    label: str                      # what the form calls it
    default: Any
    choices: tuple[str, ...] = ()   # KIND_CHOICE
    minimum: float | None = None    # KIND_FLOAT / KIND_INT
    maximum: float | None = None
    max_items: int | None = None    # KIND_INT_LIST
    item_min: int | None = None
    item_max: int | None = None
    help: str = ""


@dataclass(frozen=True)
class ResultField:
    """One key of the driver's RESULT line, and how to render it.

    `format` is a hint for the UI only — the value is whatever the binary printed.
    "percent" means the binary emits a 0..1 fraction and the UI multiplies by 100.
    """

    key: str
    label: str
    format: str = "number"          # "percent" | "number" | "text"


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    name: str
    description: str
    binary: Path
    # ORDER MATTERS: runner.build_argv emits the flags in exactly this sequence.
    params: tuple[ParamSpec, ...]
    result_fields: tuple[ResultField, ...]
    # Wall-clock kill switch, per-model because sizing differs by orders of
    # magnitude: Step0 is a 200-sample logistic regression that finishes in
    # milliseconds, while Step1 on MNIST legitimately needs seconds to minutes.
    # This bounds a single run; it is NOT how the worker detects a dead job
    # (that's the heartbeat — see worker.reclaim_stale).
    timeout_seconds: int = 60
    # {dataset: {param_name: value}} — per-dataset default overrides the form
    # applies when the dataset dropdown changes. Purely a UI affordance: the
    # server validates whatever finally arrives against `params` either way.
    dataset_defaults: dict[str, dict[str, Any]] = field(default_factory=dict)


# --- constructors -------------------------------------------------------------
# Sugar so a MODELS entry reads like a parameter list rather than a wall of
# keyword arguments. Each one just fills the fields its kind uses.

def choice(name: str, flag: str, choices: tuple[str, ...], default: str,
           label: str, help: str = "") -> ParamSpec:
    return ParamSpec(name=name, flag=flag, kind=KIND_CHOICE, label=label,
                     default=default, choices=choices, help=help)


def number(name: str, flag: str, minimum: float, maximum: float, default: float,
           label: str, help: str = "") -> ParamSpec:
    return ParamSpec(name=name, flag=flag, kind=KIND_FLOAT, label=label,
                     default=default, minimum=minimum, maximum=maximum, help=help)


def integer(name: str, flag: str, minimum: int, maximum: int, default: int,
            label: str, help: str = "") -> ParamSpec:
    return ParamSpec(name=name, flag=flag, kind=KIND_INT, label=label,
                     default=default, minimum=minimum, maximum=maximum, help=help)


def int_list(name: str, flag: str, max_items: int, item_min: int, item_max: int,
             default: str, label: str, help: str = "") -> ParamSpec:
    return ParamSpec(name=name, flag=flag, kind=KIND_INT_LIST, label=label,
                     default=default, max_items=max_items, item_min=item_min,
                     item_max=item_max, help=help)


MODELS: dict[str, ModelSpec] = {
    "step0": ModelSpec(
        model_id="step0",
        name="Single Neuron (Logistic Regression)",
        description=(
            "One neuron trained by gradient descent on binary cross-entropy. "
            "Separates linearly separable data; provably cannot solve XOR."
        ),
        binary=BASE_DIR / "services" / "Step0" / "nn",
        params=(
            # Built-in datasets the binary's --dataset flag accepts. Validated
            # against, never passed through: the process only ever sees a string
            # from this tuple.
            choice("dataset", "--dataset", ("tiny", "blobs", "xor"), "tiny",
                   label="Dataset"),
            # Upper bound is generous rather than principled: the sigmoid
            # saturates and the loss is clamped, so a large lr converges or
            # stalls but never blows up. It's here to keep the parameter form
            # honest, not to protect the process.
            number("lr", "--lr", 0.0001, 10.0, 0.5, label="Learning rate"),
            integer("epochs", "--epochs", 1, 5000, 500, label="Epochs"),
            integer("seed", "--seed", 0, 2**32 - 1, 42, label="Seed"),
        ),
        result_fields=(
            ResultField("final_accuracy", "accuracy", "percent"),
            ResultField("final_loss", "loss"),
        ),
        timeout_seconds=60,
    ),
    "step1": ModelSpec(
        model_id="step1",
        name="Multilayer Perceptron",
        description=(
            "Hidden layers trained by backpropagation with mini-batch SGD, "
            "softmax + cross-entropy at the output. Solves XOR — which one "
            "neuron provably cannot — and classifies MNIST digits."
        ),
        binary=BASE_DIR / "services" / "Step1" / "nn",
        params=(
            choice("dataset", "--dataset", ("xor", "mnist"), "xor", label="Dataset"),
            int_list("hidden", "--hidden", max_items=3, item_min=1, item_max=256,
                     default="8", label="Hidden layers",
                     help="Comma-separated widths, e.g. 64,32"),
            choice("activation", "--activation", ("tanh", "sigmoid", "relu"), "tanh",
                   label="Activation", help="Hidden layers only; the output layer is linear"),
            number("lr", "--lr", 0.0001, 10.0, 0.5, label="Learning rate"),
            integer("epochs", "--epochs", 1, 5000, 2000, label="Epochs"),
            integer("batch", "--batch", 1, 512, 4, label="Batch size"),
            # NOT offered: --limit 0, the binary's "use all 60000". The idx loader
            # materialises the whole file as doubles before applying the cap, so
            # 0 peaks around 960MB of RSS versus ~490MB at 10000 — enough to OOM a
            # small worker. The ceiling here is what keeps the worker sized at 1GB.
            integer("limit", "--limit", 100, 20000, 10000, label="Training samples",
                    help="MNIST only; ignored for XOR"),
            integer("seed", "--seed", 0, 2**32 - 1, 42, label="Seed"),
        ),
        result_fields=(
            ResultField("test_accuracy", "test acc", "percent"),
            ResultField("train_accuracy", "train acc", "percent"),
            ResultField("final_loss", "loss"),
            ResultField("topology", "topology", "text"),
        ),
        # MNIST at the ceiling (20000 samples, 50 epochs, 128-wide hidden) runs in
        # roughly 80s; 300s leaves room without letting a pathological parameter
        # set hold the single worker for a quarter of an hour.
        timeout_seconds=300,
        # Mirrors apply_defaults() in Step1/main.cpp. DUPLICATED ON PURPOSE and by
        # hand: the form always sends every flag, so the binary's own defaults
        # never fire, and a user picking "mnist" would otherwise be handed XOR's
        # 2000 epochs. Keep the two in sync when the driver's defaults change.
        dataset_defaults={
            "xor": {"hidden": "8", "activation": "tanh", "lr": 0.5,
                    "epochs": 2000, "batch": 4},
            "mnist": {"hidden": "32", "activation": "relu", "lr": 0.1,
                      "epochs": 15, "batch": 64},
        },
    ),
}


def get_model(model_id: str) -> ModelSpec | None:
    """Look up a spec by id, or None if there's no such model.

    Callers must treat model_id as a key into this dict and nothing else — it
    arrives from a URL path, so it must never reach a filesystem path.
    """
    return MODELS.get(model_id)
