"""Live dataset inspection: the tool layer between the scouts and the gates.

Gates evaluate records; THIS module is what fetches those records, so every
number a verdict cites traces back to a response captured here (the critic's
grounding rule). HuggingFace datasets are inspected through the public
datasets-server REST API (no auth needed); Kaggle datasets get a lighter
inspection through the authenticated SDK, and probe rows only when the download
is small enough to be safe on the worker.

All HTTP goes through one retrying GET with tight timeouts — a hung external
API must never hold a job past its heartbeat.
"""

import csv
import logging
import os
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.core.config import settings

logger = logging.getLogger("backend.bridge.tools")

DATASETS_SERVER = "https://datasets-server.huggingface.co"
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Kaggle probing means downloading the dataset (there is no rows API); above
# this size the candidate stays gated-but-unprobed rather than risking the
# worker's disk and wall clock on a large pull.
KAGGLE_DOWNLOAD_CAP_BYTES = 50 * 1024 * 1024

# Column names that suggest a ready-made target; mirrored by the probe's
# label detection (probes/tabular.py has its own richer heuristic).
LABEL_NAMES = ("label", "target", "class", "y", "outcome", "result")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
def _get(path: str, params: dict) -> dict | None:
    """GET a datasets-server endpoint. None for any non-200 — a dead dataset is
    a data fact for Gate 2, not an exception."""
    response = httpx.get(f"{DATASETS_SERVER}{path}", params=params, timeout=_TIMEOUT)
    if response.status_code != 200:
        return None
    return response.json()


def inspect_hf_dataset(dataset_id: str) -> dict:
    """The full inspection record for one HF dataset: validity, splits, sample
    rows, and per-modality scale/rubric statistics. Cheap — four GETs, no
    download."""
    inspection: dict = {"valid": False, "splits": [], "sample_rows": [], "stats": {}, "partial": False}

    is_valid = _get("/is-valid", {"dataset": dataset_id})
    if not is_valid or not (is_valid.get("viewer") or is_valid.get("preview")):
        return inspection
    inspection["valid"] = True

    splits_response = _get("/splits", {"dataset": dataset_id})
    splits = (splits_response or {}).get("splits", [])
    inspection["splits"] = [{"config": s["config"], "split": s["split"]} for s in splits]
    if not splits:
        return inspection

    # Prefer a train split for sampling; any split proves loadability.
    chosen = next((s for s in splits if s["split"] == "train"), splits[0])
    config, split = chosen["config"], chosen["split"]
    inspection["config"], inspection["split"] = config, split

    first_rows = _get("/first-rows", {"dataset": dataset_id, "config": config, "split": split})
    if first_rows:
        inspection["sample_rows"] = [r["row"] for r in first_rows.get("rows", [])]

    size = _get("/size", {"dataset": dataset_id})
    stats: dict = {}
    if size:
        inspection["partial"] = bool(size.get("partial"))
        dataset_size = (size.get("size") or {}).get("dataset") or {}
        stats["num_rows"] = dataset_size.get("num_rows")
        stats["num_bytes"] = dataset_size.get("num_bytes_original_files")
        stats["num_columns"] = dataset_size.get("num_columns")

    stats["num_splits"] = len({s["split"] for s in splits})
    _enrich_from_statistics(dataset_id, config, split, stats)
    if inspection["sample_rows"]:
        columns = list(inspection["sample_rows"][0].keys())
        stats.setdefault("num_columns", len(columns))
        stats["has_label_column"] = any(c.lower() in LABEL_NAMES for c in columns)
    inspection["stats"] = stats
    return inspection


def _enrich_from_statistics(dataset_id: str, config: str, split: str, stats: dict) -> None:
    """Fold /statistics into the rubric inputs where the endpoint has them:
    null fraction, class count and balance, categorical cardinality. Best
    effort — many datasets simply don't have statistics computed."""
    response = _get("/statistics", {"dataset": dataset_id, "config": config, "split": split})
    if not response:
        return
    columns = response.get("statistics", [])
    if not columns:
        return

    nan_fractions = [
        c["column_statistics"].get("nan_proportion", 0.0)
        for c in columns
        if isinstance(c.get("column_statistics"), dict)
    ]
    if nan_fractions:
        stats["null_fraction"] = round(sum(nan_fractions) / len(nan_fractions), 4)

    stats["num_text_columns"] = sum(1 for c in columns if c.get("column_type") == "string_text")
    stats["num_numeric_columns"] = sum(1 for c in columns if c.get("column_type") in ("int", "float"))

    cardinalities = []
    for c in columns:
        cs = c.get("column_statistics") or {}
        frequencies = cs.get("frequencies")
        if isinstance(frequencies, dict) and frequencies:
            cardinalities.append(len(frequencies))
            if c.get("column_name", "").lower() in LABEL_NAMES:
                total = sum(frequencies.values()) or 1
                stats["num_classes"] = len(frequencies)
                stats["minority_class_fraction"] = round(min(frequencies.values()) / total, 4)
    if cardinalities:
        stats["max_category_cardinality"] = max(cardinalities)


def fetch_hf_rows(dataset_id: str, config: str, split: str, count: int) -> list[dict]:
    """Paginate /rows (max 100 per call) up to `count` — the probe's data
    supply. Stops early on any failed page; the probe reports what it got."""
    rows: list[dict] = []
    offset = 0
    while len(rows) < count:
        page = _get("/rows", {
            "dataset": dataset_id, "config": config, "split": split,
            "offset": offset, "length": min(100, count - len(rows)),
        })
        if not page or not page.get("rows"):
            break
        rows.extend(r["row"] for r in page["rows"])
        offset += len(page["rows"])
        if len(page["rows"]) < 100:
            break
    return rows


# --- Kaggle -------------------------------------------------------------------

def kaggle_available() -> bool:
    return bool(settings.KAGGLE_USERNAME and settings.KAGGLE_KEY)


def _kaggle_env() -> None:
    """kagglehub/kagglesdk read credentials from the environment; project
    convention keeps them in Settings, so export just-in-time."""
    os.environ.setdefault("KAGGLE_USERNAME", settings.KAGGLE_USERNAME or "")
    os.environ.setdefault("KAGGLE_KEY", settings.KAGGLE_KEY or "")


def inspect_kaggle_dataset(candidate: dict) -> dict:
    """Kaggle has no free inspection API, so this is deliberately lighter: the
    search result's own metadata provides scale, and loadability means "the
    dataset reports files". Sample rows come only from a capped download."""
    stats = {
        "num_bytes": candidate.get("total_bytes"),
        "num_rows": None,  # unknown without a download
    }
    inspection = {
        "valid": True,
        "splits": [{"config": "default", "split": "all"}],
        "sample_rows": [],
        "stats": stats,
        "partial": False,
    }
    if (candidate.get("total_bytes") or 0) <= KAGGLE_DOWNLOAD_CAP_BYTES:
        # Read enough rows to clear any modality's scale floor honestly — the
        # file is already downloaded, so more rows cost nothing extra.
        rows = fetch_kaggle_rows(candidate["dataset_id"], count=10_001)
        inspection["sample_rows"] = rows[:100]
        if rows:
            stats["num_rows"] = len(rows)
            columns = list(rows[0].keys())
            stats["num_columns"] = len(columns)
            stats["has_label_column"] = any(c.lower() in LABEL_NAMES for c in columns)
    return inspection


def fetch_kaggle_rows(dataset_id: str, count: int) -> list[dict]:
    """Download a small Kaggle dataset and read rows from its first CSV. Only
    called under KAGGLE_DOWNLOAD_CAP_BYTES; returns [] on any failure — an
    unprobeable candidate is a fact, not an error."""
    if not kaggle_available():
        return []
    _kaggle_env()
    try:
        import kagglehub

        path = Path(kagglehub.dataset_download(dataset_id))
        csv_files = sorted(path.rglob("*.csv"))
        if not csv_files:
            return []
        with open(csv_files[0], newline="", errors="replace") as f:
            reader = csv.DictReader(f)
            return [row for _, row in zip(range(count), reader)]
    except Exception as exc:  # noqa: BLE001 — degrade to "not probeable"
        logger.warning("kaggle download failed for %s: %s", dataset_id, exc)
        return []


def probe_api_endpoint(base_url: str) -> dict:
    """§7's one live unauthenticated probe: does the base URL answer, and does
    it speak JSON? Deterministic; the caller interprets."""
    try:
        response = httpx.get(base_url, timeout=_TIMEOUT, follow_redirects=True)
        content_type = response.headers.get("content-type", "")
        return {
            "reachable": True,
            "status_code": response.status_code,
            "json": "json" in content_type,
        }
    except httpx.HTTPError as exc:
        return {"reachable": False, "error": str(exc)}
