"""The bridge registry boot gate: a malformed spec must stop the process.

Mirrors unit/test_registry.py's role for MODELS. Failure cases build broken
specs and patch them into BRIDGE_SPECS via monkeypatch.setitem so the real
registry is never mutated.
"""

import dataclasses

import pytest

from backend.services.bridge import registry as bridge_registry
from backend.services.bridge.registry import (
    BRIDGE_SPECS,
    LLM_BUDGETS,
    LLM_HARD_LIMITS,
    PROBE_HARD_LIMITS,
    BridgeSpec,
    DataRequirement,
    Modality,
    ProbeSpec,
    check_bridge_registry,
)
from backend.services.registry import MODELS


def test_real_registry_passes_the_gate():
    check_bridge_registry()


def test_every_trainable_model_has_a_bridge_spec():
    assert set(MODELS) <= set(BRIDGE_SPECS)


def test_registry_is_a_superset_not_parity():
    # The whole point: the bridge answers questions about steps that can't
    # train yet. If this ever becomes equality the containment check still
    # passes, but today it shouldn't be.
    assert set(BRIDGE_SPECS) - set(MODELS)


def test_ordinals_cover_the_ladder():
    assert sorted(s.ordinal for s in BRIDGE_SPECS.values()) == list(range(10))


def test_probe_none_always_carries_a_reason():
    for spec in BRIDGE_SPECS.values():
        if spec.data_requirement == DataRequirement.OWN_ASSESSMENT and spec.probe is None:
            assert spec.no_probe_reason


def test_llm_budgets_respect_hard_limits():
    for budget in LLM_BUDGETS.values():
        assert budget.max_output_tokens <= LLM_HARD_LIMITS["max_output_tokens"]
        assert budget.max_input_tokens <= LLM_HARD_LIMITS["max_input_tokens"]


def _probe(**overrides) -> ProbeSpec:
    """A complete, valid ProbeSpec. Tests override the one field under test so a
    failure names the rule it was probing, not an unrelated missing field."""
    base = dict(
        probe_id="tabular_hidden_layer_wins",
        row_cap=5000,
        wall_clock_seconds=60,
        memory_mb=512,
        seeds=(0, 1, 2),
        metric="accuracy",
        plain_outcomes={"pass": "it fits", "fail": "it does not", "unconfirmed": "hard to say"},
    )
    base.update(overrides)
    return ProbeSpec(**base)


def _spec(**overrides) -> BridgeSpec:
    base = dict(
        model_id="stepX",
        ordinal=99,
        display_name="Test",
        capability="a one-line capability",
        modality=Modality.TABULAR,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        no_probe_reason="not built",
    )
    base.update(overrides)
    return BridgeSpec(**base)


@pytest.mark.parametrize(
    "broken, message_fragment",
    [
        (_spec(model_id="mismatch"), "!= dict key"),
        (_spec(ordinal=0), "duplicate ordinal"),
        (_spec(capability="two\nlines"), "one non-empty line"),
        (_spec(no_probe_reason=None), "no_probe_reason"),
        (
            _spec(data_requirement=DataRequirement.INHERITS_VERDICT,
                  inherits_from="nope", no_probe_reason=None),
            "does not exist",
        ),
        (
            _spec(data_requirement=DataRequirement.INHERITS_VERDICT,
                  inherits_from="step2", no_probe_reason=None),
            "itself inherits",
        ),
        (
            _spec(data_requirement=DataRequirement.OWN_ASSESSMENT,
                  inherits_from="step1"),
            "forbids inherits_from",
        ),
        (
            _spec(no_probe_reason=None, probe=_probe(seeds=(0, 1))),
            ">=3 seeds",
        ),
        (
            _spec(no_probe_reason=None,
                  probe=_probe(row_cap=PROBE_HARD_LIMITS["row_cap"] + 1)),
            "exceeds PROBE_HARD_LIMITS",
        ),
        (
            # Every probe must say what its three outcomes MEAN in plain words;
            # the dataset page reads them straight out of the descriptor.
            _spec(no_probe_reason=None,
                  probe=_probe(plain_outcomes={"pass": "it fits"})),
            "missing plain_outcomes",
        ),
    ],
)
def test_malformed_specs_fail_the_gate(monkeypatch, broken, message_fragment):
    monkeypatch.setitem(BRIDGE_SPECS, "stepX", broken)
    with pytest.raises(RuntimeError, match=message_fragment):
        check_bridge_registry()


def test_missing_trainable_spec_fails_the_gate(monkeypatch):
    without_step0 = {k: v for k, v in BRIDGE_SPECS.items() if k != "step0"}
    monkeypatch.setattr(bridge_registry, "BRIDGE_SPECS", without_step0)
    with pytest.raises(RuntimeError, match="without a BridgeSpec"):
        check_bridge_registry()


def test_enabling_bridge_without_keys_fails_the_gate(monkeypatch):
    monkeypatch.setattr(bridge_registry.settings, "BRIDGE_ENABLED", True)
    monkeypatch.setattr(bridge_registry.settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(bridge_registry.settings, "VOYAGER_API_KEY", "pa-x")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        check_bridge_registry()


def test_dangling_probe_id_fails_the_strict_gate(monkeypatch):
    spec = _spec(no_probe_reason=None, probe=_probe(probe_id="no_such_probe"), ordinal=99)
    monkeypatch.setitem(BRIDGE_SPECS, "stepX", spec)
    check_bridge_registry()  # web-side gate can't resolve implementations: passes
    with pytest.raises(RuntimeError, match="no implementation"):
        check_bridge_registry(require_probe_impls=True)


def test_specs_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        BRIDGE_SPECS["step0"].ordinal = 5  # type: ignore[misc]
