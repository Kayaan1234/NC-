"""The single Anthropic entry point for the pipeline's three LLM call sites.

Everything §14 demands about a paid call happens HERE, once, rather than at
each call site:

  - the site's LLMCallBudget sets max_tokens in the request itself (§14.1)
  - the static instruction block is marked cacheable; only per-candidate text
    is fresh input (§14.3)
  - extended thinking is off unless the caller explicitly asks (§14.4) — note
    Sonnet 5 runs ADAPTIVE thinking when the param is omitted, so "off" must be
    an explicit {"type": "disabled"}
  - output is schema-constrained via output_config json_schema, then validated
    into the caller's Pydantic model — no regex parsing, no retry-on-parse loop
    (§14.5)
  - byte-identical requests are served from bridge_llm_cache for free (§14.6),
    which also bounds duplicate spend from the queue's at-least-once delivery
  - the running spend is checked against the per-verdict ceiling BEFORE the
    call is dispatched, not after (§14.8)

Worker-only: the web image ships no anthropic SDK.
"""

import hashlib
import json
import logging
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.Bridge import BridgeJob, BridgeLLMCache
from backend.services.bridge import tracing
from backend.services.bridge.registry import LLM_BUDGETS, LLMCallBudget

logger = logging.getLogger("backend.bridge.llm")

# USD per 1M tokens, Anthropic first-party rates as of 2026-08-20. Cache reads
# bill at ~0.1x input, cache writes at ~1.25x. Voyage is input-only. If a model
# tier changes, update this table and the LLM_BUDGETS entry together.
PRICES_PER_MTOK = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "voyage-4-lite": {"input": 0.02, "output": 0.0},
}
_CACHE_READ_MULT = 0.1
_CACHE_WRITE_MULT = 1.25


class BudgetExceeded(Exception):
    """Raised BEFORE a paid call once the run's ceiling is reached. The pipeline
    turns this into an honest partial-evidence failure, never a stack trace."""


class SpendLedger:
    """The running per-run spend counter, persisted on the job row so the daily
    cap can be computed as a SUM over bridge_jobs."""

    def __init__(self, db: Session, job: BridgeJob) -> None:
        self._db = db
        self._job = job
        self.ceiling = Decimal(str(settings.BRIDGE_VERDICT_SPEND_CEILING_USD))

    @property
    def spent(self) -> Decimal:
        return Decimal(self._job.cost_usd or 0)

    def check(self, about_to_spend_on: str) -> None:
        """Call before dispatching a paid batch — this is the circuit breaker."""
        if self.spent >= self.ceiling:
            raise BudgetExceeded(
                f"per-verdict spend ceiling ${self.ceiling} reached before {about_to_spend_on} "
                f"(spent ${self.spent})"
            )

    def charge(self, cost_usd: float) -> None:
        self._job.cost_usd = self.spent + Decimal(str(round(cost_usd, 6)))
        self._db.commit()


def cost_from_usage(model: str, usage: dict) -> float:
    prices = PRICES_PER_MTOK[model]
    return (
        usage.get("input_tokens", 0) * prices["input"]
        + usage.get("output_tokens", 0) * prices["output"]
        + usage.get("cache_read_input_tokens", 0) * prices["input"] * _CACHE_READ_MULT
        + usage.get("cache_creation_input_tokens", 0) * prices["input"] * _CACHE_WRITE_MULT
    ) / 1_000_000


def _cache_key(call_site: str, model: str, request: dict) -> str:
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{call_site}|{model}|{canonical}".encode()).hexdigest()


def cache_get(db: Session, key: str) -> BridgeLLMCache | None:
    return db.query(BridgeLLMCache).filter(BridgeLLMCache.cache_key == key).first()


def cache_put(db: Session, key: str, call_site: str, model: str,
              response: dict, usage: dict) -> None:
    if cache_get(db, key) is None:
        db.add(BridgeLLMCache(cache_key=key, call_site=call_site, model=model,
                              response=response, usage=usage))
        db.commit()


_client = None


def _anthropic():
    global _client
    if _client is None:
        import anthropic

        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set — the bridge pipeline cannot run")
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _thinking_param(budget: LLMCallBudget, thinking: str | None) -> dict | None:
    """None means "omit the parameter". Sonnet-family models run ADAPTIVE
    thinking when the param is omitted, so budgeted-off must be explicit."""
    if thinking == "adaptive":
        return {"type": "adaptive"}
    if budget.model.startswith("claude-sonnet"):
        return {"type": "disabled"}
    return None  # Haiku 4.5: omitting the param means no thinking


# Length-constraint keywords the structured-output endpoint rejects (verified
# live: minItems > 1 is a 400). Sizes are enforced by the prompt and by the
# caller's own slicing/truncation instead.
_UNSUPPORTED_SCHEMA_KEYS = frozenset({"minItems", "maxItems", "minLength", "maxLength"})


def _strictify(node: object) -> object:
    """Make a pydantic JSON schema acceptable to the structured-output
    endpoint: every 'object' node must set additionalProperties: false
    explicitly (pydantic omits it), and length constraints must go. Applied
    recursively, $defs included."""
    if isinstance(node, dict):
        out = {k: _strictify(v) for k, v in node.items() if k not in _UNSUPPORTED_SCHEMA_KEYS}
        if out.get("type") == "object":
            out.setdefault("additionalProperties", False)
        return out
    if isinstance(node, list):
        return [_strictify(v) for v in node]
    return node


def call_structured(
    db: Session,
    ledger: SpendLedger,
    call_site: str,
    static_instructions: str,
    user_text: str,
    response_model: type[BaseModel],
    thinking: str | None = None,
):
    """One budgeted, cached, schema-constrained LLM call. Returns an instance of
    response_model. Raises BudgetExceeded before spending past the ceiling."""
    budget = LLM_BUDGETS[call_site]
    schema = _strictify(response_model.model_json_schema())

    request = {
        "system": static_instructions,
        "user": user_text,
        "schema": schema,
        "max_tokens": budget.max_output_tokens,
        "thinking": thinking or "off",
    }
    key = _cache_key(call_site, budget.model, request)
    cached = cache_get(db, key)
    if cached is not None:
        logger.info("%s: cache hit (%s)", call_site, key[:12])
        return response_model.model_validate(cached.response)

    ledger.check(call_site)

    with tracing.generation(call_site, model=budget.model, input=user_text) as observation:
        response = _anthropic().messages.create(
            model=budget.model,
            max_tokens=budget.max_output_tokens,
            # The static block (capability, gate schema, format instructions) is
            # identical across every candidate and every replan round — cache it;
            # only user_text below bills as fresh input. Short blocks silently
            # fall under the minimum cacheable prefix, which costs nothing extra.
            system=[{
                "type": "text",
                "text": static_instructions,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_text}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
            **({"thinking": tp} if (tp := _thinking_param(budget, thinking)) else {}),
        )

        if response.stop_reason == "max_tokens":
            # The site outgrew its budget — a design signal, not a retry case
            # (§14.1): fix the site or its budget, deliberately.
            raise RuntimeError(
                f"{call_site} hit its max_output_tokens budget ({budget.max_output_tokens}); "
                "the task at this site has outgrown its design"
            )

        text = next(block.text for block in response.content if block.type == "text")
        parsed = response_model.model_validate(json.loads(text))

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": response.usage.cache_read_input_tokens or 0,
            "cache_creation_input_tokens": response.usage.cache_creation_input_tokens or 0,
        }
        cost = cost_from_usage(budget.model, usage)
        ledger.charge(cost)
        tracing.record_generation(observation, output=parsed.model_dump(), usage=usage, cost_usd=cost)

    cache_put(db, key, call_site, budget.model, parsed.model_dump(), usage)
    logger.info("%s: %d in / %d out tokens, $%.4f", call_site,
                usage["input_tokens"], usage["output_tokens"], cost)
    return parsed
