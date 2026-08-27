"""Gate 4's runner: executes one step's probe against one candidate's rows.

Enforces the ProbeSpec budget (row cap, wall clock) and measures the noise band
across the spec's seeds before letting decide() speak. The report it returns is
a plain dict — every number the verdict or the critic will ever cite about the
probe comes from this record and nowhere else.

Branches only on `spec.probe is None`; it never names a step.
"""

import logging
import time

from backend.services.bridge.probes import PROBES
from backend.services.bridge.probes.tabular import prepare_xy, sanity
from backend.services.bridge.registry import BridgeSpec, ProbeOutcome

logger = logging.getLogger("backend.bridge.probe")


def run_probe(spec: BridgeSpec, rows: list[dict]) -> dict:
    """Fit the spec's named variants across its seeds and decide.

    Never raises for a data-shaped problem: an unusable candidate yields an
    UNCONFIRMED report with the reason stated, because "we couldn't measure it"
    is a legitimate verdict input and an exception is not.
    """
    assert spec.probe is not None, "run_probe called for a probe-less spec"
    probe_spec = spec.probe
    probe = PROBES[probe_spec.probe_id]

    report: dict = {
        "probe_id": probe_spec.probe_id,
        "metric": probe_spec.metric,
        "seeds": list(probe_spec.seeds),
        "row_cap": probe_spec.row_cap,
    }

    xy = prepare_xy(rows[: probe_spec.row_cap])
    if xy is None:
        report.update(
            outcome=ProbeOutcome.UNCONFIRMED.value,
            code="no_label",
            reason=(
                "no usable label/feature structure identifiable in the sample rows, "
                "so deriving a target is the first design decision of this project"
            ),
            rows_used=0,
        )
        return report
    X, y = xy
    report["rows_used"] = int(len(X))

    started = time.monotonic()
    per_seed: dict[int, dict[str, float]] = {}
    for seed in probe_spec.seeds:
        elapsed = time.monotonic() - started
        if elapsed > probe_spec.wall_clock_seconds:
            # The kill switch. A candidate too slow to probe within budget is
            # not measured — not half-measured.
            report.update(
                outcome=ProbeOutcome.UNCONFIRMED.value,
                code="too_slow",
                reason=(
                    f"probe exceeded its wall-clock budget "
                    f"({elapsed:.0f}s > {probe_spec.wall_clock_seconds}s) before all seeds ran"
                ),
                elapsed_seconds=round(elapsed, 1),
            )
            return report
        try:
            per_seed[seed] = {k: sanity(v) for k, v in probe.fit_variants(X, y, seed).items()}
        except Exception as exc:  # noqa: BLE001 — a sklearn failure is a data fact, not a bug
            logger.warning("probe %s failed on seed %d: %s", probe_spec.probe_id, seed, exc)
            report.update(
                outcome=ProbeOutcome.UNCONFIRMED.value,
                code="fit_failed",
                # Developer text, deliberately. It is the raw exception and it
                # belongs in the evidence disclosure, never in the sentence a
                # student reads — plain.fit_line keys off the code above for
                # that, and only ever falls back to prose it wrote itself.
                reason=f"variant fit failed on this data: {exc}",
            )
            return report

    variants = list(next(iter(per_seed.values())).keys())
    means = {
        v: sum(per_seed[s][v] for s in probe_spec.seeds) / len(probe_spec.seeds)
        for v in variants
    }
    # The MEASURED noise band: the widest across-seed spread any single variant
    # shows. decide() must not let a gap inside this band pick a side.
    band = max(
        max(per_seed[s][v] for s in probe_spec.seeds)
        - min(per_seed[s][v] for s in probe_spec.seeds)
        for v in variants
    )

    # decide() may return (outcome, reason) or (outcome, reason, code). The
    # code distinguishes situations that share an outcome but mean different
    # things to a reader; probes that have no such split just return two.
    decision = probe.decide(means, band)
    outcome, reason = decision[0], decision[1]
    code = decision[2] if len(decision) > 2 else outcome.value
    report.update(
        code=code,
        per_seed={str(s): per_seed[s] for s in probe_spec.seeds},
        means={k: round(v, 4) for k, v in means.items()},
        noise_band=round(band, 4),
        outcome=outcome.value,
        reason=reason,
        elapsed_seconds=round(time.monotonic() - started, 1),
    )
    return report
