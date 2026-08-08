"""services/registry.py descriptors and the check_registry() boot gate.

check_registry() runs at import of backend.main and backend.worker, so a
malformed spec takes the whole process down rather than surfacing as a 422 the
user can't explain. These tests pin every rejection reason, and — more
importantly — assert that the real registry passes, which is what stops a new
model entry breaking startup.
"""

import pytest

from backend.services.params import (
    HARD_LIMITS,
    ParamError,
    _check_spec,
    check_registry,
    coerce,
    effective_max,
)
from backend.services.registry import (
    KIND_CHOICE,
    KIND_FLOAT,
    KIND_INT,
    KIND_INT_LIST,
    MODELS,
    ModelSpec,
    ParamSpec,
    choice,
    get_model,
    int_list,
    integer,
    number,
)


def _spec(*params, model_id="demo", **kwargs) -> ModelSpec:
    return ModelSpec(
        model_id=model_id,
        name="Demo",
        description="",
        binary="/nonexistent/nn",
        params=params or (number("lr", "--lr", 0.0, 1.0, 0.5, label="Learning rate"),),
        result_fields=(),
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# The real registry
# --------------------------------------------------------------------------- #

def test_the_shipped_registry_passes_its_own_boot_check():
    """If this fails, `import backend.main` raises and the API will not start."""
    check_registry()


def test_every_shipped_model_is_keyed_by_its_own_model_id():
    for key, spec in MODELS.items():
        assert key == spec.model_id


def test_get_model_returns_none_for_an_unknown_id_rather_than_raising():
    assert get_model("step0") is not None
    assert get_model("nope") is None
    # model_id is only ever a dict key, never joined onto a path — so traversal
    # attempts are just misses.
    assert get_model("../../etc/passwd") is None


def test_every_shipped_default_survives_the_validator_it_will_face():
    """A default the server would itself reject means the generated form ships a
    value that 422s the moment the user hits submit."""
    for spec in MODELS.values():
        for param in spec.params:
            coerce(param, param.default)


def test_no_shipped_parameter_exceeds_its_hard_ceiling():
    for spec in MODELS.values():
        for param in spec.params:
            hard = HARD_LIMITS.get(param.name)
            if hard is not None and param.maximum is not None:
                assert param.maximum <= hard, (
                    f"{spec.model_id}.{param.name} maximum {param.maximum} > {hard}"
                )
                assert effective_max(param) == min(param.maximum, hard)


def test_every_shipped_dataset_default_names_a_real_dataset_and_parameter():
    for spec in MODELS.values():
        dataset_param = next((p for p in spec.params if p.name == "dataset"), None)
        names = {p.name for p in spec.params}
        for dataset, overrides in spec.dataset_defaults.items():
            if dataset_param is not None:
                assert dataset in dataset_param.choices
            assert set(overrides) <= names


# --------------------------------------------------------------------------- #
# _check_spec — one test per rejection reason
# --------------------------------------------------------------------------- #

def test_a_spec_with_no_parameters_is_rejected():
    with pytest.raises(RuntimeError, match="has no parameters"):
        _check_spec(ModelSpec(
            model_id="demo", name="D", description="", binary="/nn",
            params=(), result_fields=(),
        ))


def test_two_parameters_with_the_same_name_are_rejected():
    duplicate = number("lr", "--lr", 0.0, 1.0, 0.5, label="Learning rate")
    with pytest.raises(RuntimeError, match="duplicate parameter 'lr'"):
        _check_spec(_spec(duplicate, duplicate))


def test_an_unknown_parameter_kind_is_rejected():
    weird = ParamSpec(name="x", flag="--x", kind="colour", label="X", default="a")
    with pytest.raises(RuntimeError, match="unknown kind 'colour'"):
        _check_spec(_spec(weird))


def test_a_flag_that_is_not_a_long_option_is_rejected():
    short = ParamSpec(
        name="lr", flag="-l", kind=KIND_FLOAT, label="Learning rate",
        default=0.5, minimum=0.0, maximum=1.0,
    )
    with pytest.raises(RuntimeError, match="not a long option"):
        _check_spec(_spec(short))


def test_a_choice_parameter_with_no_choices_is_rejected():
    empty = ParamSpec(
        name="dataset", flag="--dataset", kind=KIND_CHOICE, label="Dataset",
        default="x", choices=(),
    )
    with pytest.raises(RuntimeError, match="has no choices"):
        _check_spec(_spec(empty))


@pytest.mark.parametrize("kind", [KIND_FLOAT, KIND_INT])
def test_a_numeric_parameter_missing_a_bound_is_rejected(kind):
    unbounded = ParamSpec(
        name="x", flag="--x", kind=kind, label="X", default=1, minimum=0, maximum=None,
    )
    with pytest.raises(RuntimeError, match="needs both a minimum and a maximum"):
        _check_spec(_spec(unbounded))


def test_an_inverted_range_is_rejected():
    inverted = ParamSpec(
        name="x", flag="--x", kind=KIND_INT, label="X", default=5, minimum=10, maximum=1,
    )
    with pytest.raises(RuntimeError, match="minimum > maximum"):
        _check_spec(_spec(inverted))


def test_a_maximum_above_the_hard_ceiling_refuses_to_boot():
    """The point of HARD_LIMITS: a careless registry entry cannot raise the cap,
    and the failure is at startup rather than on a request."""
    greedy = integer("epochs", "--epochs", 1, int(HARD_LIMITS["epochs"]) + 1, 10, label="Epochs")
    with pytest.raises(RuntimeError, match="exceeds the hard limit"):
        _check_spec(_spec(greedy))


def test_a_maximum_exactly_at_the_hard_ceiling_is_allowed():
    """The comparison is strict (`>`), so a spec may sit right on the cap."""
    at_cap = integer("epochs", "--epochs", 1, int(HARD_LIMITS["epochs"]), 10, label="Epochs")
    _check_spec(_spec(at_cap))


def test_a_default_the_spec_would_itself_reject_is_rejected():
    bad_default = integer("epochs", "--epochs", 10, 20, 999, label="Epochs")
    with pytest.raises(RuntimeError, match="default for 'epochs' is invalid"):
        _check_spec(_spec(bad_default))


def test_dataset_defaults_naming_an_unknown_dataset_are_rejected():
    """A typo here would silently mean "this dataset has no overrides", so the
    form would quietly hand the user another dataset's defaults."""
    spec = _spec(
        choice("dataset", "--dataset", ("xor",), "xor", label="Dataset"),
        dataset_defaults={"mnist": {}},
    )
    with pytest.raises(RuntimeError, match="no such dataset 'mnist'"):
        _check_spec(spec)


def test_dataset_defaults_naming_an_unknown_parameter_are_rejected():
    spec = _spec(
        choice("dataset", "--dataset", ("xor",), "xor", label="Dataset"),
        dataset_defaults={"xor": {"nonexistent": 1}},
    )
    with pytest.raises(RuntimeError, match="unknown parameter 'nonexistent'"):
        _check_spec(spec)


def test_a_dataset_default_value_out_of_range_is_rejected():
    spec = _spec(
        choice("dataset", "--dataset", ("xor",), "xor", label="Dataset"),
        integer("epochs", "--epochs", 1, 100, 10, label="Epochs"),
        dataset_defaults={"xor": {"epochs": 5000}},
    )
    with pytest.raises(RuntimeError, match=r"dataset_defaults\['xor'\]\['epochs'\] is invalid"):
        _check_spec(spec)


# --------------------------------------------------------------------------- #
# Descriptor constructors
# --------------------------------------------------------------------------- #

def test_the_constructors_set_the_kind_that_matches_their_name():
    assert choice("d", "--d", ("a",), "a", label="D").kind == KIND_CHOICE
    assert number("lr", "--lr", 0.0, 1.0, 0.5, label="L").kind == KIND_FLOAT
    assert integer("e", "--e", 1, 2, 1, label="E").kind == KIND_INT
    assert int_list("h", "--h", 3, 1, 9, "1", label="H").kind == KIND_INT_LIST


def test_descriptors_are_frozen_so_a_test_cannot_leak_into_the_shared_registry():
    param = number("lr", "--lr", 0.0, 1.0, 0.5, label="Learning rate")
    with pytest.raises(Exception):
        param.maximum = 999  # type: ignore[misc]


def test_a_stored_value_from_an_older_spec_fails_loudly_rather_than_silently():
    param = choice("dataset", "--dataset", ("tiny", "xor"), "tiny", label="Dataset")
    with pytest.raises(ParamError):
        coerce(param, "a-dataset-that-was-removed")
