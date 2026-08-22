"""Gates 1-3: license, loadable, scale (bridge-plan-v3.md §5).

Ordered cheapest-first and entirely deterministic — no LLM anywhere in this
module. Gates evaluate RECORDS the tools fetched (a candidate dict, an
inspection dict); they never make network calls themselves, which keeps them
trivially testable and keeps every rejection reason traceable to data a tool
actually returned (the critic asserts exactly that).

Gates 1-2 are universal. Gate 3 is per-modality: "enough rows, small enough for
a laptop" is a tabular sentence, so each modality declares its own reading via
SCALE_READINGS. A modality in use with no entry here fails the boot
(check_bridge_registry), not the first verdict.

Candidate dict keys (produced by the scouts, stored in the pool):
  source, dataset_id, url, title, description, license (SPDX slug or None),
  downloads, tags
Inspection dict keys (produced by tools.inspect_dataset):
  valid (bool), splits (list), sample_rows (list), stats (per-modality numbers),
  partial (bool — datasets-server may still be computing size for huge sets)
"""

from dataclasses import dataclass, field
from typing import Callable

from backend.services.bridge.registry import Modality


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str                 # one line, shown in the verdict's rejection groups
    details: dict = field(default_factory=dict)


# SPDX-ish license slugs (HF's license tags) we can honestly point a learner at.
# Non-commercial and no-derivative variants are rejected as ambiguous for a
# project someone may publish results from — the verdict still says "check the
# terms before publishing" even for these. We never mirror or re-host either way.
LICENSE_ALLOWLIST = frozenset({
    "mit", "apache-2.0", "bsd", "bsd-2-clause", "bsd-3-clause", "isc",
    "cc0-1.0", "cc-by-2.0", "cc-by-2.5", "cc-by-3.0", "cc-by-4.0",
    "cc-by-sa-3.0", "cc-by-sa-4.0",
    "odc-by", "odbl", "pddl",
    "cdla-permissive-1.0", "cdla-permissive-2.0", "cdla-sharing-1.0",
    "gpl-2.0", "gpl-3.0", "lgpl-3.0", "agpl-3.0",
    "unlicense", "wtfpl", "openrail",
})


def gate1_license(candidate: dict) -> GateResult:
    """Universal. Absent or unrecognised is a rejection, not a shrug — an
    unlicensed dataset can't be recommended to someone who may publish."""
    license_slug = (candidate.get("license") or "").strip().lower()
    if not license_slug:
        return GateResult(False, "no license declared")
    if license_slug not in LICENSE_ALLOWLIST:
        return GateResult(False, f"license not usable ({license_slug})",
                          {"license": license_slug})
    return GateResult(True, "license ok", {"license": license_slug})


def gate2_loadable(inspection: dict) -> GateResult:
    """Universal. Defined splits and the inspection endpoint actually returning
    rows — dead datasets are common on both sources."""
    if not inspection.get("valid"):
        return GateResult(False, "dataset viewer reports it unusable")
    if not inspection.get("splits"):
        return GateResult(False, "no defined splits")
    if not inspection.get("sample_rows"):
        return GateResult(False, "inspection returned no rows")
    return GateResult(True, "loadable")


@dataclass(frozen=True)
class ScaleReading:
    """One modality's meaning of "enough to learn from, small enough for a
    laptop". `floor` doubles as §7's records_needed for the API path's
    collection-time arithmetic."""

    unit: str                       # what scale is measured in, verbatim in verdicts
    floor: int                      # minimum usable examples
    laptop_ceiling_bytes: int       # above this: pass WITH a documented-subset note
    evaluate: Callable[[dict], GateResult]


def _eval_tabular(stats: dict) -> GateResult:
    rows = stats.get("num_rows")
    cols = stats.get("num_columns")
    size = stats.get("num_bytes")
    if rows is None:
        return GateResult(False, "row count unavailable")
    if rows < _TABULAR_FLOOR:
        return GateResult(False, f"too few rows ({rows}) to learn from",
                          {"num_rows": rows})
    if cols is not None and cols < 2:
        return GateResult(False, "fewer than two columns, nothing to predict from")
    details = {"num_rows": rows, "num_columns": cols, "num_bytes": size}
    if size is not None and size > _TABULAR_CEILING:
        # Too-large is never terminal — a documented subset is a valid answer.
        return GateResult(True, "large, so work from a documented subset", details)
    return GateResult(True, "scale ok", details)


def _eval_image(stats: dict) -> GateResult:
    count = stats.get("num_rows")
    size = stats.get("num_bytes")
    if count is None:
        return GateResult(False, "image count unavailable")
    if count < _IMAGE_FLOOR:
        return GateResult(False, f"too few images ({count})", {"num_rows": count})
    details = {"num_rows": count, "num_bytes": size}
    if size is not None and size > _IMAGE_CEILING:
        return GateResult(True, "large, so work from a documented subset", details)
    return GateResult(True, "scale ok", details)


def _eval_sequence(stats: dict) -> GateResult:
    rows = stats.get("num_rows")
    if rows is None:
        return GateResult(False, "series/step count unavailable")
    if rows < _SEQUENCE_FLOOR:
        return GateResult(False, f"too few sequence rows ({rows})", {"num_rows": rows})
    details = {"num_rows": rows, "num_bytes": stats.get("num_bytes")}
    return GateResult(True, "scale ok", details)


def _eval_text_pair(stats: dict) -> GateResult:
    pairs = stats.get("num_rows")
    if pairs is None:
        return GateResult(False, "pair count unavailable")
    if pairs < _TEXT_PAIR_FLOOR:
        return GateResult(False, f"too few sentence pairs ({pairs}) for a parallel corpus",
                          {"num_rows": pairs})
    details = {"num_rows": pairs, "num_bytes": stats.get("num_bytes")}
    if (stats.get("num_bytes") or 0) > _TEXT_PAIR_CEILING:
        return GateResult(True, "large, so work from a documented subset", details)
    return GateResult(True, "scale ok", details)


_TABULAR_FLOOR = 500
_TABULAR_CEILING = 2 * 1024**3
_IMAGE_FLOOR = 1000
_IMAGE_CEILING = 5 * 1024**3
_SEQUENCE_FLOOR = 1000
_TEXT_PAIR_FLOOR = 10_000
_TEXT_PAIR_CEILING = 5 * 1024**3

SCALE_READINGS: dict[Modality, ScaleReading] = {
    Modality.TABULAR: ScaleReading(
        unit="rows / columns / file size",
        floor=_TABULAR_FLOOR,
        laptop_ceiling_bytes=_TABULAR_CEILING,
        evaluate=_eval_tabular,
    ),
    Modality.IMAGE_GRID: ScaleReading(
        unit="image count / resolution / total bytes",
        floor=_IMAGE_FLOOR,
        laptop_ceiling_bytes=_IMAGE_CEILING,
        evaluate=_eval_image,
    ),
    Modality.SEQUENCE: ScaleReading(
        unit="series count / length distribution",
        floor=_SEQUENCE_FLOOR,
        laptop_ceiling_bytes=_TABULAR_CEILING,
        evaluate=_eval_sequence,
    ),
    Modality.TEXT_PAIR: ScaleReading(
        unit="sentence pairs / vocabulary / length ratio",
        floor=_TEXT_PAIR_FLOOR,
        laptop_ceiling_bytes=_TEXT_PAIR_CEILING,
        evaluate=_eval_text_pair,
    ),
    # AUDIO deliberately absent: no step uses it yet, and adding the reading is
    # part of introducing the modality (bridge-plan-v3.md §16), not before.
}


def gate3_scale(inspection: dict, modality: Modality) -> GateResult:
    stats = inspection.get("stats") or {}
    if inspection.get("partial"):
        # datasets-server is still computing sizes for a huge dataset; the
        # numbers below would understate it. Say so instead of judging on them.
        return GateResult(False, "size statistics still computing (dataset likely very large)")
    return SCALE_READINGS[modality].evaluate(stats)
