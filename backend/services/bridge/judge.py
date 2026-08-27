"""The relevance judge — LLM call site 2 of 3 (bridge-plan-v3.md §14).

A binary classification of one candidate card against the topic and the step's
capability: keyword search returns plenty of datasets that merely mention a
word. This is the highest-VOLUME call site (once per scout hit), which is why
it runs the cheapest tier with a tiny output budget, why the instruction block
is identical across every candidate (prompt-cached — only the card text bills
fresh), and why the spend ceiling is checked before every single call.
"""

import logging

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.services.bridge.llm import SpendLedger, call_structured
from backend.services.bridge.registry import BridgeSpec

logger = logging.getLogger("backend.bridge.judge")


class RelevanceJudgment(BaseModel):
    relevant: bool
    reason: str  # one line; the tiny output budget is the real cap


_STATIC_TEMPLATE = """You judge whether one dataset is genuinely about a learner's topic.

The learner wants data that can demonstrate:
{capability}
Required modality: {modality}.

Judge ONLY semantic topic relevance and plausible modality from the card text —
licensing, size and quality are checked elsewhere. A dataset that merely
mentions the topic's words while being about something else is NOT relevant.
Return JSON: relevant (true/false) and a one-line reason."""


def judge_relevance(
    db: Session,
    ledger: SpendLedger,
    spec: BridgeSpec,
    topic: str,
    candidate: dict,
) -> RelevanceJudgment:
    static = _STATIC_TEMPLATE.format(capability=spec.capability, modality=spec.modality.value)
    card = (
        f"Topic: {topic}\n"
        f"Dataset: {candidate['dataset_id']} ({candidate['source']})\n"
        f"Title: {candidate.get('title')}\n"
        f"Description: {(candidate.get('description') or '(none)')[:800]}\n"
        f"Tags: {', '.join(candidate.get('tags') or [])[:200]}"
    )
    return call_structured(
        db, ledger, "relevance_judge",
        static_instructions=static,
        user_text=card,
        response_model=RelevanceJudgment,
    )
