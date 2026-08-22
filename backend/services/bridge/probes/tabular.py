"""Tabular probes: the named-variant fits and decisions for steps 0, 1 and 3.

The variant framing is the whole generalisation (bridge-plan-v3.md §3): step0
and step1 share one fit over {majority, linear, mlp} and differ only in what
their decide() reads from the gaps; step3 compares {sgd, adam} — the SAME
architecture under two optimisers — which the old baseline/linear/MLP triple
could not express at all.

All decisions are made against the MEASURED noise band (harness.py fits every
variant across >=3 seeds). A gap inside the band is UNCONFIRMED, never a
recommendation.
"""

import csv
import math
import warnings
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from backend.services.bridge.registry import ProbeOutcome

# Column names accepted as the target, in preference order. If none matches,
# the probe reports honestly that no label is identifiable — deriving one is
# then the learner's first design decision, and the verdict says so.
LABEL_NAMES = ("label", "target", "class", "y", "outcome", "result")

# Categorical feature columns wider than this are dropped rather than one-hot
# encoded — the probe is a feasibility measurement, not a modelling exercise.
MAX_ONEHOT_CARDINALITY = 20


def load_csv_rows(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def prepare_xy(rows: list[dict]) -> tuple[np.ndarray, np.ndarray] | None:
    """Turn inspection rows (list of flat dicts) into a feature matrix and a
    label vector, or None when no usable label column can be identified.

    Numeric columns become features directly; low-cardinality string columns are
    one-hot encoded; everything else (free text, ids) is dropped. Deliberately
    simple — the probe measures whether structure exists, not how well it can be
    modelled.
    """
    if not rows:
        return None
    columns = list(rows[0].keys())

    label_col = next((c for c in columns if c.lower() in LABEL_NAMES), None)
    if label_col is None:
        # Fall back: a trailing low-cardinality column is usually the target.
        for c in reversed(columns):
            values = {str(r.get(c)) for r in rows}
            if 2 <= len(values) <= MAX_ONEHOT_CARDINALITY:
                label_col = c
                break
    if label_col is None:
        return None

    y_raw = [str(r.get(label_col)) for r in rows]
    classes = sorted(set(y_raw))
    if len(classes) < 2:
        return None
    y = np.array([classes.index(v) for v in y_raw])

    features: list[np.ndarray] = []
    for c in columns:
        if c == label_col:
            continue
        raw = [r.get(c) for r in rows]
        numeric = _as_numeric(raw)
        if numeric is not None:
            features.append(numeric.reshape(-1, 1))
            continue
        values = sorted({str(v) for v in raw})
        if 2 <= len(values) <= MAX_ONEHOT_CARDINALITY:
            onehot = np.zeros((len(raw), len(values)))
            index = {v: i for i, v in enumerate(values)}
            for row_i, v in enumerate(raw):
                onehot[row_i, index[str(v)]] = 1.0
            features.append(onehot)
    if not features:
        return None

    X = np.hstack(features)
    # isfinite, not ~isnan: np.isnan is False for +/-inf, so an infinity slips
    # through this filter and then detonates inside sklearn ("Input X contains
    # infinity"), which costs the whole probe — every seed fails and the page
    # loses the one line a dataset search cannot give you. Sensor exports carry
    # infinities routinely (a divide-by-zero upstream), so this is a normal data
    # fact, not an exotic one. Same intent as before, one more way of not being
    # a usable number.
    keep = np.isfinite(X).all(axis=1)
    X, y = X[keep], y[keep]
    if len(X) < 40 or len(set(y.tolist())) < 2:
        return None
    return X, y


def _as_numeric(raw: list) -> np.ndarray | None:
    out = np.empty(len(raw))
    for i, v in enumerate(raw):
        if v is None or v == "":
            out[i] = np.nan
            continue
        try:
            out[i] = float(v)
        except (TypeError, ValueError):
            return None
    if np.all(np.isnan(out)):
        return None
    return out


def _accuracy(model, X, y, seed: int, scale: bool = True) -> float:
    stratify = y if min(np.bincount(y)) >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=seed, stratify=stratify
    )
    if scale:
        scaler = StandardScaler().fit(X_train)
        X_train, X_test = scaler.transform(X_train), scaler.transform(X_test)
    with warnings.catch_warnings():
        # Non-convergence inside the iteration budget is EXPECTED here — the
        # step3 probe exists to catch SGD still lost when the budget runs out.
        # Left unfiltered, the suite's warnings-as-errors policy would turn the
        # measurement into an exception.
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(X_train, y_train)
    return float(model.score(X_test, y_test))


def fit_tabular_variants(X: np.ndarray, y: np.ndarray, seed: int) -> dict[str, float]:
    """The shared fit for steps 0 and 1: does a line do it, and does a hidden
    layer buy anything beyond one?"""
    return {
        "majority": _accuracy(DummyClassifier(strategy="most_frequent"), X, y, seed, scale=False),
        "linear": _accuracy(LogisticRegression(max_iter=1000), X, y, seed),
        "mlp": _accuracy(
            MLPClassifier(hidden_layer_sizes=(32,), max_iter=300, random_state=seed),
            X, y, seed,
        ),
    }


def fit_optimiser_variants(X: np.ndarray, y: np.ndarray, seed: int) -> dict[str, float]:
    """Step 3: the SAME architecture under plain SGD vs Adam, on a deliberately
    tight epoch budget — the checkpoint's claim is that Adam trains faster and
    to a better score, which only shows while the budget binds. Features are NOT
    standardised here: adaptive learning rates earn their keep on badly scaled
    inputs, and rescaling everything would probe a dataset we invented."""
    common = dict(hidden_layer_sizes=(32,), max_iter=40, random_state=seed)
    return {
        "sgd": _accuracy(
            MLPClassifier(solver="sgd", learning_rate_init=0.01, momentum=0.0,
                          nesterovs_momentum=False, **common),
            X, y, seed, scale=False,
        ),
        "adam": _accuracy(MLPClassifier(solver="adam", **common), X, y, seed, scale=False),
    }


# --- decisions ----------------------------------------------------------------
# Each takes the across-seed MEAN metric per variant plus the measured band and
# returns (outcome, one-line reason, code).
#
# `code` exists because one outcome can have genuinely different meanings: a
# step-0 FAIL is either "nothing here is learnable at all" or "this needs a
# hidden layer", and telling a student the second when the first is true is a
# lie. The registry keys its plain-language wording on the code when it has one
# and falls back to the bare outcome, so a probe only names codes it needs.

def decide_linear_sufficient(metrics: dict[str, float], band: float) -> tuple[ProbeOutcome, str]:
    learnable = metrics["linear"] - metrics["majority"]
    hidden_gain = metrics["mlp"] - metrics["linear"]
    if learnable <= band:
        return ProbeOutcome.FAIL, (
            f"nothing beats the majority class (linear gain {learnable:.3f} inside the "
            f"noise band {band:.3f}), no learnable signal at this scale"
        ), "no_signal"
    if hidden_gain > band:
        return ProbeOutcome.FAIL, (
            f"a hidden layer visibly helps (+{hidden_gain:.3f} > band {band:.3f}), so "
            "this data belongs at step 1 or above"
        ), "needs_hidden_layer"
    return ProbeOutcome.PASS, (
        f"a line is genuinely enough: linear beats majority by {learnable:.3f} and the "
        f"MLP adds only {hidden_gain:.3f} (band {band:.3f})"
    ), "pass"


def decide_hidden_layer_wins(metrics: dict[str, float], band: float) -> tuple[ProbeOutcome, str]:
    hidden_gain = metrics["mlp"] - metrics["linear"]
    if hidden_gain > band:
        return ProbeOutcome.PASS, (
            f"the hidden layer buys something real: +{hidden_gain:.3f} over linear "
            f"(band {band:.3f})"
        )
    if hidden_gain < -band:
        return ProbeOutcome.FAIL, (
            f"the MLP loses to plain logistic regression by {-hidden_gain:.3f}, so "
            "no hidden-layer structure to find here"
        )
    return ProbeOutcome.UNCONFIRMED, (
        f"gap {hidden_gain:+.3f} sits inside the measured noise band {band:.3f}, so it "
        "could be built at step 0 or step 1; both shown, neither recommended over the other"
    )


def decide_adam_beats_sgd(metrics: dict[str, float], band: float) -> tuple[ProbeOutcome, str]:
    gain = metrics["adam"] - metrics["sgd"]
    if gain > band:
        return ProbeOutcome.PASS, (
            f"the optimiser visibly matters: Adam beats plain SGD by {gain:.3f} on the "
            f"same architecture and budget (band {band:.3f})"
        )
    if gain < -band:
        return ProbeOutcome.FAIL, (
            f"plain SGD matched or beat Adam ({gain:+.3f}), so this data will not show why "
            "training tricks matter"
        )
    return ProbeOutcome.UNCONFIRMED, (
        f"Adam-vs-SGD gap {gain:+.3f} inside the noise band {band:.3f}, so "
        "the optimiser difference doesn't show on this data"
    )


def sanity(value: float) -> float:
    """Guard against NaN leaking out of a degenerate fit."""
    return 0.0 if math.isnan(value) else value
