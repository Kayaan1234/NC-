"""Validates a training request against a model's ParamSpec descriptors.

This module is where the DoS ceiling lives. It used to be the `Field(le=...)`
literals on a pydantic `TrainRequest`; moving parameter definitions into the
registry moved the enforcement here, and the reasoning is unchanged: every
accepted request spawns a real process, so `epochs: 1_000_000_000` would be a free
way to burn a worker.

HARD_LIMITS is deliberately NOT derived from the registry. A ModelSpec may be
tighter than the ceiling, never looser — so a careless registry entry cannot
raise the cap, and check_registry() refuses to start the process if one tries.

Import direction is one-way: params -> registry. `registry` must never import
this module at the top level or the two would cycle; check_registry() imports
MODELS lazily inside the function, and the API and worker call it at startup.
"""

from typing import Any

from backend.services.registry import (
    KIND_CHOICE,
    KIND_FLOAT,
    KIND_INT,
    KIND_INT_LIST,
    ModelSpec,
    ParamSpec,
)


class ParamError(ValueError):
    """A request parameter the server refuses. The message is user-facing."""


# Absolute ceilings by parameter name, independent of any ModelSpec. These are
# the numbers that used to sit in TrainRequest's Field(...) literals.
HARD_LIMITS: dict[str, float] = {
    "epochs": 5000,
    "lr": 10.0,
    "batch": 4096,
    # See the registry's step1 entry: the idx loader reads the whole file before
    # applying the cap, so this bounds worker memory, not just runtime.
    "limit": 20000,
    "seed": 2**32 - 1,
}
HARD_MAX_LIST_ITEMS = 8
HARD_MAX_LIST_ITEM = 1024
MAX_STRING_LEN = 50
# A request body can only ever be as wide as the widest model plus slack; this
# stops a caller making the validator walk a huge dict before it rejects it.
MAX_BODY_KEYS = 32

_KINDS = (KIND_CHOICE, KIND_FLOAT, KIND_INT, KIND_INT_LIST)


def effective_max(p: ParamSpec) -> float | None:
    """The tighter of the spec's own maximum and the hard ceiling for its name."""
    hard = HARD_LIMITS.get(p.name)
    if p.maximum is None:
        return hard
    if hard is None:
        return p.maximum
    return min(p.maximum, hard)


def validate(spec: ModelSpec, raw: Any) -> dict[str, Any]:
    """Turn a request body into the parameter dict a run is built from.

    Rejects unknown keys, coerces each value to its declared kind, and bounds it.
    A missing key falls back to the parameter's default, so a client may send a
    partial body. The returned dict is keyed by parameter name in spec order and
    is what gets stored on the job row — a finished report is then self-describing
    even after the model's defaults or bounds change.
    """
    if not isinstance(raw, dict):
        raise ParamError("Expected a JSON object of parameters.")
    if len(raw) > MAX_BODY_KEYS:
        raise ParamError("Too many parameters.")

    known = {p.name for p in spec.params}
    unknown = sorted(k for k in raw if k not in known)
    if unknown:
        raise ParamError(
            f"Unknown parameter(s): {', '.join(unknown)}. "
            f"Expected one of: {', '.join(p.name for p in spec.params)}"
        )

    return {p.name: coerce(p, raw.get(p.name, p.default)) for p in spec.params}


def coerce(p: ParamSpec, value: Any) -> Any:
    """Validate one value against one descriptor, returning the stored form.

    Stored form by kind: choice -> str, float -> float, int -> int,
    int_list -> the canonical "64,32" string (so job.params stays JSON-simple and
    comparable regardless of whether the client sent a string or a list).
    """
    if p.kind == KIND_CHOICE:
        return _coerce_choice(p, value)
    if p.kind == KIND_FLOAT:
        return _coerce_float(p, value)
    if p.kind == KIND_INT:
        return _coerce_int(p, value)
    if p.kind == KIND_INT_LIST:
        return _coerce_int_list(p, value)
    raise ParamError(f"Parameter '{p.name}' has an unsupported kind '{p.kind}'.")


def format_value(p: ParamSpec, value: Any) -> str:
    """Render one validated value as a single argv token.

    The only place argv formatting lives. `repr(float(...))` for floats matches
    what the router produced before descriptors existed, so an existing step0 job
    builds a byte-identical command line.
    """
    try:
        if p.kind == KIND_FLOAT:
            return repr(float(value))
        if p.kind == KIND_INT:
            return str(int(value))
        return str(value)
    except (TypeError, ValueError) as exc:
        # Reached only for a value that bypassed validate() — i.e. one read back
        # from a job row written under an older spec. Failing the job with this
        # message beats spawning a process with a nonsense flag.
        raise ParamError(f"Stored value for '{p.name}' is not usable: {value!r}") from exc


# --- per-kind coercion --------------------------------------------------------

def _coerce_choice(p: ParamSpec, value: Any) -> str:
    if not isinstance(value, str):
        raise ParamError(f"{p.label} must be one of: {', '.join(p.choices)}")
    text = value.strip()
    if len(text) > MAX_STRING_LEN:
        raise ParamError(f"{p.label} is too long.")
    if text not in p.choices:
        raise ParamError(
            f"Unknown {p.name} '{text}'. Expected one of: {', '.join(p.choices)}"
        )
    return text


def _as_number(p: ParamSpec, value: Any) -> float:
    # bool is an int subclass in Python; True would silently become 1.
    if isinstance(value, bool):
        raise ParamError(f"{p.label} must be a number.")
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str) and len(value) <= MAX_STRING_LEN:
        try:
            num = float(value.strip())
        except ValueError:
            raise ParamError(f"{p.label} must be a number.") from None
    else:
        raise ParamError(f"{p.label} must be a number.")
    # inf/nan pass float() and would reach the process as "inf".
    if num != num or num in (float("inf"), float("-inf")):
        raise ParamError(f"{p.label} must be a finite number.")
    return num


def _bounds(p: ParamSpec, num: float) -> None:
    hi = effective_max(p)
    if p.minimum is not None and num < p.minimum:
        raise ParamError(f"{p.label} must be at least {_trim(p.minimum)}.")
    if hi is not None and num > hi:
        raise ParamError(f"{p.label} must be at most {_trim(hi)}.")


def _coerce_float(p: ParamSpec, value: Any) -> float:
    num = _as_number(p, value)
    _bounds(p, num)
    return num


def _coerce_int(p: ParamSpec, value: Any) -> int:
    num = _as_number(p, value)
    if num != int(num):
        raise ParamError(f"{p.label} must be a whole number.")
    _bounds(p, num)
    return int(num)


def _coerce_int_list(p: ParamSpec, value: Any) -> str:
    """Accept "64,32" or [64, 32]; always store "64,32".

    Matches parse_hidden() in Step1/main.cpp, which rejects empty tokens and
    non-positive widths — this rejects the same shapes earlier, with a message.
    """
    if isinstance(value, (list, tuple)):
        tokens = [str(v).strip() for v in value]
    elif isinstance(value, str):
        if len(value) > MAX_STRING_LEN:
            raise ParamError(f"{p.label} is too long.")
        tokens = [t.strip() for t in value.split(",")]
    else:
        raise ParamError(f"{p.label} must be comma-separated whole numbers, e.g. 64,32")

    if not tokens or any(t == "" for t in tokens):
        raise ParamError(f"{p.label} must be comma-separated whole numbers, e.g. 64,32")

    max_items = min(p.max_items or HARD_MAX_LIST_ITEMS, HARD_MAX_LIST_ITEMS)
    if len(tokens) > max_items:
        raise ParamError(f"{p.label} may have at most {max_items} entries.")

    item_max = min(p.item_max or HARD_MAX_LIST_ITEM, HARD_MAX_LIST_ITEM)
    item_min = p.item_min if p.item_min is not None else 1
    widths: list[int] = []
    for token in tokens:
        try:
            width = int(token)
        except ValueError:
            raise ParamError(
                f"{p.label} must be comma-separated whole numbers, e.g. 64,32"
            ) from None
        if width < item_min or width > item_max:
            raise ParamError(f"Each {p.label.lower()} entry must be {item_min}–{item_max}.")
        widths.append(width)
    return ",".join(str(w) for w in widths)


def _trim(num: float) -> str:
    """Format a bound for a message: 5000 not 5000.0, but 0.0001 intact."""
    return str(int(num)) if float(num).is_integer() else str(num)


# --- startup self-check -------------------------------------------------------

def check_registry() -> None:
    """Fail fast on a malformed or over-generous ModelSpec.

    Called from the API and worker startup. A registry entry that exceeds a hard
    limit, names two parameters the same, or carries a default it would itself
    reject is a bug that must surface on boot — not on the first request, and
    certainly not as a job that fails after a user waits for it.
    """
    from backend.services.registry import MODELS   # lazy: params -> registry only

    for model_id, spec in MODELS.items():
        if model_id != spec.model_id:
            raise RuntimeError(f"MODELS['{model_id}'] has model_id '{spec.model_id}'")
        _check_spec(spec)


def _check_spec(spec: ModelSpec) -> None:
    def fail(msg: str) -> None:
        raise RuntimeError(f"ModelSpec '{spec.model_id}': {msg}")

    if not spec.params:
        fail("has no parameters")

    seen: set[str] = set()
    for p in spec.params:
        if p.name in seen:
            fail(f"duplicate parameter '{p.name}'")
        seen.add(p.name)
        if p.kind not in _KINDS:
            fail(f"parameter '{p.name}' has unknown kind '{p.kind}'")
        if not p.flag.startswith("--"):
            fail(f"parameter '{p.name}' has a flag that is not a long option: {p.flag!r}")

        if p.kind == KIND_CHOICE and not p.choices:
            fail(f"choice parameter '{p.name}' has no choices")
        if p.kind in (KIND_FLOAT, KIND_INT):
            if p.minimum is None or p.maximum is None:
                fail(f"numeric parameter '{p.name}' needs both a minimum and a maximum")
            elif p.minimum > p.maximum:
                fail(f"parameter '{p.name}' has minimum > maximum")
            hard = HARD_LIMITS.get(p.name)
            if hard is not None and p.maximum is not None and p.maximum > hard:
                fail(
                    f"parameter '{p.name}' maximum {p.maximum} exceeds the hard "
                    f"limit {hard} (raise HARD_LIMITS deliberately, or lower the spec)"
                )

        # The default must survive the same gate a request does, or the form
        # would ship a value the server rejects on submit.
        try:
            coerce(p, p.default)
        except ParamError as exc:
            fail(f"default for '{p.name}' is invalid: {exc}")

    dataset_param = next((p for p in spec.params if p.name == "dataset"), None)
    for dataset, overrides in spec.dataset_defaults.items():
        # A typo here would silently mean "this dataset has no overrides", so the
        # form would quietly hand the user another dataset's defaults.
        if dataset_param is not None and dataset not in dataset_param.choices:
            fail(f"dataset_defaults has no such dataset '{dataset}'")
        for name, value in overrides.items():
            match = next((p for p in spec.params if p.name == name), None)
            if match is None:
                fail(f"dataset_defaults['{dataset}'] sets unknown parameter '{name}'")
            else:
                try:
                    coerce(match, value)
                except ParamError as exc:
                    fail(f"dataset_defaults['{dataset}']['{name}'] is invalid: {exc}")
