"""The over-rejection fixes: what the relevance judge is asked, when a stored
candidate pool may be reused, and how a Hugging Face inspection reads /size.

Each of these let on-topic datasets be thrown away before any gate or probe
looked at them. The live symptom was "pokemon" finding nothing: the judge
rejected 37/38 candidates, Kaggle's canonical Pokemon stats CSV included.
"""

from types import SimpleNamespace

import pytest

from backend.services.bridge import judge, pipeline, tools
from backend.services.bridge.gates import gate3_scale
from backend.services.bridge.registry import BRIDGE_SPECS, DataRequirement, Modality

_ASSESSED = [s for s in BRIDGE_SPECS.values()
             if s.data_requirement == DataRequirement.OWN_ASSESSMENT]


def _captured_judge_prompt(monkeypatch, spec) -> str:
    seen = {}

    def fake_call(db, ledger, call_site, static_instructions, user_text, response_model, **_):
        seen["static"] = static_instructions
        return response_model(relevant=True, reason="stub")

    monkeypatch.setattr(judge, "call_structured", fake_call)
    judge.judge_relevance(None, None, spec, "pokemon",
                          {"dataset_id": "a/b", "source": "hf", "title": "b"})
    return seen["static"]


class TestJudgePrompt:
    @pytest.mark.parametrize("spec", _ASSESSED, ids=lambda s: s.model_id)
    def test_the_step_capability_never_reaches_the_judge(self, monkeypatch, spec):
        """Given the capability, the judge rejected data for not *demonstrating*
        it, which only the probe can measure."""
        prompt = _captured_judge_prompt(monkeypatch, spec)
        assert spec.capability not in prompt
        assert spec.modality.value in prompt

    def test_steps_sharing_a_modality_get_an_identical_prompt(self, monkeypatch):
        """The pool the judge filters is keyed by (topic, modality) and reused
        across steps, so the judgement must not depend on which step built it."""
        by_modality: dict[Modality, set[str]] = {}
        for spec in _ASSESSED:
            by_modality.setdefault(spec.modality, set()).add(
                _captured_judge_prompt(monkeypatch, spec)
            )
        shared = {m: p for m, p in by_modality.items()
                  if sum(s.modality == m for s in _ASSESSED) > 1}
        assert shared, "expected at least one modality shared by several steps"
        for modality, prompts in shared.items():
            assert len(prompts) == 1, f"{modality.value} steps disagree on the judge prompt"


class _FakeDB:
    """Just enough Session for _get_or_build_pool: one lookup, add, commit."""

    def __init__(self, row):
        self.row = row
        self.added = []

    def execute(self, _stmt):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: self.row))

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass


class TestPoolReuse:
    @pytest.fixture
    def rebuilt(self, monkeypatch):
        """Stub every outside call; record whether a fresh search happened."""
        calls = {"searched": 0}

        def fake_scouts(queries, log):
            calls["searched"] += 1
            return [{"source": "kaggle", "dataset_id": "abcsds/pokemon"}]

        monkeypatch.setattr(pipeline, "plan_queries", lambda *a, **k: ["pokemon stats"])
        monkeypatch.setattr(pipeline, "_fan_out_scouts", fake_scouts)
        monkeypatch.setattr(pipeline.card_index, "vector_recall", lambda *a, **k: [])
        monkeypatch.setattr(pipeline.card_index, "upsert_cards", lambda *a, **k: None)
        monkeypatch.setattr(pipeline, "_judge_all",
                            lambda db, ledger, spec, topic, cands, rej, log: cands)
        return calls

    def _run(self, db):
        job = SimpleNamespace(topic_slug="pokemon", topic_input="pokemon")
        log = SimpleNamespace(event=lambda *a, **k: None)
        deadline = SimpleNamespace(check=lambda stage: None)
        return pipeline._get_or_build_pool(db, job, BRIDGE_SPECS["step1"], None, log, deadline)

    def test_a_current_pool_is_reused_without_searching(self, rebuilt):
        stored = {"version": pipeline.POOL_VERSION, "queries": ["q"],
                  "candidates": [{"dataset_id": "kept"}], "rejected_relevance": []}
        pool = self._run(_FakeDB(SimpleNamespace(pool=stored)))
        assert rebuilt["searched"] == 0
        assert pool["candidates"] == [{"dataset_id": "kept"}]

    def test_a_pool_from_the_old_judge_is_rebuilt_in_place(self, rebuilt):
        """The production case: a pool stored before the version stamp holds
        the old judge's rejections, and reuse would serve them forever."""
        row = SimpleNamespace(pool={"queries": ["q"], "candidates": [],
                                    "rejected_relevance": [{"dataset_id": "abcsds/pokemon"}]},
                              last_verified=None)
        db = _FakeDB(row)
        pool = self._run(db)
        assert rebuilt["searched"] == 1
        assert pool["candidates"] == [{"source": "kaggle", "dataset_id": "abcsds/pokemon"}]
        assert row.pool["version"] == pipeline.POOL_VERSION  # overwritten, not duplicated
        assert db.added == []  # (topic_slug, modality) is unique: never a second row

    def test_a_brand_new_pool_is_stamped(self, rebuilt):
        db = _FakeDB(None)
        pool = self._run(db)
        assert pool["version"] == pipeline.POOL_VERSION
        assert len(db.added) == 1


def _stub_datasets_server(monkeypatch, size_response):
    responses = {
        "/is-valid": {"viewer": True, "preview": True},
        "/splits": {"splits": [{"config": "default", "split": "train"}]},
        "/first-rows": {"rows": [{"row": {"hp": 45, "attack": 49, "type": "grass"}}]},
        "/size": size_response,
        "/statistics": None,
    }
    monkeypatch.setattr(tools, "_get", lambda path, params: responses[path])


class TestHFSizeReading:
    def test_a_failed_size_job_is_unknown_not_zero(self, monkeypatch):
        """datasets-server answers a failed size job with all-zero placeholders
        plus a `failed` entry. Read as a count, that rejected real datasets as
        'too few rows (0)'."""
        _stub_datasets_server(monkeypatch, {
            "size": {"dataset": {"num_rows": 0, "num_bytes_original_files": 0},
                     "configs": [], "splits": []},
            "failed": [{"kind": "config-size", "config": "default"}],
            "partial": False,
        })
        inspection = tools.inspect_hf_dataset("someone/pokemon")
        assert inspection["stats"]["num_rows"] is None
        result = gate3_scale(inspection, Modality.TABULAR)
        assert not result.passed
        assert result.reason == "row count unavailable"

    def test_a_real_zero_is_still_a_zero(self, monkeypatch):
        """Only the failed-job placeholder is reinterpreted."""
        _stub_datasets_server(monkeypatch, {
            "size": {"dataset": {"num_rows": 0, "num_bytes_original_files": 0},
                     "configs": [{"config": "default", "num_rows": 0, "num_columns": 3}]},
            "failed": [],
            "partial": False,
        })
        assert tools.inspect_hf_dataset("someone/empty")["stats"]["num_rows"] == 0

    def test_column_count_comes_from_the_chosen_config(self, monkeypatch):
        """/size has no num_columns at the dataset level; reading it there left
        every HF inspection with num_columns=None."""
        _stub_datasets_server(monkeypatch, {
            "size": {"dataset": {"num_rows": 1680, "num_bytes_original_files": None},
                     "configs": [{"config": "other", "num_columns": 99},
                                 {"config": "default", "num_rows": 1680, "num_columns": 23}]},
            "failed": [],
            "partial": False,
        })
        stats = tools.inspect_hf_dataset("someone/pokemon")["stats"]
        assert stats["num_rows"] == 1680
        assert stats["num_columns"] == 23

    def test_column_count_falls_back_to_the_sample_rows(self, monkeypatch):
        _stub_datasets_server(monkeypatch, {
            "size": {"dataset": {"num_rows": 800}, "configs": []},
            "failed": [],
            "partial": False,
        })
        assert tools.inspect_hf_dataset("someone/pokemon")["stats"]["num_columns"] == 3
