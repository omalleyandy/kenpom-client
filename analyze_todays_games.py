"""Analyze today's NCAA Men's Basketball games using enriched KenPom data.

This script demonstrates how to use the snapshot enrichment system for:
- Win probability calculations
- Predicted margins
- Game variance analysis
- Advanced basketball analytics

Reads games from overtime.ag odds file and combines with KenPom predictions.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

# Import matchup feature engineering and prediction module
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))
from kenpom_client.matchup import calculate_matchup_features
from kenpom_client.prediction import predict_game

# Home court advantage in college basketball (points)
HOME_COURT_ADVANTAGE = 3.5

def load_todays_odds(odds_date: Optional[date] = None) -> pd.DataFrame:
    """Load today's games from overtime.ag odds file.

    Args:
        odds_date: Date to load odds for (defaults to today)

    Returns:
        DataFrame with columns: away_team, home_team, market_spread, etc.
    """
    if odds_date is None:
        odds_date = date.today()

    date_str = odds_date.strftime("%Y-%m-%d")

    # Try dated file first, then generic file
    odds_paths = [
        Path(f"data/overtime_ncaab_odds_{date_str}.csv"),
        Path("data/overtime_odds.csv"),
    ]

    for odds_path in odds_paths:
        if odds_path.exists():
            print(f"Loading odds from: {odds_path}")
            return pd.read_csv(odds_path)

    print(f"WARNING: No odds file found. Tried: {[str(p) for p in odds_paths]}")
    return pd.DataFrame()


def get_games_from_odds(odds_df: pd.DataFrame) -> list[tuple[str, str]]:
    """Extract (away_team, home_team) tuples from odds DataFrame."""
    if odds_df.empty:
        return []
    return [(row["away_team"], row["home_team"]) for _, row in odds_df.iterrows()]


def get_market_odds(odds_df: pd.DataFrame, away_team: str, home_team: str) -> dict:
    """Get market odds for a specific game.

    Args:
        odds_df: DataFrame with odds data
        away_team: Away team name
        home_team: Home team name

    Returns:
        Dictionary with market_spread, home_ml, away_ml, total, etc.
    """
    if odds_df.empty:
        return {}

    # Find matching game (case-insensitive)
    mask = (odds_df["away_team"].str.lower() == away_team.lower()) & (
        odds_df["home_team"].str.lower() == home_team.lower()
    )
    match = odds_df[mask]

    if match.empty:
        return {}

    row = match.iloc[0]
    return {
        "market_spread": row.get("market_spread"),
        "spread_odds": row.get("spread_odds"),
        "home_ml": row.get("home_ml"),
        "away_ml": row.get("away_ml"),
        "total": row.get("total"),
        "over_odds": row.get("over_odds"),
        "under_odds": row.get("under_odds"),
        "game_time": row.get("game_time"),
    }


def load_enriched_snapshot(snapshot_path: Path) -> pd.DataFrame:
    """Load the enriched KenPom snapshot."""
    return pd.read_csv(snapshot_path)


def find_team(df: pd.DataFrame, team_name: str) -> Optional[pd.Series]:
    """Find a team in the snapshot (case-insensitive, fuzzy matching)."""
    # Try exact match first
    exact_match = df[df["team"].str.lower() == team_name.lower()]
    if not exact_match.empty:
        return exact_match.iloc[0]

    # Try partial match (contains)
    partial_match = df[df["team"].str.contains(team_name, case=False, na=False)]
    if not partial_match.empty:
        return partial_match.iloc[0]

    return None


def normal_cdf(x: float) -> float:
    """Approximate the cumulative distribution function of standard normal.

    Uses the error function approximation for faster calculation without scipy.

    Args:
        x: Standard score (z-score)

    Returns:
        Probability that a standard normal variable is less than x
    """
    # Abramowitz and Stegun approximation
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def calculate_win_probability(predicted_margin: float, sigma: float) -> tuple[float, float]:
    """Calculate win probability using normal distribution.

    Args:
        predicted_margin: Expected margin (positive = team favored)
        sigma: Standard deviation of scoring margin

    Returns:
        Tuple of (win_probability, cover_probability_if_spread_is_margin)
    """
    # Win probability: P(margin > 0)
    # Convert to z-score and use normal CDF
    z_score = predicted_margin / sigma
    win_prob = normal_cdf(z_score)

    # If the spread equals the predicted margin, 50% cover probability
    cover_prob = 0.5

    return win_prob, cover_prob


def analyze_game(
    df: pd.DataFrame,
    away_team: str,
    home_team: str,
    market_odds: Optional[dict] = None,
) -> dict[str, float | str | None]:
    """Analyze a single game matchup with enhanced predictions.

    Args:
        df: Enriched snapshot DataFrame
        away_team: Away team name
        home_team: Home team name
        market_odds: Optional dictionary with market spread, ML, totals

    Returns:
        Dictionary with game analysis including baseline and enhanced predictions
    """
    away = find_team(df, away_team)
    home = find_team(df, home_team)

    if away is None or home is None:
        return {
            "away_team": away_team,
            "home_team": home_team,
            "error": f"Team not found: {away_team if away is None else home_team}",
        }

    market_odds = market_odds or {}

    # Get full prediction (baseline + enhanced)
    prediction = predict_game(away, home)

    # Calculate matchup features for CSV export
    matchup = calculate_matchup_features(away, home)

    # Helper for confidence classification
    def calculate_confidence(win_prob: float) -> str:
        if abs(win_prob - 0.5) > 0.3:
            return "High"
        elif abs(win_prob - 0.5) > 0.15:
            return "Medium"
        else:
            return "Low"

    return {
        # ===== EXISTING FIELDS (backward compatibility) =====
        "away_team": away["team"],
        "away_adj_em": away["adj_em"],
        "away_adj_oe": away["adj_oe"],
        "away_adj_de": away["adj_de"],
        "away_sigma": away["sigma"],
        "home_team": home["team"],
        "home_adj_em": home["adj_em"],
        "home_adj_oe": home["adj_oe"],
        "home_adj_de": home["adj_de"],
        "home_sigma": home["sigma"],
        # Keep these for backward compatibility
        "predicted_margin": prediction.margin_baseline,
        "avg_sigma": prediction.sigma_baseline,
        "home_win_prob": prediction.win_prob_baseline,
        "away_win_prob": 1 - prediction.win_prob_baseline,
        "confidence": calculate_confidence(prediction.win_prob_baseline),
        # ===== NEW BASELINE FIELDS (explicit naming) =====
        "margin_baseline": prediction.margin_baseline,
        "sigma_baseline": prediction.sigma_baseline,
        "win_prob_baseline": prediction.win_prob_baseline,
        # ===== NEW ENHANCED FIELDS =====
        "margin_enhanced": prediction.margin_enhanced,
        "margin_adjustment": prediction.margin_adjustment,
        "sigma_game": prediction.sigma_game,
        "win_prob_enhanced": prediction.win_prob_enhanced,
        # ===== ADJUSTMENT BREAKDOWN (4 fields) =====
        "adj_pace_control": prediction.adjustment_breakdown["pace_control"],
        "adj_shooting_matchup": prediction.adjustment_breakdown["shooting_matchup"],
        "adj_turnover_battle": prediction.adjustment_breakdown["turnover_battle"],
        "adj_rebounding_edge": prediction.adjustment_breakdown["rebounding_edge"],
        # ===== VARIANCE BREAKDOWN (3 fields) =====
        "var_away": prediction.sigma_components["var_away"],
        "var_home": prediction.sigma_components["var_home"],
        "var_interaction": prediction.sigma_components["var_interaction"],
        # ===== EXISTING MATCHUP FEATURES (15 fields) =====
        "delta_adj_em": matchup.delta_adj_em,
        "delta_adj_oe": matchup.delta_adj_oe,
        "delta_adj_de": matchup.delta_adj_de,
        "delta_tempo": matchup.delta_tempo,
        "shooting_advantage": matchup.shooting_advantage,
        "shooting_defense_advantage": matchup.shooting_defense_advantage,
        "turnover_advantage": matchup.turnover_advantage,
        "rebounding_advantage": matchup.rebounding_advantage,
        "tempo_mismatch": matchup.tempo_mismatch,
        "pace_control": matchup.pace_control,
        "home_3pt_reliance": matchup.home_3pt_reliance,
        "away_3pt_reliance": matchup.away_3pt_reliance,
        "style_clash": matchup.style_clash,
        "home_court_factor": matchup.home_court_factor,
        "feature_version": matchup.feature_version,
        # ===== METADATA =====
        "prediction_version": prediction.prediction_version,
        # ===== MARKET ODDS (from overtime.ag) =====
        "market_spread": market_odds.get("market_spread"),
        "spread_odds": market_odds.get("spread_odds"),
        "market_home_ml": market_odds.get("home_ml"),
        "market_away_ml": market_odds.get("away_ml"),
        "market_total": market_odds.get("total"),
        "over_odds": market_odds.get("over_odds"),
        "under_odds": market_odds.get("under_odds"),
        "game_time": market_odds.get("game_time"),
        # ===== EDGE CALCULATIONS (KenPom vs Market) =====
        "spread_edge": (
            prediction.margin_enhanced - market_odds.get("market_spread", 0)
            if market_odds.get("market_spread") is not None
            else None
        ),
    }


def format_game_analysis(analysis: dict) -> str:
    """Format game analysis for display."""
    if "error" in analysis:
        return f"ERROR: {analysis['error']}"

    lines = []
    lines.append(f"\n{'=' * 80}")
    lines.append(f"{analysis['away_team']} @ {analysis['home_team']}")
    lines.append(f"{'-' * 80}")

    # Team stats
    lines.append(f"\nAway: {analysis['away_team']}")
    lines.append(f"  AdjEM: {analysis['away_adj_em']:>6.2f}")
    lines.append(f"  AdjOE: {analysis['away_adj_oe']:>6.2f}")
    lines.append(f"  AdjDE: {analysis['away_adj_de']:>6.2f}")
    lines.append(f"  Sigma: {analysis['away_sigma']:>6.2f}")

    lines.append(f"\nHome: {analysis['home_team']}")
    lines.append(f"  AdjEM: {analysis['home_adj_em']:>6.2f}")
    lines.append(f"  AdjOE: {analysis['home_adj_oe']:>6.2f}")
    lines.append(f"  AdjDE: {analysis['home_adj_de']:>6.2f}")
    lines.append(f"  Sigma: {analysis['home_sigma']:>6.2f}")

    # Prediction
    lines.append("\nPrediction:")
    lines.append(
        f"  Predicted Margin: {analysis['home_team']} by {analysis['predicted_margin']:>5.1f}"
    )
    lines.append(f"  Game Variance (Avg Sigma): {analysis['avg_sigma']:>6.2f}")
    lines.append(f"  {analysis['home_team']} Win Probability: {analysis['home_win_prob']:.1%}")
    lines.append(f"  {analysis['away_team']} Win Probability: {analysis['away_win_prob']:.1%}")
    lines.append(f"  Confidence: {analysis['confidence']}")

    # Market odds (if available)
    if analysis.get("market_spread") is not None:
        lines.append("\nMarket Odds:")
        lines.append(f"  Spread: {analysis['market_spread']:>+5.1f} ({analysis.get('spread_odds', 'N/A')})")
        if analysis.get("market_home_ml"):
            lines.append(f"  Home ML: {int(analysis['market_home_ml']):>+5d}")
        if analysis.get("market_away_ml"):
            lines.append(f"  Away ML: {int(analysis['market_away_ml']):>+5d}")
        if analysis.get("market_total"):
            lines.append(f"  Total: {analysis['market_total']}")
        if analysis.get("game_time"):
            lines.append(f"  Game Time: {analysis['game_time']}")

        # Edge calculation
        if analysis.get("spread_edge") is not None:
            edge = analysis["spread_edge"]
            edge_label = "HOME" if edge > 0 else "AWAY"
            lines.append(f"\n  *** EDGE: {abs(edge):.1f} pts on {edge_label} ***")

    return "\n".join(lines)


def main():
    """Analyze today's games using odds from overtime.ag and KenPom predictions."""
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    # Load odds from overtime.ag
    odds_df = load_todays_odds(today)

    if odds_df.empty:
        print("ERROR: No odds file found. Run: uv run fetch-odds")
        return

    games = get_games_from_odds(odds_df)
    print(f"Found {len(games)} games in odds file\n")

    # Find enriched snapshot (try today, then yesterday)
    snapshot_paths = [
        Path(f"data/kenpom_ratings_2025_{date_str}_enriched.csv"),
        Path(f"data/kenpom_ratings_2025_{(today.replace(day=today.day - 1)).strftime('%Y-%m-%d')}_enriched.csv"),
    ]

    snapshot_path = None
    for path in snapshot_paths:
        if path.exists():
            snapshot_path = path
            break

    if snapshot_path is None:
        print(f"ERROR: No enriched snapshot found. Tried: {[str(p) for p in snapshot_paths]}")
        print(f"Run: uv run kenpom ratings --y 2025 --date {date_str} --four-factors --point-dist --sigma")
        return

    print(f"Loading enriched KenPom snapshot: {snapshot_path}")
    df = load_enriched_snapshot(snapshot_path)
    print(f"Loaded {len(df)} teams with {len(df.columns)} metrics\n")

    # Analyze games
    print("=" * 80)
    print("TODAY'S NCAA MEN'S BASKETBALL GAME PREDICTIONS")
    print("Using KenPom Enriched Snapshot + Overtime.ag Market Odds")
    print(f"Date: {date_str}")
    print("=" * 80)

    analyses = []
    for away, home in games:
        market_odds = get_market_odds(odds_df, away, home)
        analysis = analyze_game(df, away, home, market_odds)
        analyses.append(analysis)
        print(format_game_analysis(analysis))

    # Summary statistics
    print(f"\n\n{'=' * 80}")
    print("SUMMARY STATISTICS")
    print(f"{'=' * 80}")

    valid_analyses = [a for a in analyses if "error" not in a]

    if valid_analyses:
        avg_margin = sum(abs(a["predicted_margin"]) for a in valid_analyses) / len(valid_analyses)
        avg_sigma = sum(a["avg_sigma"] for a in valid_analyses) / len(valid_analyses)
        close_games = sum(1 for a in valid_analyses if abs(a["predicted_margin"]) < 5)

        print(f"\nGames Analyzed: {len(valid_analyses)}/{len(games)}")
        print(f"Average Predicted Margin: {avg_margin:.1f} points")
        print(f"Average Game Sigma: {avg_sigma:.2f}")
        print(f"Close Games (margin < 5): {close_games} ({close_games / len(valid_analyses):.1%})")

        # Biggest favorites
        sorted_by_margin = sorted(
            valid_analyses, key=lambda x: abs(x["predicted_margin"]), reverse=True
        )
        print("\nBiggest Favorites:")
        for i, game in enumerate(sorted_by_margin[:3], 1):
            favorite = game["home_team"] if game["predicted_margin"] > 0 else game["away_team"]
            margin = abs(game["predicted_margin"])
            print(f"  {i}. {favorite} by {margin:.1f} points")

        # Best edges (KenPom vs Market)
        games_with_edge = [a for a in valid_analyses if a.get("spread_edge") is not None]
        if games_with_edge:
            sorted_by_edge = sorted(games_with_edge, key=lambda x: abs(x["spread_edge"]), reverse=True)
            print("\nBest Spread Edges (KenPom vs Market):")
            for i, game in enumerate(sorted_by_edge[:5], 1):
                edge = game["spread_edge"]
                side = game["home_team"] if edge > 0 else game["away_team"]
                print(f"  {i}. {side} ({abs(edge):+.1f} pts) - {game['away_team']} @ {game['home_team']}")

        # Most uncertain games (highest sigma)
        sorted_by_sigma = sorted(valid_analyses, key=lambda x: x["avg_sigma"], reverse=True)
        print("\nMost Volatile Games (Highest Variance):")
        for i, game in enumerate(sorted_by_sigma[:3], 1):
            print(
                f"  {i}. {game['away_team']} @ {game['home_team']} (sigma={game['avg_sigma']:.2f})"
            )

    # Export to CSV
    results_df = pd.DataFrame(valid_analyses)
    output_path = Path(f"data/todays_game_predictions_{date_str}.csv")
    results_df.to_csv(output_path, index=False)
    print(f"\nPredictions exported to: {output_path}")


if __name__ == "__main__":
    main()
