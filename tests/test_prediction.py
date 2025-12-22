"""Tests for margin prediction with context modifiers and game-specific variance."""

from __future__ import annotations

import pandas as pd
import pytest

from kenpom_client.matchup import MatchupFeatures
from kenpom_client.prediction import (
    calculate_margin_baseline,
    calculate_margin_enhanced,
    calculate_sigma_baseline,
    calculate_sigma_game,
    predict_game,
)


class TestMarginBaseline:
    """Test baseline margin calculation."""

    def test_baseline_formula(self):
        """Verify baseline matches current formula."""
        margin = calculate_margin_baseline(
            home_adj_em=22.0, away_adj_em=12.3, home_court_advantage=3.5
        )
        assert margin == pytest.approx(13.2)  # 22.0 - 12.3 + 3.5

    def test_baseline_negative_margin(self):
        """Test away team favored."""
        margin = calculate_margin_baseline(
            home_adj_em=8.0, away_adj_em=15.5, home_court_advantage=3.5
        )
        assert margin == pytest.approx(-4.0)  # 8.0 - 15.5 + 3.5

    def test_baseline_custom_home_court(self):
        """Test with custom home court advantage."""
        margin = calculate_margin_baseline(
            home_adj_em=15.0, away_adj_em=15.0, home_court_advantage=2.5
        )
        assert margin == pytest.approx(2.5)

    def test_baseline_even_teams(self):
        """Test with evenly matched teams."""
        margin = calculate_margin_baseline(
            home_adj_em=10.0, away_adj_em=10.0, home_court_advantage=3.5
        )
        assert margin == pytest.approx(3.5)


class TestSigmaBaseline:
    """Test baseline sigma calculation."""

    def test_sigma_baseline_average(self):
        """Verify sigma baseline is simple average."""
        sigma = calculate_sigma_baseline(away_sigma=10.5, home_sigma=11.2)
        assert sigma == pytest.approx(10.85)

    def test_sigma_baseline_equal(self):
        """Test with equal team sigmas."""
        sigma = calculate_sigma_baseline(away_sigma=11.0, home_sigma=11.0)
        assert sigma == pytest.approx(11.0)


class TestMarginEnhanced:
    """Test enhanced margin with heuristic adjustments."""

    def test_enhanced_stays_within_bounds(self):
        """Enhanced margin should be within ±2 pts of baseline."""
        # Create matchup with extreme features
        matchup = MatchupFeatures(
            delta_adj_em=-9.7,
            delta_adj_oe=-6.3,
            delta_adj_de=3.4,
            delta_tempo=-10.0,  # Large mismatch
            shooting_advantage=10.0,  # Large advantage
            shooting_defense_advantage=10.0,
            turnover_advantage=10.0,
            rebounding_advantage=10.0,
            tempo_mismatch=10.0,
            pace_control="home_controls",
            home_3pt_reliance=35.0,
            away_3pt_reliance=35.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        margin, breakdown = calculate_margin_enhanced(22.0, 12.3, matchup)
        baseline = 22.0 - 12.3 + 3.5  # 13.2

        assert abs(margin - baseline) <= 2.0  # Within ±2 pts
        assert sum(breakdown.values()) == pytest.approx(margin - baseline, abs=0.01)

    def test_neutral_matchup_minimal_adjustment(self):
        """Neutral matchup should have minimal adjustment."""
        # Balanced matchup
        matchup = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=0.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=0.0,
            pace_control="neutral",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        margin, breakdown = calculate_margin_enhanced(15.0, 15.0, matchup)
        baseline = 15.0 - 15.0 + 3.5  # 3.5

        assert abs(margin - baseline) < 0.1  # Minimal adjustment
        assert all(abs(adj) < 0.01 for adj in breakdown.values())

    def test_home_pace_control_advantage(self):
        """Home controlling pace should give small advantage."""
        matchup = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=-10.0,  # Home is faster
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=10.0,
            pace_control="home_controls",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        margin, breakdown = calculate_margin_enhanced(15.0, 15.0, matchup)

        # Pace adjustment should be positive (home advantage)
        assert breakdown["pace_control"] > 0.0
        # Should be around (10.0 / 5.0) * 0.10 = 0.2
        assert breakdown["pace_control"] == pytest.approx(0.2, abs=0.01)

    def test_away_pace_control_disadvantage(self):
        """Away controlling pace should penalize home."""
        matchup = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=10.0,  # Away is faster
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=10.0,
            pace_control="away_controls",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        margin, breakdown = calculate_margin_enhanced(15.0, 15.0, matchup)

        # Pace adjustment should be negative (home disadvantage)
        assert breakdown["pace_control"] < 0.0
        assert breakdown["pace_control"] == pytest.approx(-0.2, abs=0.01)

    def test_shooting_matchup_advantage(self):
        """Positive shooting advantage should help home."""
        matchup = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=0.0,
            shooting_advantage=0.0,  # Away offense vs home defense (neutral)
            shooting_defense_advantage=5.0,  # Home offense vs away defense (advantage)
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=0.0,
            pace_control="neutral",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        margin, breakdown = calculate_margin_enhanced(15.0, 15.0, matchup)

        # Net shooting = 5.0 - 0.0 = 5.0
        # Adjustment = (5.0 / 5.0) * 0.06 = 0.06
        assert breakdown["shooting_matchup"] > 0.0
        assert breakdown["shooting_matchup"] == pytest.approx(0.06, abs=0.01)

    def test_real_world_oregon_gonzaga(self):
        """Test with realistic Oregon @ Gonzaga matchup."""
        # Use actual matchup features from test_matchup_features.py
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
                "sigma": 10.5,
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
                "sigma": 11.2,
            }
        )

        prediction = predict_game(oregon, gonzaga)

        # Baseline should be 13.2 (22.0 - 12.3 + 3.5)
        assert prediction.margin_baseline == pytest.approx(13.2)

        # Enhanced should be within ±2 pts
        assert abs(prediction.margin_enhanced - 13.2) <= 2.0

        # Adjustment breakdown should sum to margin_adjustment
        total_adj = sum(prediction.adjustment_breakdown.values())
        assert total_adj == pytest.approx(prediction.margin_adjustment, abs=0.01)

    def test_custom_coefficients(self):
        """Test ML coefficient override."""
        matchup = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=-10.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=10.0,
            pace_control="home_controls",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        custom_coef = {
            "pace_control_per_5_tempo": 0.20,  # Double the heuristic
            "shooting_matchup_per_5_efg": 0.12,
            "turnover_battle_per_2_to": 0.20,
            "rebounding_edge_per_3_or": 0.066,
            "max_total_adjustment": 4.0,  # Allow larger adjustments
        }

        margin_heuristic, _ = calculate_margin_enhanced(15.0, 15.0, matchup)
        margin_custom, breakdown_custom = calculate_margin_enhanced(
            15.0, 15.0, matchup, coefficients=custom_coef
        )

        # Custom coefficients should produce different results
        assert margin_custom != pytest.approx(margin_heuristic)
        # Pace adjustment should be doubled: (10.0 / 5.0) * 0.20 = 0.4
        assert breakdown_custom["pace_control"] == pytest.approx(0.4, abs=0.01)


class TestSigmaGame:
    """Test additive variance sigma calculation."""

    def test_sigma_game_greater_than_max_team_sigma(self):
        """Game sigma should be >= max(away_sigma, home_sigma)."""
        matchup = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=0.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=0.0,
            pace_control="neutral",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        sigma, components = calculate_sigma_game(10.5, 11.2, matchup)

        assert sigma >= max(10.5, 11.2)
        assert sigma >= 11.2

    def test_tempo_mismatch_increases_variance(self):
        """High tempo mismatch should increase game variance."""
        low_mismatch = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=1.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=1.0,
            pace_control="neutral",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )
        high_mismatch = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=10.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=10.0,
            pace_control="away_controls",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        sigma_low, _ = calculate_sigma_game(10.0, 10.0, low_mismatch)
        sigma_high, _ = calculate_sigma_game(10.0, 10.0, high_mismatch)

        assert sigma_high > sigma_low

    def test_style_clash_increases_variance(self):
        """3PT vs interior clash should increase variance."""
        similar = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=5.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=5.0,
            pace_control="neutral",
            home_3pt_reliance=30.0,
            away_3pt_reliance=30.0,
            style_clash="similar",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )
        clash = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=5.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=5.0,
            pace_control="neutral",
            home_3pt_reliance=45.0,
            away_3pt_reliance=25.0,
            style_clash="3pt_vs_interior",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        sigma_similar, _ = calculate_sigma_game(10.0, 10.0, similar)
        sigma_clash, _ = calculate_sigma_game(10.0, 10.0, clash)

        assert sigma_clash > sigma_similar

    def test_variance_components_add_up(self):
        """Variance components should sum correctly."""
        matchup = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=7.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=7.0,
            pace_control="neutral",
            home_3pt_reliance=45.0,
            away_3pt_reliance=25.0,
            style_clash="3pt_vs_interior",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        sigma, components = calculate_sigma_game(10.5, 11.2, matchup)

        expected_var = (
            components["var_away"] + components["var_home"] + components["var_interaction"]
        )
        assert components["var_total"] == pytest.approx(expected_var)
        # sigma_game should be sqrt of total variance (or max team sigma, whichever is larger)
        from_variance = (expected_var) ** 0.5
        assert sigma == pytest.approx(max(from_variance, 10.5, 11.2))

    def test_interaction_variance_formula(self):
        """Test interaction variance calculation."""
        matchup = MatchupFeatures(
            delta_adj_em=0.0,
            delta_adj_oe=0.0,
            delta_adj_de=0.0,
            delta_tempo=10.0,
            shooting_advantage=0.0,
            shooting_defense_advantage=0.0,
            turnover_advantage=0.0,
            rebounding_advantage=0.0,
            tempo_mismatch=10.0,
            pace_control="away_controls",
            home_3pt_reliance=45.0,
            away_3pt_reliance=25.0,
            style_clash="3pt_vs_interior",
            home_court_factor=3.5,
            rest_advantage=None,
            travel_distance=None,
            feature_version="1.0",
        )

        sigma, components = calculate_sigma_game(10.0, 10.0, matchup)

        # tempo_var = 0.015 * (10.0 ** 2) = 1.5
        # style_multiplier = 1.10 (3pt_vs_interior)
        # var_interaction = 1.5 * 1.10 = 1.65
        expected_interaction = 0.015 * (10.0**2) * 1.10
        assert components["var_interaction"] == pytest.approx(expected_interaction)


class TestPredictGame:
    """Test complete game prediction."""

    def test_predict_game_returns_all_fields(self):
        """Verify MarginPrediction has all required fields."""
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
                "sigma": 10.5,
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
                "sigma": 11.2,
            }
        )

        prediction = predict_game(oregon, gonzaga)

        # Check all fields exist
        assert hasattr(prediction, "margin_baseline")
        assert hasattr(prediction, "margin_enhanced")
        assert hasattr(prediction, "margin_adjustment")
        assert hasattr(prediction, "sigma_baseline")
        assert hasattr(prediction, "sigma_game")
        assert hasattr(prediction, "win_prob_baseline")
        assert hasattr(prediction, "win_prob_enhanced")
        assert hasattr(prediction, "adjustment_breakdown")
        assert hasattr(prediction, "sigma_components")
        assert hasattr(prediction, "prediction_version")

        # Check adjustment breakdown keys
        assert "pace_control" in prediction.adjustment_breakdown
        assert "shooting_matchup" in prediction.adjustment_breakdown
        assert "turnover_battle" in prediction.adjustment_breakdown
        assert "rebounding_edge" in prediction.adjustment_breakdown

        # Check sigma components keys
        assert "var_away" in prediction.sigma_components
        assert "var_home" in prediction.sigma_components
        assert "var_interaction" in prediction.sigma_components
        assert "var_total" in prediction.sigma_components

        # Check prediction version
        assert prediction.prediction_version == "1.0"

    def test_predict_game_baseline_values(self):
        """Test baseline prediction values are correct."""
        home = pd.Series({"adj_em": 20.0, "sigma": 11.0})
        away = pd.Series({"adj_em": 15.0, "sigma": 10.0})

        prediction = predict_game(away, home)

        # Baseline margin = 20.0 - 15.0 + 3.5 = 8.5
        assert prediction.margin_baseline == pytest.approx(8.5)

        # Baseline sigma = (10.0 + 11.0) / 2.0 = 10.5
        assert prediction.sigma_baseline == pytest.approx(10.5)

        # Margin adjustment should be margin_enhanced - margin_baseline
        assert prediction.margin_adjustment == pytest.approx(
            prediction.margin_enhanced - prediction.margin_baseline
        )

    def test_predict_game_with_precomputed_matchup(self):
        """Test with precomputed matchup features."""
        from kenpom_client.matchup import calculate_matchup_features

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
                "sigma": 10.5,
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
                "sigma": 11.2,
            }
        )

        matchup = calculate_matchup_features(oregon, gonzaga)
        prediction1 = predict_game(oregon, gonzaga)
        prediction2 = predict_game(oregon, gonzaga, matchup_features=matchup)

        # Should get same results
        assert prediction1.margin_baseline == pytest.approx(prediction2.margin_baseline)
        assert prediction1.margin_enhanced == pytest.approx(prediction2.margin_enhanced)
        assert prediction1.sigma_game == pytest.approx(prediction2.sigma_game)
