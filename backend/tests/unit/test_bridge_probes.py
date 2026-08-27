"""The probe self-test (bridge-plan-v3.md §3, "Self-test in CI") and the decide
contract.

Each step's shipped template dataset must PASS that step's own probe: if the
MLP probe rejects the dataset step1 ships with, the probe is wrong. This is the
first thing to break when someone tunes a threshold — by design.

Also the step-discrimination check (§15): step0's template must NOT pass
step1's reading and vice versa, or two steps would hand out the same verdict.
"""

from pathlib import Path

import numpy as np
import pytest

from backend.services.bridge.difficulty import score
from backend.services.bridge.probes.harness import run_probe
from backend.services.bridge.probes.tabular import (
    decide_adam_beats_sgd,
    decide_hidden_layer_wins,
    decide_linear_sufficient,
    load_csv_rows,
    prepare_xy,
)
from backend.services.bridge.registry import BRIDGE_SPECS, ProbeOutcome

FIXTURES = Path(__file__).resolve().parents[2] / "services" / "bridge" / "probes" / "fixtures"


def _rows(name: str) -> list[dict]:
    return load_csv_rows(FIXTURES / name)


@pytest.mark.parametrize("step", ["step0", "step1", "step3"])
def test_template_passes_its_own_probe(step):
    report = run_probe(BRIDGE_SPECS[step], _rows(f"{step}_template.csv"))
    assert report["outcome"] == ProbeOutcome.PASS.value, report


def test_step_discrimination_on_the_same_pool():
    """The check that proves the variant contract discriminates: the same data
    must reach DIFFERENT verdicts at step0 and step1."""
    step0_rows = _rows("step0_template.csv")
    step1_rows = _rows("step1_template.csv")
    # step0's linearly-separable blobs: a hidden layer buys nothing -> step1 fails.
    assert run_probe(BRIDGE_SPECS["step1"], step0_rows)["outcome"] != ProbeOutcome.PASS.value
    # step1's circles: a line is NOT enough -> step0 fails.
    assert run_probe(BRIDGE_SPECS["step0"], step1_rows)["outcome"] == ProbeOutcome.FAIL.value


def test_unlabelled_rows_are_unconfirmed_not_an_error():
    rows = [{"a": str(i), "b": str(i * 2)} for i in range(100)]  # no label anywhere
    report = run_probe(BRIDGE_SPECS["step1"], rows)
    assert report["outcome"] == ProbeOutcome.UNCONFIRMED.value
    assert "label" in report["reason"]


class TestDecide:
    """decide() must never round noise into a recommendation."""

    def test_gap_inside_band_is_unconfirmed(self):
        outcome, reason = decide_hidden_layer_wins(
            {"majority": 0.5, "linear": 0.80, "mlp": 0.82}, band=0.05
        )
        assert outcome == ProbeOutcome.UNCONFIRMED
        assert "noise band" in reason

    def test_gap_beyond_band_passes(self):
        outcome, _ = decide_hidden_layer_wins(
            {"majority": 0.5, "linear": 0.55, "mlp": 0.95}, band=0.05
        )
        assert outcome == ProbeOutcome.PASS

    def test_linear_sufficient_fails_when_hidden_helps(self):
        outcome, reason, code = decide_linear_sufficient(
            {"majority": 0.5, "linear": 0.7, "mlp": 0.95}, band=0.05
        )
        assert outcome == ProbeOutcome.FAIL
        assert "step 1" in reason
        assert code == "needs_hidden_layer"

    def test_linear_sufficient_fails_on_unlearnable_data(self):
        outcome, reason, code = decide_linear_sufficient(
            {"majority": 0.5, "linear": 0.51, "mlp": 0.52}, band=0.05
        )
        assert outcome == ProbeOutcome.FAIL
        assert "majority" in reason
        # The two FAIL branches mean different things to a reader, so they must
        # carry different codes: "nothing to learn here" is not "use a bigger
        # model", and the dataset page says so out loud.
        assert code == "no_signal"

    def test_the_two_fail_branches_read_differently(self):
        probe = BRIDGE_SPECS["step0"].probe
        assert probe.plain_outcomes["no_signal"] != probe.plain_outcomes["needs_hidden_layer"]

    def test_adam_gap_inside_band_is_unconfirmed(self):
        outcome, _ = decide_adam_beats_sgd({"sgd": 0.80, "adam": 0.82}, band=0.05)
        assert outcome == ProbeOutcome.UNCONFIRMED


class TestPrepareXY:
    def test_label_column_by_name(self):
        rows = [{"x": str(i % 7), "label": str(i % 2)} for i in range(100)]
        X, y = prepare_xy(rows)
        assert len(X) == 100 and set(y.tolist()) == {0, 1}

    def test_no_features_returns_none(self):
        rows = [{"freetext": f"row {i} unique", "label": str(i % 2)} for i in range(100)]
        assert prepare_xy(rows) is None

    def test_infinities_are_dropped_like_missing_values(self):
        """np.isnan is False for +/-inf, so an infinity used to survive the row
        filter and then blow up inside sklearn, failing every seed and costing
        the page its fit line. A sensor export with one divide-by-zero in it is
        an ordinary dataset, not an exotic one."""
        rows = [{"a": float(i % 7), "b": float(i % 3), "label": i % 2} for i in range(120)]
        rows[5]["a"] = float("inf")
        rows[9]["b"] = float("-inf")
        rows[11]["a"] = ""  # the missing-value path must keep working too

        X, y = prepare_xy(rows)
        assert len(X) == 117
        assert np.isfinite(X).all()


class TestDifficulty:
    def test_floor_raises_the_tier(self):
        step0 = BRIDGE_SPECS["step0"]
        step3 = BRIDGE_SPECS["step3"]
        clean = {"num_classes": 2, "null_fraction": 0.0, "has_label_column": True}
        assert score(step0, clean)["tier"] == 1
        assert score(step3, clean)["tier"] == step3.difficulty_floor

    def test_factors_raise_the_rubric_tier(self):
        step0 = BRIDGE_SPECS["step0"]
        messy = {"num_classes": 5, "null_fraction": 0.2, "has_label_column": False,
                 "max_category_cardinality": 200}
        result = score(step0, messy)
        assert result["rubric_tier"] > 1
        assert any(f["triggered"] for f in result["factors"])

    def test_unassessable_factors_are_reported_not_guessed(self):
        result = score(BRIDGE_SPECS["step0"], {})
        assert any(f["assessed"] is False for f in result["factors"])
