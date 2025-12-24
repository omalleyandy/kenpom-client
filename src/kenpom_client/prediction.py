"""Enhanced margin prediction with context modifiers and game-specific variance.

This module provides both baseline (simple) and enhanced (context-aware) margin
predictions for NCAA basketball games. It implements heuristic adjustments based
on matchup features and uses an additive variance model for game-level sigma.

Key Features:
- Baseline model: Simple margin = home_adj_em - away_adj_em + 3.5
- Enhanced model: Baseline + heuristic adjustments (±2 pts max)
- Game-specific sigma: Additive variance model with interaction terms
- Score projection: Individual team scores using OE/DE crossover
- ML-ready architecture: Coefficients replaceable for machine learning
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Union

import pandas as pd

from kenpom_client.matchup import MatchupFeatures
from kenpom_client.models import ArchiveRating, Rating

# Default home court advantage in college basketball (points)
# This is used as a fallback when team-specific HCA data is not available
DEFAULT_HOME_COURT_ADVANTAGE = 3.5

# Default sigmoid scaling factor for win probability
# At k=11, a 10-point favorite has ~71% win probability
# Lower k = sharper probabilities, higher k = more conservative
DEFAULT_SIGMOID_K = 11.0


# =============================================================================
# Score Projection (Individual Team Scores)
# =============================================================================


@dataclass(frozen=True)
class ScoreProjection:
    """Projected scores for a game using OE/DE crossover method.

    Uses the algorithm:
    1. poss = avg(tempo_home, tempo_visitor)
    2. E_home = avg(OE_home, DE_visitor)
    3. E_visitor = avg(OE_visitor, DE_home)
    4. score = poss * E / 100 ± home_adv/2

    All fields from home team perspective.
    """

    proj_home: float  # Projected home team score
    proj_visitor: float  # Projected visitor score
    proj_total: float  # proj_home + proj_visitor
    proj_margin: float  # proj_home - proj_visitor (positive = home favored)
    possessions: float  # Expected game possessions
    win_prob_home: float  # sigmoid(margin/k)
    win_prob_visitor: float  # 1 - win_prob_home
    home_adv: float  # HCA value used
    k: float  # Sigmoid k value used
    method: str  # "ratings" or "archive"
    feature_source: str  # Source identifier for the ratings data


def sigmoid_winprob(margin: float, k: float = DEFAULT_SIGMOID_K) -> float:
    """Calculate win probability using sigmoid function.

    Formula: p = 1 / (1 + exp(-margin / k))

    Args:
        margin: Point spread (positive = home favored)
        k: Scaling factor (default 11.0)

    Returns:
        Win probability for home team [0, 1]

    Example:
        >>> sigmoid_winprob(10.0)  # 10-point favorite
        0.7109...
        >>> sigmoid_winprob(0.0)   # Even game
        0.5
    """
    return 1.0 / (1.0 + math.exp(-margin / k))


def project_scores(
    home: Union[Rating, ArchiveRating],
    visitor: Union[Rating, ArchiveRating],
    home_adv: float = DEFAULT_HOME_COURT_ADVANTAGE,
    k: float = DEFAULT_SIGMOID_K,
    feature_source: Optional[str] = None,
) -> ScoreProjection:
    """Project individual team scores using OE/DE crossover method.

    Implements the algorithm from PROJECTION_MODEL_SPEC.md:
    1. poss = (AdjTempo_home + AdjTempo_visitor) / 2
    2. E_home = (AdjOE_home + AdjDE_visitor) / 2
    3. E_visitor = (AdjOE_visitor + AdjDE_home) / 2
    4. raw_score = poss * E / 100
    5. Apply HCA split evenly across scores

    Args:
        home: Home team Rating or ArchiveRating
        visitor: Visitor team Rating or ArchiveRating
        home_adv: Home court advantage in points (default 3.5)
        k: Sigmoid scaling factor for win probability (default 11.0)
        feature_source: Optional source identifier (e.g., "archive:2024-03-14")

    Returns:
        ScoreProjection with projected scores, margin, total, and win probability

    Example:
        >>> from kenpom_client.client import KenPomClient
        >>> client = KenPomClient(settings)
        >>> ratings = client.ratings(y=2025)
        >>> duke = next(r for r in ratings if "Duke" in r.TeamName)
        >>> unc = next(r for r in ratings if "North Carolina" in r.TeamName)
        >>> proj = project_scores(duke, unc)
        >>> print(f"{proj.proj_home:.1f} - {proj.proj_visitor:.1f}")
    """
    # Step 1: Compute possessions
    poss = (home.AdjTempo + visitor.AdjTempo) / 2.0

    # Step 2: Compute expected efficiencies (OE/DE crossover)
    e_home = (home.AdjOE + visitor.AdjDE) / 2.0
    e_visitor = (visitor.AdjOE + home.AdjDE) / 2.0

    # Step 3: Compute raw scores (neutral site)
    raw_home = poss * e_home / 100.0
    raw_visitor = poss * e_visitor / 100.0

    # Step 4: Apply home court adjustment (split evenly)
    proj_home = raw_home + (home_adv / 2.0)
    proj_visitor = raw_visitor - (home_adv / 2.0)

    # Step 5: Compute derived outputs
    proj_total = proj_home + proj_visitor
    proj_margin = proj_home - proj_visitor

    # Step 6: Compute win probability
    win_prob_home = sigmoid_winprob(proj_margin, k)
    win_prob_visitor = 1.0 - win_prob_home

    # Determine method and feature source
    method = "archive" if isinstance(home, ArchiveRating) else "ratings"
    if feature_source is None:
        if isinstance(home, ArchiveRating):
            feature_source = f"archive:{home.ArchiveDate}"
        else:
            feature_source = f"ratings:{home.DataThrough}"

    return ScoreProjection(
        proj_home=proj_home,
        proj_visitor=proj_visitor,
        proj_total=proj_total,
        proj_margin=proj_margin,
        possessions=poss,
        win_prob_home=win_prob_home,
        win_prob_visitor=win_prob_visitor,
        home_adv=home_adv,
        k=k,
        method=method,
        feature_source=feature_source,
    )


# Heuristic coefficients for enhanced margin model
# Research-based conservative adjustments (±2 pts max total)
HEURISTIC_COEFFICIENTS = {
    # Pace control: ±0.5 pts per 5 tempo difference
    # Source: KenPom tempo correlation (52-55% win rate for tempo control)
    "pace_control_per_5_tempo": 0.10,
    # Shooting matchup: ±0.3 pts per 5% eFG advantage
    # Source: Dean Oliver Four Factors (40% weight on eFG%)
    "shooting_matchup_per_5_efg": 0.06,
    # Turnover battle: ±0.2 pts per 2% TO advantage
    # Source: Four Factors (25% weight on TO%)
    "turnover_battle_per_2_to": 0.10,
    # Rebounding edge: ±0.1 pts per 3% OR advantage
    # Source: Synergy offensive rebounding efficiency (~1.1 PPP)
    "rebounding_edge_per_3_or": 0.033,
    # Maximum total adjustment cap
    "max_total_adjustment": 2.0,
}

# Variance interaction coefficients for sigma calculation
VARIANCE_COEFFICIENTS = {
    # Tempo mismatch increases variance
    # Research: High tempo differential (10+ poss) adds ~10-15% variance
    "tempo_mismatch_factor": 0.015,
    # Style clash increases variance
    # Research: 3PT vs interior matchups have 12-18% higher variance
    "style_clash_3pt_vs_interior_boost": 1.10,
    "style_clash_similar_boost": 1.0,
}


@dataclass(frozen=True)
class MarginPrediction:
    """Complete prediction output with baseline and enhanced models.

    This dataclass contains both baseline (simple formula) and enhanced
    (context-aware) margin predictions, along with game-specific variance
    calculations and win probabilities.

    All margin fields are from the home team perspective:
    - Positive margin = home team favored
    - Negative margin = away team favored
    """

    # Baseline model (current formula)
    margin_baseline: float  # home_adj_em - away_adj_em + 3.5
    sigma_baseline: float  # (away_sigma + home_sigma) / 2.0
    win_prob_baseline: float  # Using margin_baseline and sigma_baseline

    # Enhanced model (with heuristic adjustments)
    margin_enhanced: float  # margin_baseline + adjustments
    margin_adjustment: float  # Total adjustment applied (±2 pts max)
    adjustment_breakdown: dict[str, float]  # Component adjustments

    # Game-level sigma (additive variance model)
    sigma_game: float  # sqrt(var_away + var_home + var_interaction)
    sigma_components: dict[str, float]  # Variance breakdown

    # Enhanced prediction
    win_prob_enhanced: float  # Using margin_enhanced and sigma_game

    # Metadata
    prediction_version: str  # "1.0"


def normal_cdf(x: float) -> float:
    """Approximate the cumulative distribution function of standard normal.

    Uses the error function approximation for faster calculation without scipy.

    Args:
        x: Standard score (z-score)

    Returns:
        Probability that a standard normal variable is less than x
    """
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def calculate_margin_baseline(
    home_adj_em: float,
    away_adj_em: float,
    home_court_advantage: float = DEFAULT_HOME_COURT_ADVANTAGE,
) -> float:
    """Calculate baseline margin prediction using current simple formula.

    Args:
        home_adj_em: Home team adjusted efficiency margin
        away_adj_em: Away team adjusted efficiency margin
        home_court_advantage: Home court points (default: 3.5, can be team-specific)

    Returns:
        Predicted margin from home team perspective (positive = home favored)

    Example:
        >>> calculate_margin_baseline(22.0, 12.3)  # Uses default 3.5 HCA
        13.2
        >>> calculate_margin_baseline(22.0, 12.3, 4.5)  # Kansas at Phog Allen
        13.7
    """
    return home_adj_em - away_adj_em + home_court_advantage


def calculate_sigma_baseline(away_sigma: float, home_sigma: float) -> float:
    """Calculate baseline sigma using simple average.

    Args:
        away_sigma: Away team sigma from snapshot
        home_sigma: Home team sigma from snapshot

    Returns:
        Average sigma for game

    Example:
        >>> calculate_sigma_baseline(10.5, 11.2)
        10.85
    """
    return (away_sigma + home_sigma) / 2.0


def _adjust_for_pace(matchup_features: MatchupFeatures, coefficients: dict[str, float]) -> float:
    """Calculate pace control adjustment.

    Args:
        matchup_features: Computed matchup features
        coefficients: Heuristic coefficients

    Returns:
        Pace control adjustment in points (positive = home advantage)
    """
    if matchup_features.pace_control == "home_controls":
        # Home team plays faster, small advantage
        pace_diff = abs(matchup_features.delta_tempo)
        return (pace_diff / 5.0) * coefficients["pace_control_per_5_tempo"]
    elif matchup_features.pace_control == "away_controls":
        # Away team plays faster, home loses advantage
        pace_diff = abs(matchup_features.delta_tempo)
        return -(pace_diff / 5.0) * coefficients["pace_control_per_5_tempo"]
    else:  # "neutral"
        return 0.0


def _adjust_for_shooting(
    matchup_features: MatchupFeatures, coefficients: dict[str, float]
) -> float:
    """Calculate shooting matchup adjustment.

    Args:
        matchup_features: Computed matchup features
        coefficients: Heuristic coefficients

    Returns:
        Shooting matchup adjustment in points (positive = home advantage)
    """
    # Net shooting advantage (home perspective)
    # shooting_defense_advantage = home offense vs away defense
    # shooting_advantage = away offense vs home defense
    net_shooting = matchup_features.shooting_defense_advantage - matchup_features.shooting_advantage
    return (net_shooting / 5.0) * coefficients["shooting_matchup_per_5_efg"]


def _adjust_for_turnovers(
    matchup_features: MatchupFeatures, coefficients: dict[str, float]
) -> float:
    """Calculate turnover battle adjustment.

    Args:
        matchup_features: Computed matchup features
        coefficients: Heuristic coefficients

    Returns:
        Turnover battle adjustment in points (positive = home advantage)
    """
    # Positive turnover_advantage = home forces TOs better than away commits
    return (matchup_features.turnover_advantage / 2.0) * coefficients["turnover_battle_per_2_to"]


def _adjust_for_rebounding(
    matchup_features: MatchupFeatures, coefficients: dict[str, float]
) -> float:
    """Calculate rebounding edge adjustment.

    Args:
        matchup_features: Computed matchup features
        coefficients: Heuristic coefficients

    Returns:
        Rebounding edge adjustment in points (positive = home advantage)
    """
    # Positive rebounding_advantage = away gets offensive boards (hurts home)
    return -(matchup_features.rebounding_advantage / 3.0) * coefficients["rebounding_edge_per_3_or"]


def calculate_margin_enhanced(
    home_adj_em: float,
    away_adj_em: float,
    matchup_features: MatchupFeatures,
    coefficients: Optional[dict[str, float]] = None,
) -> tuple[float, dict[str, float]]:
    """Calculate enhanced margin with heuristic adjustments.

    Applies conservative adjustments (±1-2 pts max) using matchup features.
    Uses team-specific home court advantage from matchup_features.home_court_factor.

    Args:
        home_adj_em: Home team adjusted efficiency margin
        away_adj_em: Away team adjusted efficiency margin
        matchup_features: Computed matchup features (includes team-specific HCA)
        coefficients: Optional learned coefficients (for ML model replacement)
                     If None, uses HEURISTIC_COEFFICIENTS

    Returns:
        Tuple of (enhanced_margin, adjustment_breakdown)

    Example:
        >>> matchup = MatchupFeatures(...)
        >>> margin, breakdown = calculate_margin_enhanced(22.0, 12.3, matchup)
        >>> print(f"Enhanced margin: {margin:.2f}")
        >>> print(f"Pace adjustment: {breakdown['pace_control']:.2f}")
    """
    coef = coefficients or HEURISTIC_COEFFICIENTS

    # Start with baseline using team-specific HCA from matchup features
    margin_baseline = calculate_margin_baseline(
        home_adj_em, away_adj_em, matchup_features.home_court_factor
    )

    # Calculate individual adjustments
    adjustments = {
        "pace_control": _adjust_for_pace(matchup_features, coef),
        "shooting_matchup": _adjust_for_shooting(matchup_features, coef),
        "turnover_battle": _adjust_for_turnovers(matchup_features, coef),
        "rebounding_edge": _adjust_for_rebounding(matchup_features, coef),
    }

    # Sum all adjustments
    total_adjustment = sum(adjustments.values())

    # Apply hard cap (±2 points maximum)
    max_adjustment = coef.get("max_total_adjustment", 2.0)
    if abs(total_adjustment) > max_adjustment:  # type: ignore[arg-type]
        total_adjustment = math.copysign(max_adjustment, total_adjustment)

    # Enhanced margin
    margin_enhanced = margin_baseline + total_adjustment

    return margin_enhanced, adjustments


def calculate_sigma_game(
    away_sigma: float, home_sigma: float, matchup_features: MatchupFeatures
) -> tuple[float, dict[str, float]]:
    """Calculate game-level sigma using additive variance model.

    Formula: sigma_game = sqrt(var_away + var_home + var_interaction)

    Variance interaction accounts for:
    - Tempo mismatch (higher mismatch = higher variance)
    - Style clash (3PT vs interior = higher variance)

    Args:
        away_sigma: Away team sigma from snapshot
        home_sigma: Home team sigma from snapshot
        matchup_features: Computed matchup features

    Returns:
        Tuple of (sigma_game, variance_components)

    Example:
        >>> matchup = MatchupFeatures(...)
        >>> sigma, components = calculate_sigma_game(10.5, 11.2, matchup)
        >>> print(f"Game sigma: {sigma:.2f}")
        >>> print(f"Interaction variance: {components['var_interaction']:.2f}")
    """
    coef = VARIANCE_COEFFICIENTS

    # Base variances (sigma squared)
    var_away = away_sigma**2
    var_home = home_sigma**2

    # Interaction variance from tempo mismatch
    tempo_var = coef["tempo_mismatch_factor"] * (matchup_features.tempo_mismatch**2)

    # Style clash multiplier
    if matchup_features.style_clash == "3pt_vs_interior":
        style_multiplier = coef["style_clash_3pt_vs_interior_boost"]
    else:
        style_multiplier = coef["style_clash_similar_boost"]

    # Total interaction variance
    var_interaction = tempo_var * style_multiplier

    # Additive variance model
    total_variance = var_away + var_home + var_interaction
    sigma_game = math.sqrt(total_variance)

    # Ensure sigma_game >= max(away_sigma, home_sigma)
    # (game variance can't be less than team variance)
    sigma_game = max(sigma_game, away_sigma, home_sigma)

    components = {
        "var_away": var_away,
        "var_home": var_home,
        "var_interaction": var_interaction,
        "var_total": total_variance,
    }

    return sigma_game, components


def predict_game(
    away: pd.Series,
    home: pd.Series,
    matchup_features: Optional[MatchupFeatures] = None,
    coefficients: Optional[dict[str, float]] = None,
) -> MarginPrediction:
    """Complete game prediction with baseline and enhanced models.

    This is the primary entry point for predictions. Computes both
    baseline (current formula) and enhanced (with adjustments) predictions.

    Args:
        away: Away team data (from enriched snapshot)
        home: Home team data (from enriched snapshot)
        matchup_features: Pre-computed matchup features (computed if None)
        coefficients: Optional ML coefficients (uses heuristics if None)

    Returns:
        MarginPrediction with complete baseline and enhanced predictions

    Example:
        >>> df = load_enriched_snapshot("data/kenpom_ratings_2025.csv")
        >>> oregon = find_team(df, "Oregon")
        >>> gonzaga = find_team(df, "Gonzaga")
        >>> prediction = predict_game(oregon, gonzaga)
        >>> print(f"Baseline: {prediction.margin_baseline:.1f}")
        >>> print(f"Enhanced: {prediction.margin_enhanced:.1f}")
        >>> print(f"Adjustment: {prediction.margin_adjustment:+.1f}")
    """
    # Compute matchup features if not provided
    if matchup_features is None:
        from kenpom_client.matchup import calculate_matchup_features

        matchup_features = calculate_matchup_features(away, home)

    # Baseline predictions (now uses team-specific HCA from matchup_features)
    margin_baseline = calculate_margin_baseline(
        home["adj_em"], away["adj_em"], matchup_features.home_court_factor
    )
    sigma_baseline = calculate_sigma_baseline(away["sigma"], home["sigma"])
    win_prob_baseline = normal_cdf(margin_baseline / sigma_baseline)

    # Enhanced predictions
    margin_enhanced, adjustment_breakdown = calculate_margin_enhanced(
        home["adj_em"], away["adj_em"], matchup_features, coefficients
    )

    sigma_game, sigma_components = calculate_sigma_game(
        away["sigma"], home["sigma"], matchup_features
    )

    win_prob_enhanced = normal_cdf(margin_enhanced / sigma_game)

    return MarginPrediction(
        # Baseline
        margin_baseline=margin_baseline,
        sigma_baseline=sigma_baseline,
        win_prob_baseline=win_prob_baseline,
        # Enhanced
        margin_enhanced=margin_enhanced,
        margin_adjustment=margin_enhanced - margin_baseline,
        adjustment_breakdown=adjustment_breakdown,
        # Game sigma
        sigma_game=sigma_game,
        sigma_components=sigma_components,
        # Enhanced win probability
        win_prob_enhanced=win_prob_enhanced,
        # Metadata
        prediction_version="1.0",
    )
