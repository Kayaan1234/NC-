"""Topic slug normalisation — a cost-control mechanism, not just a cache key.

Two learner-entered topics that normalise to the same slug hit the same
(topic_slug, model_id) verdict and the same (topic_slug, modality) pool, so
"Morris Dancing" and "morris dancing " never pay for two pipeline runs
(bridge-plan-v3.md §14.6).
"""

import re
import unicodedata

_MAX_SLUG = 80


def slugify_topic(topic: str) -> str:
    """Lowercase, ASCII-fold, collapse everything non-alphanumeric to single
    hyphens. Deliberately no stemming — "birds" and "bird" staying distinct is
    an acceptable cache miss; conflating "training" and "train" is not."""
    value = unicodedata.normalize("NFKD", topic).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:_MAX_SLUG].rstrip("-")
