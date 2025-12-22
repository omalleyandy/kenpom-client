"""Tests for matchup feature engineering."""

from __future__ import annotations

import pandas as pd
import pytest

from kenpom_client.matchup import (
    MatchupFeatures,
    calculate_home_court_factor,
    calculate_matchup_features,
)


class TestMatchupFeatures:
    """Test MatchupFeatures dataclass properties."""

    def test_dataclass_frozen(self):
        """Test that MatchupFeatures is immutable."""
        features = MatchupFeatures(
            delta_adj_em=10.0,
            delta_adj_oe=5.0,
            delta_adj_de=-3.0,
            delta_tempo=2.0,
            shooting_advantage=3.5,
            shooting_defense_advantage=-2.0,
            turnover_advantage=1.5,
            rebounding_advantage=4.0,
            tempo_mismatch=2.0,
            pace_control="neutral",
            home_3pt_reliance=32.0,
            away_3pt_reliance=28.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        with pytest.raises(AttributeError):
            features.delta_adj_em = 15.0  # type: ignore[misc]  # Intentional test


class TestCalculateMatchupFeatures:
    """Test matchup feature calculation."""

    def test_efficiency_deltas(self):
        """Test efficiency delta calculations."""
        away = pd.Series({"adj_em": 20.5, "adj_oe": 115.0, "adj_de": 94.5, "adj_tempo": 70.0})
        home = pd.Series({"adj_em": 15.0, "adj_oe": 110.0, "adj_de": 95.0, "adj_tempo": 68.0})

        matchup = calculate_matchup_features(away, home)

        assert matchup.delta_adj_em == pytest.approx(5.5)  # 20.5 - 15.0
        assert matchup.delta_adj_oe == pytest.approx(5.0)  # 115.0 - 110.0
        assert matchup.delta_adj_de == pytest.approx(-0.5)  # 94.5 - 95.0 (better defense)
        assert matchup.delta_tempo == pytest.approx(2.0)  # 70.0 - 68.0

    def test_shooting_matchup(self):
        """Test shooting advantage calculations."""
        away = pd.Series({"efg_pct": 55.0, "defg_pct": 48.0})
        home = pd.Series({"efg_pct": 52.0, "defg_pct": 50.0})

        matchup = calculate_matchup_features(away, home)

        # Away offense (55.0) vs Home defense (50.0) = +5.0 advantage
        assert matchup.shooting_advantage == pytest.approx(5.0)

        # Home offense (52.0) vs Away defense (48.0) = +4.0 advantage
        assert matchup.shooting_defense_advantage == pytest.approx(4.0)

    def test_ball_control_signals(self):
        """Test turnover and rebounding advantage calculations."""
        away = pd.Series({"to_pct": 18.0, "or_pct": 35.0})
        home = pd.Series({"dto_pct": 22.0, "dor_pct": 28.0})

        matchup = calculate_matchup_features(away, home)

        # Turnover: Home forces (22.0) - Away commits (18.0) = +4.0
        assert matchup.turnover_advantage == pytest.approx(4.0)

        # Rebounding: Away OR (35.0) - Home DOR (28.0) = +7.0
        assert matchup.rebounding_advantage == pytest.approx(7.0)

    def test_tempo_mismatch_neutral(self):
        """Test tempo mismatch detection - neutral pace."""
        away = pd.Series({"adj_tempo": 68.0})
        home = pd.Series({"adj_tempo": 67.0})

        matchup = calculate_matchup_features(away, home)

        assert matchup.tempo_mismatch == pytest.approx(1.0)
        assert matchup.pace_control == "neutral"

    def test_tempo_mismatch_away_controls(self):
        """Test tempo mismatch - away team controls pace."""
        away = pd.Series({"adj_tempo": 75.0})  # Fast-paced
        home = pd.Series({"adj_tempo": 65.0})  # Slow-paced

        matchup = calculate_matchup_features(away, home)

        assert matchup.tempo_mismatch == pytest.approx(10.0)
        assert matchup.delta_tempo == pytest.approx(10.0)
        assert matchup.pace_control == "away_controls"

    def test_tempo_mismatch_home_controls(self):
        """Test tempo mismatch - home team controls pace."""
        away = pd.Series({"adj_tempo": 62.0})  # Slow-paced
        home = pd.Series({"adj_tempo": 72.0})  # Fast-paced

        matchup = calculate_matchup_features(away, home)

        assert matchup.tempo_mismatch == pytest.approx(10.0)
        assert matchup.delta_tempo == pytest.approx(-10.0)
        assert matchup.pace_control == "home_controls"

    def test_style_clash_similar(self):
        """Test style classification - similar teams."""
        away = pd.Series({"off_fg3": 30.0})  # Balanced
        home = pd.Series({"off_fg3": 32.0})  # Balanced

        matchup = calculate_matchup_features(away, home)

        assert matchup.away_3pt_reliance == pytest.approx(30.0)
        assert matchup.home_3pt_reliance == pytest.approx(32.0)
        assert matchup.style_clash == "similar"

    def test_style_clash_3pt_vs_interior(self):
        """Test style classification - 3PT vs interior mismatch."""
        away = pd.Series({"off_fg3": 42.0})  # 3PT-heavy
        home = pd.Series({"off_fg3": 25.0})  # Interior-focused

        matchup = calculate_matchup_features(away, home)

        assert matchup.away_3pt_reliance == pytest.approx(42.0)
        assert matchup.home_3pt_reliance == pytest.approx(25.0)
        assert matchup.style_clash == "3pt_vs_interior"

    def test_home_court_factor_constant(self):
        """Test home court factor (currently constant)."""
        away = pd.Series({})
        home = pd.Series({})

        matchup = calculate_matchup_features(away, home)

        assert matchup.home_court_factor == pytest.approx(3.5)

    def test_placeholder_hooks_none(self):
        """Test placeholder hooks return None."""
        away = pd.Series({})
        home = pd.Series({})

        matchup = calculate_matchup_features(away, home)

        assert matchup.rest_advantage is None
        assert matchup.travel_distance is None

    def test_feature_version(self):
        """Test feature version metadata."""
        away = pd.Series({})
        home = pd.Series({})

        matchup = calculate_matchup_features(away, home)

        assert matchup.feature_version == "1.0"

    def test_missing_four_factors_uses_defaults(self):
        """Test that missing four factors data uses default values."""
        # Teams with no enrichment data
        away = pd.Series({"adj_em": 10.0, "adj_oe": 108.0, "adj_de": 98.0, "adj_tempo": 68.0})
        home = pd.Series({"adj_em": 8.0, "adj_oe": 106.0, "adj_de": 98.0, "adj_tempo": 67.0})

        matchup = calculate_matchup_features(away, home)

        # Should use default values (50.0 for eFG%, etc.)
        assert matchup.shooting_advantage == pytest.approx(0.0)  # 50.0 - 50.0
        assert matchup.shooting_defense_advantage == pytest.approx(0.0)
        assert matchup.turnover_advantage == pytest.approx(0.0)  # 20.0 - 20.0
        assert matchup.rebounding_advantage == pytest.approx(0.0)  # 30.0 - 30.0

    def test_missing_point_distribution_uses_defaults(self):
        """Test that missing point distribution data uses default values."""
        # Teams with no point distribution data
        away = pd.Series({})
        home = pd.Series({})

        matchup = calculate_matchup_features(away, home)

        # Should use default 3PT reliance (30.0%)
        assert matchup.away_3pt_reliance == pytest.approx(30.0)
        assert matchup.home_3pt_reliance == pytest.approx(30.0)
        assert matchup.style_clash == "similar"

    def test_none_values_handled(self):
        """Test that None values are handled gracefully."""
        away = pd.Series({"adj_em": None, "adj_oe": None, "efg_pct": None, "to_pct": None})
        home = pd.Series({"adj_em": None, "adj_oe": None, "efg_pct": None, "dto_pct": None})

        matchup = calculate_matchup_features(away, home)

        # Should use defaults without errors
        assert matchup.delta_adj_em == pytest.approx(0.0)
        assert matchup.delta_adj_oe == pytest.approx(0.0)
        assert matchup.shooting_advantage == pytest.approx(0.0)
        assert matchup.turnover_advantage == pytest.approx(0.0)

    def test_real_world_example_oregon_gonzaga(self):
        """Test with realistic Oregon vs Gonzaga data."""
        # Example from 2025 season
        oregon = pd.Series(
            {
                "adj_em": 12.3,
                "adj_oe": 114.5,
                "adj_de": 102.2,
                "adj_tempo": 67.5,
                "efg_pct": 52.5,
                "defg_pct": 49.8,
                "to_pct": 17.5,
                "or_pct": 32.0,
                "off_fg3": 35.0,
            }
        )

        gonzaga = pd.Series(
            {
                "adj_em": 22.0,
                "adj_oe": 120.8,
                "adj_de": 98.8,
                "adj_tempo": 69.2,
                "efg_pct": 55.2,
                "defg_pct": 47.5,
                "to_pct": 15.8,
                "or_pct": 28.5,
                "dto_pct": 21.0,
                "dor_pct": 27.0,
                "off_fg3": 33.0,
            }
        )

        matchup = calculate_matchup_features(oregon, gonzaga)

        # Efficiency deltas (away - home)
        assert matchup.delta_adj_em == pytest.approx(-9.7)  # Oregon underdog
        assert matchup.delta_adj_oe == pytest.approx(-6.3)  # Gonzaga offense better
        assert matchup.delta_adj_de == pytest.approx(3.4)  # Gonzaga defense better

        # Tempo
        assert matchup.delta_tempo == pytest.approx(-1.7)  # Similar pace
        assert matchup.pace_control == "neutral"  # < 5.0 difference

        # Shooting
        assert matchup.shooting_advantage == pytest.approx(
            5.0
        )  # Oregon offense (52.5) vs Gonzaga defense (47.5)
        assert matchup.shooting_defense_advantage == pytest.approx(
            5.4
        )  # Gonzaga offense (55.2) vs Oregon defense (49.8)

        # Style
        assert matchup.style_clash == "similar"  # 2% 3PT difference


class TestHelperFunctions:
    """Test helper functions."""

    def test_calculate_home_court_factor(self):
        """Test home court factor calculation (placeholder)."""
        home = pd.Series({"team": "Duke", "wins": 15, "losses": 2})

        hca = calculate_home_court_factor(home)

        assert hca == pytest.approx(3.5)  # Currently returns constant
