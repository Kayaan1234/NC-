"""The cost plumbing: pricing arithmetic, cache keys, the thinking policy, the
spend ledger's circuit breaker, and the critic's grounding assertions. All pure
— no network (the unit tier blocks sockets anyway), no real DB.
"""

from decimal import Decimal

import pytest

from backend.services.bridge import critic
from backend.services.bridge.llm import (
    BudgetExceeded,
    SpendLedger,
    _cache_key,
    _thinking_param,
    cost_from_usage,
)
from backend.services.bridge.registry import BRIDGE_SPECS, LLM_BUDGETS
from backend.services.bridge.verdict import (
    BUILDABLE_AFTER_COLLECTION,
    BUILDABLE_NOW,
    NOT_AT_HOBBY_SCALE,
    NOT_AT_THIS_STEP,
    decide_verdict_value,
)


class TestPricing:
    def test_plain_call_cost(self):
        usage = {"input_tokens": 1000, "output_tokens": 100}
        # Haiku: $1/M in + $5/M out.
        assert cost_from_usage("claude-haiku-4-5", usage) == pytest.approx(0.001 + 0.0005)

    def test_cache_reads_bill_at_a_tenth(self):
        cached = cost_from_usage("claude-haiku-4-5", {"cache_read_input_tokens": 10_000})
        fresh = cost_from_usage("claude-haiku-4-5", {"input_tokens": 10_000})
        assert cached == pytest.approx(fresh * 0.1)

    def test_every_budgeted_model_is_priced(self):
        for budget in LLM_BUDGETS.values():
            assert cost_from_usage(budget.model, {"input_tokens": 1}) >= 0


class TestCacheKey:
    def test_identical_requests_share_a_key(self):
        request = {"system": "s", "user": "u", "schema": {"a": 1}}
        assert _cache_key("judge", "m", request) == _cache_key("judge", "m", dict(request))

    def test_any_field_change_changes_the_key(self):
        base = {"system": "s", "user": "u"}
        assert _cache_key("judge", "m", base) != _cache_key("judge", "m", {"system": "s", "user": "v"})
        assert _cache_key("judge", "m", base) != _cache_key("planner", "m", base)


class TestThinkingPolicy:
    def test_sonnet_default_is_explicitly_disabled(self):
        # Omitting the param on Sonnet 5 runs ADAPTIVE thinking — budgeted-off
        # must therefore be explicit, not an omission.
        assert _thinking_param(LLM_BUDGETS["query_planner"], None) == {"type": "disabled"}

    def test_haiku_omits_the_param(self):
        assert _thinking_param(LLM_BUDGETS["relevance_judge"], None) is None

    def test_replan_round_two_gets_adaptive(self):
        assert _thinking_param(LLM_BUDGETS["query_planner"], "adaptive") == {"type": "adaptive"}


class _FakeDb:
    def commit(self):
        pass


class _FakeJob:
    def __init__(self, cost):
        self.cost_usd = cost


class TestSpendLedger:
    def test_breaker_trips_before_the_next_call(self, monkeypatch):
        from backend.services.bridge import llm as llm_mod

        monkeypatch.setattr(llm_mod.settings, "BRIDGE_VERDICT_SPEND_CEILING_USD", 0.10)
        ledger = SpendLedger(_FakeDb(), _FakeJob(Decimal("0.10")))
        with pytest.raises(BudgetExceeded, match="ceiling"):
            ledger.check("relevance_judge")

    def test_under_ceiling_is_allowed_and_charges_accumulate(self, monkeypatch):
        from backend.services.bridge import llm as llm_mod

        monkeypatch.setattr(llm_mod.settings, "BRIDGE_VERDICT_SPEND_CEILING_USD", 0.10)
        job = _FakeJob(Decimal("0"))
        ledger = SpendLedger(_FakeDb(), job)
        ledger.check("query_planner")
        ledger.charge(0.04)
        ledger.charge(0.04)
        assert job.cost_usd == Decimal("0.08")
        ledger.check("verdict_summary")
        ledger.charge(0.04)
        with pytest.raises(BudgetExceeded):
            ledger.check("relevance_judge")


class TestVerdictValue:
    def test_dataset_with_passing_probe_is_buildable_now(self):
        context = {"dataset": {"x": 1}, "probe_report": {"outcome": "pass"}}
        assert decide_verdict_value(context) == BUILDABLE_NOW

    def test_dataset_with_failed_probe_is_not_at_this_step(self):
        context = {"dataset": {"x": 1}, "probe_report": {"outcome": "fail"}}
        assert decide_verdict_value(context) == NOT_AT_THIS_STEP

    def test_reachable_api_only_is_after_collection(self):
        context = {"dataset": None, "api_assessments": [{"reachable": True}]}
        assert decide_verdict_value(context) == BUILDABLE_AFTER_COLLECTION

    def test_nothing_is_not_at_hobby_scale(self):
        assert decide_verdict_value({"dataset": None}) == NOT_AT_HOBBY_SCALE


class TestCritic:
    def _context(self):
        return {
            "dataset": {"source": "hf", "dataset_id": "user/set"},
            "probe_report": {"outcome": "pass", "means": {"mlp": 0.9}, "noise_band": 0.01,
                             "per_seed": {"0": {"mlp": 0.9}}},
            "pool_candidates": [{"source": "hf", "dataset_id": "user/set"}],
            "inspection": {"stats": {}},
            "evidence": {"rejections": {}},
        }

    def _artefact(self, context):
        spec = BRIDGE_SPECS["step1"]
        return {
            "verdict": BUILDABLE_NOW,
            "dataset": context["dataset"],
            "fit": {"probed": True, **{k: context["probe_report"][k]
                                       for k in ("outcome", "means", "noise_band", "per_seed")}},
            "difficulty": {"tier": max(1, spec.difficulty_floor)},
            "evidence": {"rejections": {}},
        }

    def test_consistent_artefact_passes(self):
        context = self._context()
        critic.check(self._artefact(context), BRIDGE_SPECS["step1"], context)

    def test_wrong_verdict_value_is_a_hard_failure(self):
        context = self._context()
        artefact = self._artefact(context)
        artefact["verdict"] = NOT_AT_HOBBY_SCALE
        with pytest.raises(critic.CriticError, match="inconsistent"):
            critic.check(artefact, BRIDGE_SPECS["step1"], context)

    def test_uncited_dataset_is_a_hard_failure(self):
        context = self._context()
        artefact = self._artefact(context)
        artefact["dataset"] = {"source": "hf", "dataset_id": "invented/name"}
        with pytest.raises(critic.CriticError, match="not in the scouted pool"):
            critic.check(artefact, BRIDGE_SPECS["step1"], context)

    def test_fit_numbers_must_match_the_probe_record(self):
        context = self._context()
        artefact = self._artefact(context)
        artefact["fit"]["means"] = {"mlp": 0.99}  # embellished
        with pytest.raises(critic.CriticError, match="does not match the probe record"):
            critic.check(artefact, BRIDGE_SPECS["step1"], context)

    def test_unprobed_needs_a_stated_reason(self):
        context = self._context()
        artefact = self._artefact(context)
        context["probe_report"] = None
        artefact["fit"] = {"probed": False}
        artefact["verdict"] = BUILDABLE_NOW
        with pytest.raises(critic.CriticError, match="unconfirmed_reason"):
            critic.check(artefact, BRIDGE_SPECS["step1"], context)

    def test_inherited_fit_must_be_copied_unchanged(self):
        upstream = {"fit": {"probed": True}, "evidence": {"a": 1}}
        artefact = {"inherited_from": "step1", "fit": {"probed": False}, "evidence": {"a": 1}}
        with pytest.raises(critic.CriticError, match="differs from upstream"):
            critic.check_inherited(artefact, upstream)
