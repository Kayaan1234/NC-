"""Probe implementations, keyed by BridgeSpec.probe.probe_id.

WORKER-ONLY: this package imports numpy/scikit-learn, which the web image
deliberately does not ship. The registry references probes by id so the web
process can boot without resolving them; the worker boots with
check_bridge_registry(require_probe_impls=True), which resolves every id
against PROBES and fails fast on a dangling one.
"""

from dataclasses import dataclass
from typing import Callable

from backend.services.bridge.probes.tabular import (
    decide_adam_beats_sgd,
    decide_hidden_layer_wins,
    decide_linear_sufficient,
    fit_optimiser_variants,
    fit_tabular_variants,
)


@dataclass(frozen=True)
class Probe:
    """The two-function contract of bridge-plan-v3.md §3: fit NAMED variants,
    then decide from their metrics and the measured noise band — and never
    round noise into a recommendation."""

    fit_variants: Callable  # (X, y, seed) -> dict[variant_name, metric]
    decide: Callable        # (metrics, noise_band) -> (ProbeOutcome, reason)


PROBES: dict[str, Probe] = {
    "tabular_linear_sufficient": Probe(fit_tabular_variants, decide_linear_sufficient),
    "tabular_hidden_layer_wins": Probe(fit_tabular_variants, decide_hidden_layer_wins),
    "tabular_adam_beats_sgd": Probe(fit_optimiser_variants, decide_adam_beats_sgd),
}
