"""The relevance judge — LLM call site 2 of 3 (bridge-plan-v3.md §14).

A binary classification of one candidate card against the topic and the
modality: keyword search returns plenty of datasets that merely mention a word.
This is the highest-VOLUME call site (once per scout hit), which is why it runs
the cheapest tier with a tiny output budget, why the instruction block is
identical across every candidate (prompt-cached — only the card text bills
fresh), and why the spend ceiling is checked before every single call.

The step's capability is deliberately NOT in the prompt. Given it, the judge
rejected datasets for not *demonstrating* it ("not about linear decision
boundaries") — 37/38 on-topic pokemon candidates, the canonical one included.
Whether data shows a capability is the probe's question, answered on real rows;
a card can't answer it. And the pool the judge filters is keyed by
(topic, MODALITY), shared across steps, so a step-specific judgement would leak
one step's criteria into another's candidates.
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

Required modality: {modality}.

Judge ONLY two things from the card text: is the dataset really about the topic,
and could its records plausibly be {modality} data? Do NOT judge whether the data
suits any particular model or would show any machine-learning property; a later
automated test measures that on the real rows. Licensing, size and quality are
also checked elsewhere.

A dataset that merely mentions the topic's words while being about something
else is NOT relevant. Cards are often thin: when the name clearly matches the
topic and nothing contradicts the modality, lean relevant.
Return JSON: relevant (true/false) and a one-line reason."""


def judge_relevance(
    db: Session,
    ledger: SpendLedger,
    spec: BridgeSpec,
    topic: str,
    candidate: dict,
) -> RelevanceJudgment:
    static = _STATIC_TEMPLATE.format(modality=spec.modality.value)
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
