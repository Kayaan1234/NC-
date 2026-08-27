"""Scouts: turn one search query into candidate dicts (bridge-plan-v3.md §"Two
surfaces" and §10).

Three recall channels behind one interface:

  - HFScout      keyword search over the HuggingFace Hub (no auth)
  - KaggleScout  keyword search via the authenticated Kaggle SDK — activates
                 only when KAGGLE_USERNAME/KAGGLE_KEY are configured, and skips
                 gracefully (logged, never fatal) otherwise
  - vector recall lives in card_index.py, not here — it searches cards already
                 embedded, alongside (never instead of) keyword search

A candidate is a plain JSON-able dict: source, dataset_id, url, title,
description, license, downloads, total_bytes — exactly what the pool stores and
the gates read.
"""

import logging

from backend.services.bridge.tools import _kaggle_env, kaggle_available

logger = logging.getLogger("backend.bridge.scouts")

SEARCH_LIMIT_PER_QUERY = 10


_STOPWORDS = frozenset({"dataset", "datasets", "data", "the", "a", "an", "of", "for", "with", "and"})


class HFScout:
    source = "hf"

    @staticmethod
    def available() -> bool:
        return True

    @classmethod
    def search(cls, query: str, limit: int = SEARCH_LIMIT_PER_QUERY) -> list[dict]:
        """HF's `search` matches EVERY word against the repo name (verified
        live: "wine quality" hits, "wine quality dataset" returns zero), so a
        phrase that finds nothing degrades word by word before giving up."""
        words = [w for w in query.lower().split() if w not in _STOPWORDS]
        attempts = [" ".join(words[:n]) for n in range(len(words), 0, -1)]
        for attempt in attempts or [query]:
            candidates = cls._search_once(attempt, limit)
            if candidates:
                return candidates
        return []

    @staticmethod
    def _search_once(query: str, limit: int) -> list[dict]:
        from huggingface_hub import HfApi

        candidates = []
        try:
            for info in HfApi().list_datasets(search=query, sort="downloads", limit=limit):
                tags = list(info.tags or [])
                license_slug = next(
                    (t.split(":", 1)[1] for t in tags if t.startswith("license:")), None
                )
                candidates.append({
                    "source": "hf",
                    "dataset_id": info.id,
                    "url": f"https://huggingface.co/datasets/{info.id}",
                    "title": info.id,
                    "description": (getattr(info, "description", None) or "")[:500],
                    "license": license_slug,
                    "downloads": getattr(info, "downloads", None),
                    "total_bytes": None,  # filled by inspection
                    "tags": tags[:20],
                })
        except Exception as exc:  # noqa: BLE001 — a failed search is an empty result, not a dead run
            logger.warning("HF search failed for %r: %s", query, exc)
        return candidates


class KaggleScout:
    source = "kaggle"

    @staticmethod
    def available() -> bool:
        return kaggle_available()

    @staticmethod
    def search(query: str, limit: int = SEARCH_LIMIT_PER_QUERY) -> list[dict]:
        if not kaggle_available():
            return []
        _kaggle_env()
        candidates = []
        try:
            from kagglesdk import KaggleClient
            from kagglesdk.datasets.types.dataset_api_service import ApiListDatasetsRequest

            with KaggleClient() as client:
                request = ApiListDatasetsRequest()
                request.search = query
                request.page_size = limit
                response = client.datasets.dataset_api_client.list_datasets(request)
                for item in (response.datasets or [])[:limit]:
                    ref = getattr(item, "ref", None) or f"{item.owner_slug}/{item.dataset_slug}"
                    candidates.append({
                        "source": "kaggle",
                        "dataset_id": ref,
                        "url": f"https://www.kaggle.com/datasets/{ref}",
                        "title": getattr(item, "title", ref) or ref,
                        "description": (getattr(item, "subtitle", None) or "")[:500],
                        "license": _normalise_kaggle_license(getattr(item, "license_name", None)),
                        "downloads": getattr(item, "download_count", None),
                        "total_bytes": getattr(item, "total_bytes", None),
                        "tags": [],
                    })
        except Exception as exc:  # noqa: BLE001
            logger.warning("Kaggle search failed for %r: %s", query, exc)
        return candidates


# Kaggle reports licenses as display names, and its vaguest values are the
# common ones: "Other (specified in description)" and "Data files © Original
# Authors" both mean "read the page yourself". Those must resolve to None so
# Gate 1 rejects them, rather than passing through as a slug nothing matches.
_KAGGLE_LICENSE_MAP = {
    "cc0: public domain": "cc0-1.0",
    "cc0-1.0": "cc0-1.0",
    "cc by 4.0": "cc-by-4.0",
    "cc by-sa 4.0": "cc-by-sa-4.0",
    "cc by-sa 3.0": "cc-by-sa-3.0",
    "attribution 4.0 international (cc by 4.0)": "cc-by-4.0",
    "attribution-sharealike 4.0 international (cc by-sa 4.0)": "cc-by-sa-4.0",
    "mit": "mit",
    "apache 2.0": "apache-2.0",
    "gpl 2": "gpl-2.0",
    "database: open database, contents: database contents": "odbl",
    "database: open database, contents: original authors": "odbl",
    "odbl-1.0": "odbl",
    "u.s. government works": "cc0-1.0",
    "community data license agreement - permissive - version 1.0": "cdla-permissive-1.0",
    "community data license agreement - sharing - version 1.0": "cdla-sharing-1.0",
}

# Substrings that mean "no clear license", whatever else the string says.
_KAGGLE_LICENSE_UNCLEAR = ("other", "unknown", "©", "copyright", "specified in description")


def _normalise_kaggle_license(name: str | None) -> str | None:
    """Kaggle display name to the SPDX-ish slug Gate 1's allowlist speaks."""
    if not name:
        return None
    cleaned = name.strip().lower()
    if any(marker in cleaned for marker in _KAGGLE_LICENSE_UNCLEAR):
        return None
    return _KAGGLE_LICENSE_MAP.get(cleaned, cleaned)


def active_scouts() -> list:
    scouts: list = [HFScout]
    if KaggleScout.available():
        scouts.append(KaggleScout)
    else:
        logger.info("Kaggle scout inactive (no KAGGLE_USERNAME/KAGGLE_KEY)")
    return scouts
