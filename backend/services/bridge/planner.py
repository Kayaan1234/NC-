"""The query planner — LLM call site 1 of 3 (bridge-plan-v3.md §"Why this is
agentic", §14).

Derives 6-10 varied search queries from the spec's capability + modality and
the learner's topic. On a replan it additionally sees which queries produced
which rejections — that feedback loop is the agentic part. Round 2 (the last
allowed) turns adaptive thinking on: by then the full rejection breakdown is
known and deciding how to reformulate is genuinely harder than the first plan
was (§14.4). Everything else about the call — budget, caching, structured
output — is llm.py's job.

The produced plan is also saved as the step's template (bridge_query_plans,
§14.6): capability and modality are properties of the spec, not the topic, so
the NEXT topic's planner call is seeded from this instead of a blank page.
"""

import logging

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.Bridge import BridgeQueryPlan
from backend.services.bridge.llm import SpendLedger, call_structured
from backend.services.bridge.registry import BridgeSpec

logger = logging.getLogger("backend.bridge.planner")

MAX_REPLANS = 2


class QueryPlan(BaseModel):
    # No Field length constraints: the structured-output endpoint rejects
    # minItems/maxItems, so the prompt asks for 6-10 and the caller slices.
    queries: list[str]


_STATIC_TEMPLATE = """You plan dataset-search queries for a learner's hobby ML project.

The project's architecture level requires data that demonstrates:
{capability}
Data modality: {modality}.

Produce 6-10 SHORT search queries (1-3 words each) for dataset search engines
(HuggingFace, Kaggle). These engines match query words against dataset NAMES,
so use name-style keywords, never sentences: the topic's own words, synonyms,
the kind of records the domain produces, and one or two broader umbrella terms.
Never include filler words like "dataset" or "data". Queries must stay about
the learner's topic — do not drift to generic ML datasets. Return JSON only."""


def plan_queries(
    db: Session,
    ledger: SpendLedger,
    spec: BridgeSpec,
    topic: str,
    round_number: int = 0,
    rejection_summary: str | None = None,
) -> list[str]:
    static = _STATIC_TEMPLATE.format(capability=spec.capability, modality=spec.modality.value)

    user_parts = [f"Topic: {topic}"]
    template = _load_template(db, spec.model_id)
    if template and round_number == 0:
        user_parts.append(
            "A previous plan for a DIFFERENT topic at this same level used this "
            f"framing strategy, as a starting point only: {template}"
        )
    if rejection_summary:
        user_parts.append(
            f"Replan round {round_number}: the previous queries were tried and every "
            f"candidate was rejected. Rejection breakdown: {rejection_summary}. "
            "Reformulate in light of this — different vocabulary, different data shapes."
        )

    plan = call_structured(
        db, ledger, "query_planner",
        static_instructions=static,
        user_text="\n".join(user_parts),
        response_model=QueryPlan,
        # Round 2 is the one place in the pipeline where harder reasoning is
        # likely to change the outcome; rounds 0-1 stay thinking-off.
        thinking="adaptive" if round_number >= MAX_REPLANS else None,
    )
    queries = [q.strip() for q in plan.queries if q.strip()][:10]
    if round_number == 0:
        _save_template(db, spec.model_id, queries)
    logger.info("planned %d queries (round %d)", len(queries), round_number)
    return queries


def _load_template(db: Session, model_id: str) -> list[str] | None:
    row = db.execute(
        select(BridgeQueryPlan).where(BridgeQueryPlan.model_id == model_id)
    ).scalars().first()
    return row.plan.get("queries") if row else None


def _save_template(db: Session, model_id: str, queries: list[str]) -> None:
    row = db.execute(
        select(BridgeQueryPlan).where(BridgeQueryPlan.model_id == model_id)
    ).scalars().first()
    if row is None:
        db.add(BridgeQueryPlan(model_id=model_id, plan={"queries": queries}))
    else:
        row.plan = {"queries": queries}
    db.commit()
