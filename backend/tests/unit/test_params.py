"""services/params.py — request-parameter validation.

This is the DoS ceiling: every accepted request spawns a real process, so a
value that slips through here costs a worker. It is also pure, so the whole
surface is cheap to cover.

Specs are built by hand rather than taken from MODELS. registry.MODELS is a
module-level dict of frozen dataclasses shared by the entire process; a test that
reached into it would leak into every other test in the run.
"""

import pytest

from backend.services.params import (
    HARD_LIMITS,
    HARD_MAX_LIST_ITEM,
    HARD_MAX_LIST_ITEMS,
    MAX_BODY_KEYS,
    ParamError,
    coerce,
    effective_max,
    format_value,
    validate,
)
from backend.services.registry import ModelSpec, choice, int_list, integer, number


def _spec(*params, model_id="demo") -> ModelSpec:
    return ModelSpec(
        model_id=model_id,
        name="Demo",
        description="",
        binary="/nonexistent/nn",
        params=params,
        result_fields=(),
    )


# --------------------------------------------------------------------------- #
# effective_max — the "spec may be tighter, never looser" rule
# --------------------------------------------------------------------------- #

def test_effective_max_takes_the_hard_limit_when_the_spec_is_looser():
    # A spec asking for 999_999 epochs is capped at the hard ceiling regardless.
    loose = integer("epochs", "--epochs", 1, 999_999, 10, label="Epochs")
    assert effective_max(loose) == HARD_LIMITS["epochs"]


def test_effective_max_takes_the_spec_when_the_spec_is_tighter():
    tight = integer("epochs", "--epochs", 1, 50, 10, label="Epochs")
    assert effective_max(tight) == 50


def test_effective_max_is_the_hard_limit_when_the_spec_has_no_maximum():
    unbounded = choice("epochs", "--epochs", ("a",), "a", label="Epochs")
    assert effective_max(unbounded) == HARD_LIMITS["epochs"]


def test_effective_max_is_none_for_a_name_with_no_hard_limit_and_no_maximum():
    free = choice("activation", "--activation", ("relu",), "relu", label="Activation")
    assert effective_max(free) is None


# --------------------------------------------------------------------------- #
# validate — body-level rejection, and the order it happens in
# --------------------------------------------------------------------------- #

def test_validate_fills_every_missing_key_from_its_default():
    spec = _spec(
        choice("dataset", "--dataset", ("tiny", "xor"), "tiny", label="Dataset"),
        number("lr", "--lr", 0.0001, 10.0, 0.5, label="Learning rate"),
    )
    # A partial body is legal; the result is always full-width, in spec order.
    assert validate(spec, {"lr": 0.25}) == {"dataset": "tiny", "lr": 0.25}
    assert list(validate(spec, {}).keys()) == ["dataset", "lr"]


def test_validate_rejects_unknown_parameters_listing_them_sorted():
    spec = _spec(number("lr", "--lr", 0.0, 1.0, 0.5, label="Learning rate"))
    with pytest.raises(ParamError) as exc:
        validate(spec, {"zebra": 1, "apple": 2})
    # Sorted, so the message is deterministic and assertable.
    assert "Unknown parameter(s): apple, zebra" in str(exc.value)


def test_validate_rejects_a_too_wide_body_before_it_inspects_the_keys():
    """Order is observable: a body over the key cap is refused on width alone,
    so the validator never walks a huge dict looking for unknown names."""
    spec = _spec(number("lr", "--lr", 0.0, 1.0, 0.5, label="Learning rate"))
    wide = {f"key{i}": i for i in range(MAX_BODY_KEYS + 1)}
    with pytest.raises(ParamError) as exc:
        validate(spec, wide)
    assert str(exc.value) == "Too many parameters."


def test_validate_rejects_a_non_object_body():
    """Unreachable over HTTP — FastAPI's `body: dict` rejects first — so this is
    the only place the branch is covered."""
    spec = _spec(number("lr", "--lr", 0.0, 1.0, 0.5, label="Learning rate"))
    with pytest.raises(ParamError, match="Expected a JSON object"):
        validate(spec, [1, 2, 3])


def test_explicit_null_is_not_the_same_as_omitting_a_parameter():
    """`raw.get(name, default)` returns None for an explicit null, so {"lr": null}
    is a type error rather than a silent fallback to the default."""
    spec = _spec(number("lr", "--lr", 0.0001, 10.0, 0.5, label="Learning rate"))
    assert validate(spec, {}) == {"lr": 0.5}
    with pytest.raises(ParamError, match="must be a number"):
        validate(spec, {"lr": None})


# --------------------------------------------------------------------------- #
# Numeric coercion
# --------------------------------------------------------------------------- #

LR = number("lr", "--lr", 0.0001, 10.0, 0.5, label="Learning rate")
EPOCHS = integer("epochs", "--epochs", 1, 5000, 500, label="Epochs")


@pytest.mark.parametrize("value,expected", [(1, 1.0), (0.25, 0.25), ("0.25", 0.25), ("  0.25  ", 0.25)])
def test_floats_accept_numbers_and_numeric_strings(value, expected):
    assert coerce(LR, value) == expected


@pytest.mark.parametrize("value", [True, False])
def test_booleans_are_rejected_even_though_bool_subclasses_int(value):
    """Without the explicit guard, True would silently arrive as lr=1.0."""
    with pytest.raises(ParamError, match="must be a number"):
        coerce(LR, value)


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), "inf", "-inf", "nan"])
def test_non_finite_values_get_their_own_distinct_message(value):
    """These survive float(), so without the check "inf" would be handed to the
    process as a command-line argument. The message differs from the plain
    type error on purpose."""
    with pytest.raises(ParamError, match="must be a finite number"):
        coerce(LR, value)


def test_an_overlong_numeric_string_is_rejected_as_a_non_number():
    """The length cap is folded into the isinstance branch, so a 51-character
    numeric string falls through to the generic message rather than a length
    one. Pinned because the message is user-facing."""
    with pytest.raises(ParamError, match="must be a number"):
        coerce(LR, "0." + "0" * 60)


def test_integers_accept_whole_valued_floats_and_exponent_strings():
    assert coerce(EPOCHS, "500.0") == 500
    assert coerce(EPOCHS, "1e3") == 1000
    assert coerce(EPOCHS, 500) == 500


def test_a_fractional_integer_reports_wholeness_before_bounds():
    """Order matters for the message: 6000.5 is both fractional and over the
    ceiling, and the user is told about the fraction."""
    with pytest.raises(ParamError, match="must be a whole number"):
        coerce(EPOCHS, 6000.5)


def test_bounds_are_inclusive_at_both_ends():
    assert coerce(EPOCHS, 1) == 1
    assert coerce(EPOCHS, 5000) == 5000


def test_below_minimum_and_above_maximum_are_rejected():
    with pytest.raises(ParamError, match="at least 1"):
        coerce(EPOCHS, 0)
    with pytest.raises(ParamError, match="at most 5000"):
        coerce(EPOCHS, 5001)


def test_bound_messages_drop_a_trailing_zero_but_keep_real_decimals():
    """`_trim`: 5000 not 5000.0, yet 0.0001 must survive intact or the message
    tells the user the minimum is 0."""
    with pytest.raises(ParamError, match=r"at most 5000\."):
        coerce(EPOCHS, 99_999)
    with pytest.raises(ParamError, match=r"at least 0\.0001\."):
        coerce(LR, 0.00001)


def test_the_hard_ceiling_overrides_a_looser_spec_at_coercion_time():
    """The spec says 999_999 epochs are fine; HARD_LIMITS says otherwise, and
    HARD_LIMITS wins. This is the DoS guard working."""
    loose = integer("epochs", "--epochs", 1, 999_999, 10, label="Epochs")
    assert coerce(loose, HARD_LIMITS["epochs"]) == HARD_LIMITS["epochs"]
    with pytest.raises(ParamError, match="at most 5000"):
        coerce(loose, HARD_LIMITS["epochs"] + 1)


# --------------------------------------------------------------------------- #
# Choices
# --------------------------------------------------------------------------- #

DATASET = choice("dataset", "--dataset", ("tiny", "blobs", "xor"), "tiny", label="Dataset")


def test_a_choice_is_stripped_then_matched_exactly():
    assert coerce(DATASET, "  xor  ") == "xor"


@pytest.mark.parametrize("value", ["XOR", "nope", "", 1, None, ["xor"]])
def test_choices_outside_the_declared_set_are_rejected(value):
    with pytest.raises(ParamError):
        coerce(DATASET, value)


# --------------------------------------------------------------------------- #
# int_list — the richest branch set
# --------------------------------------------------------------------------- #

HIDDEN = int_list(
    "hidden", "--hidden", max_items=3, item_min=1, item_max=256, default="8",
    label="Hidden layers",
)


@pytest.mark.parametrize("value", ["64,32", [64, 32], (64, 32), " 64 , 32 ", ["64", "32"]])
def test_int_lists_normalise_every_accepted_shape_to_one_canonical_string(value):
    """Storing the canonical form keeps job.params JSON-simple and comparable
    however the client chose to send it."""
    assert coerce(HIDDEN, value) == "64,32"


@pytest.mark.parametrize("value", ["8,", ",8", "8,,4", "", "  "])
def test_empty_tokens_anywhere_are_rejected(value):
    # Mirrors parse_hidden() in Step1/main.cpp, which rejects the same shapes.
    with pytest.raises(ParamError, match="comma-separated whole numbers"):
        coerce(HIDDEN, value)


def test_too_many_entries_are_rejected_against_the_specs_own_cap():
    assert coerce(HIDDEN, "1,2,3") == "1,2,3"
    with pytest.raises(ParamError, match="at most 3 entries"):
        coerce(HIDDEN, "1,2,3,4")


def test_a_spec_asking_for_more_entries_than_the_hard_cap_is_silently_clamped():
    """Asymmetry worth knowing: for list bounds the hard cap is applied at
    request time via min(), so a spec declaring max_items=20 boots fine and just
    behaves as 8 — whereas a numeric spec exceeding HARD_LIMITS refuses to boot.
    Two enforcement models for the same idea."""
    greedy = int_list(
        "hidden", "--hidden", max_items=20, item_min=1, item_max=9999, default="8",
        label="Hidden layers",
    )
    ok = ",".join(["4"] * HARD_MAX_LIST_ITEMS)
    assert coerce(greedy, ok) == ok
    with pytest.raises(ParamError, match=f"at most {HARD_MAX_LIST_ITEMS} entries"):
        coerce(greedy, ",".join(["4"] * (HARD_MAX_LIST_ITEMS + 1)))
    # ...and the per-item ceiling is clamped the same way.
    with pytest.raises(ParamError, match="entry must be"):
        coerce(greedy, str(HARD_MAX_LIST_ITEM + 1))


def test_entry_width_bounds_are_inclusive_and_use_an_en_dash():
    assert coerce(HIDDEN, "1,256") == "1,256"
    # The en-dash is part of the user-facing string; pinned so it can't drift to
    # a hyphen unnoticed.
    with pytest.raises(ParamError, match="Each hidden layers entry must be 1–256."):
        coerce(HIDDEN, "257")


@pytest.mark.parametrize("value", [1, None, {"a": 1}, 4.5])
def test_int_lists_reject_types_that_are_neither_string_nor_sequence(value):
    with pytest.raises(ParamError):
        coerce(HIDDEN, value)


def test_an_overlong_int_list_string_reports_length():
    with pytest.raises(ParamError, match="is too long"):
        coerce(HIDDEN, ",".join(["1"] * 40))


# --------------------------------------------------------------------------- #
# format_value — argv rendering
# --------------------------------------------------------------------------- #

def test_floats_render_with_repr_so_argv_is_byte_stable():
    assert format_value(LR, 0.5) == "0.5"
    assert format_value(LR, 1) == "1.0"


def test_integers_render_without_a_decimal_point():
    assert format_value(EPOCHS, 500) == "500"
    assert format_value(EPOCHS, 500.0) == "500"


def test_choices_and_lists_render_as_plain_strings():
    assert format_value(DATASET, "xor") == "xor"
    assert format_value(HIDDEN, "64,32") == "64,32"


def test_an_unusable_stored_value_fails_with_a_pointed_message():
    """Reached only for a row written under an older spec. Failing the job beats
    spawning a process with a nonsense flag."""
    with pytest.raises(ParamError, match="Stored value for 'lr' is not usable"):
        format_value(LR, "not-a-number")
