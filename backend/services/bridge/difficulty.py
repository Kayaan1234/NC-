"""Difficulty scoring: per-modality rubric, per-step floor (bridge-plan-v3.md §6).

Tier 3 for a perceptron and Tier 3 for a CNN differ because the MODALITY
differs, not the step — so the rubric is keyed by modality and the step
contributes only a floor (BridgeSpec.difficulty_floor).

Everything here is arithmetic over the inspection and probe records — no LLM.
Every factor is reported, including the ones that could not be assessed from
the available statistics: transparently approximate beats confidently vague.

Tiers: 1 starter · 2 moderate · 3 ambitious · 4 at the edge of hobby scale.
The tier is 1 + (number of triggered factors), capped at 4, then raised to the
step's floor.
"""

from dataclasses import dataclass
from typing import Callable

from backend.services.bridge.registry import BridgeSpec, Modality

MAX_TIER = 4


@dataclass(frozen=True)
class RubricFactor:
    """One thing that makes a dataset harder to work with in this modality.
    `test` reads the inspection stats dict and returns True (triggered), False
    (assessed, not present) or None (not assessable from the stats we have)."""

    name: str
    test: Callable[[dict], bool | None]


def _frac(stats: dict, key: str) -> float | None:
    value = stats.get(key)
    return float(value) if value is not None else None


RUBRICS: dict[Modality, tuple[RubricFactor, ...]] = {
    Modality.TABULAR: (
        RubricFactor("multiclass or imbalanced target",
                     lambda s: s.get("num_classes", 0) > 2 or (
                         (_frac(s, "minority_class_fraction") or 1.0) < 0.2)),
        RubricFactor("mixed column types",
                     lambda s: None if s.get("num_text_columns") is None
                     else (s["num_text_columns"] > 0 and (s.get("num_numeric_columns") or 0) > 0)),
        RubricFactor("missing values",
                     lambda s: None if _frac(s, "null_fraction") is None
                     else (_frac(s, "null_fraction") or 0) > 0.05),
        RubricFactor("high-cardinality categoricals",
                     lambda s: None if s.get("max_category_cardinality") is None
                     else s["max_category_cardinality"] > 50),
        RubricFactor("label must be constructed",
                     lambda s: None if s.get("has_label_column") is None
                     else not s["has_label_column"]),
    ),
    Modality.IMAGE_GRID: (
        RubricFactor("mixed resolutions",
                     lambda s: s.get("mixed_resolutions")),
        RubricFactor("class imbalance",
                     lambda s: None if _frac(s, "minority_class_fraction") is None
                     else (_frac(s, "minority_class_fraction") or 1.0) < 0.2),
        RubricFactor("non-standard encodings",
                     lambda s: s.get("nonstandard_encoding")),
        RubricFactor("bounding boxes rather than plain labels",
                     lambda s: s.get("has_bounding_boxes")),
    ),
    Modality.SEQUENCE: (
        RubricFactor("irregular sampling",
                     lambda s: s.get("irregular_sampling")),
        RubricFactor("variable lengths",
                     lambda s: s.get("variable_lengths")),
        RubricFactor("multivariate series",
                     lambda s: None if s.get("num_channels") is None
                     else s["num_channels"] > 1),
        RubricFactor("missing timesteps",
                     lambda s: None if _frac(s, "null_fraction") is None
                     else (_frac(s, "null_fraction") or 0) > 0.01),
    ),
    Modality.TEXT_PAIR: (
        RubricFactor("noisy alignment",
                     lambda s: None if _frac(s, "length_ratio_outlier_fraction") is None
                     else (_frac(s, "length_ratio_outlier_fraction") or 0) > 0.05),
        RubricFactor("no held-out split",
                     lambda s: None if s.get("num_splits") is None
                     else s["num_splits"] < 2),
        RubricFactor("vocabulary explosion",
                     lambda s: None if s.get("vocab_size") is None
                     else s["vocab_size"] > 100_000),
        RubricFactor("domain mixture",
                     lambda s: s.get("domain_mixture")),
    ),
}


def score(spec: BridgeSpec, stats: dict) -> dict:
    """Compute the difficulty tier and show every assumption.

    Returns a record the verdict embeds verbatim; the critic re-derives the tier
    from this record and the spec's floor, so any drift between the two is a
    hard failure."""
    factors = []
    triggered = 0
    for factor in RUBRICS[spec.modality]:
        outcome = factor.test(stats)
        if outcome:
            triggered += 1
        factors.append({
            "name": factor.name,
            "triggered": bool(outcome) if outcome is not None else None,
            "assessed": outcome is not None,
        })

    rubric_tier = min(MAX_TIER, 1 + triggered)
    tier = max(rubric_tier, spec.difficulty_floor)
    return {
        "modality": spec.modality.value,
        "factors": factors,
        "rubric_tier": rubric_tier,
        "step_floor": spec.difficulty_floor,
        "tier": tier,
    }
