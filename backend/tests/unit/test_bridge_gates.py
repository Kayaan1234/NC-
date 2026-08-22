"""Gates 1-3 and the slug: pure functions over records, so pure unit tests."""

import pytest

from backend.services.bridge.gates import (
    SCALE_READINGS,
    gate1_license,
    gate2_loadable,
    gate3_scale,
)
from backend.services.bridge.registry import Modality
from backend.services.bridge.slug import slugify_topic


class TestGate1License:
    def test_allowlisted_license_passes(self):
        assert gate1_license({"license": "mit"}).passed
        assert gate1_license({"license": "CC-BY-4.0"}).passed  # case-folded

    def test_absent_license_is_rejected(self):
        result = gate1_license({"license": None})
        assert not result.passed
        assert "no license" in result.reason

    def test_non_commercial_is_rejected(self):
        result = gate1_license({"license": "cc-by-nc-4.0"})
        assert not result.passed
        assert "cc-by-nc-4.0" in result.reason


class TestGate2Loadable:
    def test_valid_with_rows_passes(self):
        assert gate2_loadable(
            {"valid": True, "splits": [{"config": "d", "split": "train"}],
             "sample_rows": [{"a": 1}]}
        ).passed

    @pytest.mark.parametrize("inspection, fragment", [
        ({"valid": False, "splits": [], "sample_rows": []}, "unusable"),
        ({"valid": True, "splits": [], "sample_rows": []}, "no defined splits"),
        ({"valid": True, "splits": [{"config": "d", "split": "t"}], "sample_rows": []}, "no rows"),
    ])
    def test_dead_datasets_are_rejected(self, inspection, fragment):
        result = gate2_loadable(inspection)
        assert not result.passed
        assert fragment in result.reason


class TestGate3Scale:
    def test_tabular_floor(self):
        result = gate3_scale({"stats": {"num_rows": 100, "num_columns": 5}}, Modality.TABULAR)
        assert not result.passed
        assert "too few rows" in result.reason

    def test_tabular_ok(self):
        assert gate3_scale({"stats": {"num_rows": 5000, "num_columns": 5}}, Modality.TABULAR).passed

    def test_too_large_is_never_terminal(self):
        result = gate3_scale(
            {"stats": {"num_rows": 10_000_000, "num_columns": 5, "num_bytes": 50 * 1024**3}},
            Modality.TABULAR,
        )
        assert result.passed
        assert "subset" in result.reason

    def test_partial_statistics_are_not_judged(self):
        result = gate3_scale({"partial": True, "stats": {"num_rows": 5}}, Modality.TABULAR)
        assert not result.passed
        assert "still computing" in result.reason

    def test_text_pair_uses_its_own_floor(self):
        # 5,000 rows clears tabular comfortably and fails a parallel corpus.
        stats = {"stats": {"num_rows": 5000}}
        assert gate3_scale(stats, Modality.TABULAR).passed
        assert not gate3_scale(stats, Modality.TEXT_PAIR).passed

    def test_every_used_modality_has_a_reading(self):
        for modality in (Modality.TABULAR, Modality.IMAGE_GRID,
                         Modality.SEQUENCE, Modality.TEXT_PAIR):
            assert modality in SCALE_READINGS
            assert SCALE_READINGS[modality].floor > 0


class TestSlug:
    @pytest.mark.parametrize("raw, expected", [
        ("Morris Dancing", "morris-dancing"),
        ("  premier   league!!  ", "premier-league"),
        ("Café Menus", "cafe-menus"),
        ("weather", "weather"),
    ])
    def test_normalisation(self, raw, expected):
        assert slugify_topic(raw) == expected

    def test_same_topic_different_typing_shares_a_slug(self):
        assert slugify_topic("Premier League") == slugify_topic("premier league ")

    def test_garbage_becomes_empty(self):
        assert slugify_topic("!!!") == ""

    def test_length_cap(self):
        assert len(slugify_topic("x" * 500)) <= 80
