"""Analyze today's NCAA Men's Basketball games using enriched KenPom data.

This script demonstrates how to use the snapshot enrichment system for:
- Win probability calculations
- Predicted margins
- Game variance analysis
- Advanced basketball analytics
"""

from __future__ import annotations

import math
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

# Today's games (from ESPN schedule - December 21, 2025)
TODAYS_GAMES = [
    ("Colgate", "Florida"),
    ("Clinton College", "Winthrop"),
    ("UMass Lowell", "Boston University"),
    ("Charleston", "Northern Kentucky"),
    ("Rosemont", "Navy"),
    ("Pittsburgh", "Penn State"),
    ("Penn State Brandywine", "Mount St. Mary's"),
    ("Vanderbilt", "Wake Forest"),
    ("Lehigh", "Monmouth"),
    ("Quinnipiac", "Hofstra"),
    ("Southern", "Baylor"),
    ("Ole Miss", "NC State"),
    ("Stony Brook", "Marist"),
    ("Kennesaw State", "Alabama"),
    ("Holy Family", "Delaware State"),
    ("Murray State", "Valparaiso"),
    ("Southern Illinois", "Bradley"),
    ("Virginia-Lynchburg", "UNC Greensboro"),
    ("Dallas", "Stephen F. Austin"),
    ("Presbyterian", "Manhattan"),
    ("Cumberland", "Middle Tennessee"),
    ("Charleston Southern", "Furman"),
    ("UIC", "Charlotte"),
    ("Maine", "Drexel"),
    ("Loyola Maryland", "George Mason"),
    ("Central Arkansas", "SMU"),
    ("Purdue Fort Wayne", "Notre Dame"),
    ("Cal State Fullerton", "Oklahoma State"),
    ("VMI", "Radford"),
    ("Gardner-Webb", "Tennessee"),
    ("Cornell", "Albany"),
    ("Chattanooga", "Alabama A&M"),
    ("UNC Asheville", "UAB"),
    ("UMBC", "South Florida"),
    ("Northern Arizona", "Incarnate Word"),
    ("Oregon State", "Arizona State"),
    ("New Hampshire", "Saint Louis"),
    ("Cincinnati", "Clemson"),
    ("La Salle", "Michigan"),
    ("UC Santa Cruz", "USC"),
    ("Drake", "Evansville"),
    ("East Texas A&M", "Texas A&M"),
    ("Florida A&M", "TCU"),
    ("North Florida", "Miami"),
    ("Sam Houston", "New Mexico State"),
    ("UConn", "DePaul"),
    ("Indiana State", "Illinois State"),
    ("Eastern Kentucky", "Wichita State"),
    ("Milwaukee", "Cleveland State"),
    ("Columbia", "California"),
    ("Long Beach State", "Iowa State"),
    ("Oregon", "Gonzaga"),
    ("Austin Peay", "Kansas City"),
    ("Campbell", "Minnesota"),
    ("UC Davis", "Idaho State"),
    ("Morgan State", "San Francisco"),
    ("UC Irvine", "North Dakota State"),
    ("Idaho", "Cal Poly"),
    ("North Dakota", "Nebraska"),
    ("Norfolk State", "UTEP"),
]


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


def analyze_game(df: pd.DataFrame, away_team: str, home_team: str) -> dict[str, float | str | None]:
    """Analyze a single game matchup with enhanced predictions.

    Args:
        df: Enriched snapshot DataFrame
        away_team: Away team name
        home_team: Home team name

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

    return "\n".join(lines)


def main():
    """Analyze today's games."""
    # Load enriched snapshot
    snapshot_path = Path("data/kenpom_ratings_2025_2025-12-21_enriched.csv")

    if not snapshot_path.exists():
        print(f"ERROR: Snapshot not found at {snapshot_path}")
        print(
            "Run: uv run kenpom ratings --y 2025 --date 2025-12-21 --four-factors --point-dist --sigma"
        )
        return

    print("Loading enriched KenPom snapshot...")
    df = load_enriched_snapshot(snapshot_path)
    print(f"Loaded {len(df)} teams with {len(df.columns)} metrics\n")

    # Analyze games
    print("=" * 80)
    print("TODAY'S NCAA MEN'S BASKETBALL GAME PREDICTIONS")
    print("Using KenPom Enriched Snapshot (2025 Season)")
    print("Date: 2025-12-21")
    print("=" * 80)

    analyses = []
    for away, home in TODAYS_GAMES:
        analysis = analyze_game(df, away, home)
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

        print(f"\nGames Analyzed: {len(valid_analyses)}/{len(TODAYS_GAMES)}")
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

        # Most uncertain games (highest sigma)
        sorted_by_sigma = sorted(valid_analyses, key=lambda x: x["avg_sigma"], reverse=True)
        print("\nMost Volatile Games (Highest Variance):")
        for i, game in enumerate(sorted_by_sigma[:3], 1):
            print(
                f"  {i}. {game['away_team']} @ {game['home_team']} (sigma={game['avg_sigma']:.2f})"
            )

    # Export to CSV
    results_df = pd.DataFrame(valid_analyses)
    output_path = Path("data/todays_game_predictions_2025-12-21.csv")
    results_df.to_csv(output_path, index=False)
    print(f"\nPredictions exported to: {output_path}")


if __name__ == "__main__":
    main()
