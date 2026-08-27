"""The API feasibility path (bridge-plan-v3.md §7) — reached when no usable
static dataset survived the gates.

Everything here is deterministic: match the topic against the curated registry
(api_registry.json — discovery from a known set, verification live; open-web
API hunting produces hallucinated endpoints), probe the matched APIs' public
endpoints once, and turn documented rate limits into wall-clock collection
days — which is often the real cost, and nobody else reports it.

records_needed comes from the modality's Gate 3 floor, so this path generalises
with the rest of the pipeline.
"""

import json
import logging
import math
import re
from pathlib import Path

from backend.services.bridge.gates import SCALE_READINGS
from backend.services.bridge.registry import BridgeSpec
from backend.services.bridge.tools import probe_api_endpoint

logger = logging.getLogger("backend.bridge.api_path")

_REGISTRY_PATH = Path(__file__).parent / "api_registry.json"
_registry_cache: list[dict] | None = None


def _registry() -> list[dict]:
    global _registry_cache
    if _registry_cache is None:
        _registry_cache = json.loads(_REGISTRY_PATH.read_text())["apis"]
    return _registry_cache


def _match_score(topic: str, entry: dict, modality: str) -> int:
    """Keyword overlap between the topic's words and the entry's keywords.
    Deliberately dumb — the registry is small and curated, and a fuzzy matcher
    would only manufacture confidence."""
    if modality not in entry["modalities"]:
        return 0
    topic_words = set(re.findall(r"[a-z]+", topic.lower()))
    score = 0
    for keyword in entry["keywords"]:
        keyword_words = set(keyword.split())
        if keyword_words <= topic_words or keyword in topic.lower():
            score += 2
        elif keyword_words & topic_words:
            score += 1
    return score


def assess_api_path(topic: str, spec: BridgeSpec, max_candidates: int = 2) -> list[dict]:
    """The §7 checks for the best-matching registry entries: auth, live response
    shape, rate-limit → collection days, terms. Empty list = the registry has
    nothing for this topic (a fact the verdict states plainly)."""
    records_needed = SCALE_READINGS[spec.modality].floor
    scored = sorted(
        ((entry, _match_score(topic, entry, spec.modality.value)) for entry in _registry()),
        key=lambda pair: pair[1],
        reverse=True,
    )
    assessments = []
    for entry, score in scored[:max_candidates]:
        if score <= 0:
            break
        live = probe_api_endpoint(entry["probe_url"])
        per_day = entry["rate_limit_per_day"]
        assessments.append({
            "name": entry["name"],
            "docs_url": entry["docs_url"],
            "auth": entry["auth"],                       # kills more hobby projects than anything else
            "reachable": live.get("reachable", False),
            "responds_json": live.get("json", False),
            "rate_limit_per_day": per_day,
            "records_needed": records_needed,
            # Assumes one record per request — the conservative reading; many
            # APIs return pages, which only shortens this.
            "estimated_collection_days": math.ceil(records_needed / per_day),
            "terms_note": entry["terms_note"],
            "match_score": score,
        })
    return assessments
