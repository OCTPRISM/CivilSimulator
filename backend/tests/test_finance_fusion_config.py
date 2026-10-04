"""Tests for 9×4 fusion strategy configuration table."""
from app.layer2_civilization.finance_fusion_config import (
    FUSION_TABLE,
    GENRES,
    MACRO_MODES,
    fusion_table_summary,
    get_fusion_strategy,
)


def test_table_covers_all_genres_and_modes():
    assert len(GENRES) == 9
    assert len(MACRO_MODES) == 4
    for genre in GENRES:
        assert genre in FUSION_TABLE
        for mode in MACRO_MODES:
            s = get_fusion_strategy(genre, mode)
            assert s.label
            if mode == "retail":
                assert s.enabled is False
                assert s.weight_scale == 0.0
            else:
                assert s.enabled is True
                assert s.weight_scale > 0


def test_ancient_global_high_longrun():
    s = get_fusion_strategy("ancient", "global")
    assert s.weight_scale >= 1.1
    assert s.use_mle_rho is True
    assert s.param_weights["inflation"] >= 0.30


def test_military_war_multiplier_lowest():
    mil = get_fusion_strategy("military", "global").war_regime_multiplier
    anc = get_fusion_strategy("ancient", "global").war_regime_multiplier
    assert mil < anc


def test_scifi_mystery_use_reference():
    assert get_fusion_strategy("scifi", "global").use_reference_anchor is True
    assert get_fusion_strategy("mystery", "global").use_reference_anchor is True
    assert get_fusion_strategy("modern", "global").use_reference_anchor is False


def test_corporate_lighter_than_global():
    for genre in GENRES:
        g = get_fusion_strategy(genre, "global")
        c = get_fusion_strategy(genre, "corporate")
        assert c.weight_scale <= g.weight_scale
        assert c.max_weight <= g.max_weight


def test_summary_row_count():
    assert len(fusion_table_summary()) == 36
