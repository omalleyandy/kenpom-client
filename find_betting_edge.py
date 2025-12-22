"""Find betting edge by analyzing today's game predictions.

This script demonstrates how to identify analytical edge using the enriched
KenPom predictions. It shows practical examples of finding value in spreads,
moneylines, and totals.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


def normal_cdf(x: float) -> float:
    """Approximate the cumulative distribution function of standard normal."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def cover_probability(predicted_margin: float, spread: float, avg_sigma: float) -> float:
    """Calculate probability of covering a specific spread.

    Args:
        predicted_margin: Model's predicted margin (home team perspective)
        spread: Market spread (negative = home favored)
        avg_sigma: Average game variance

    Returns:
        Probability of home team covering the spread (0.0 to 1.0)
    """
    z_score = (predicted_margin - spread) / avg_sigma
    return normal_cdf(z_score)


def calculate_expected_value(win_probability: float, american_odds: int) -> tuple[float, float]:
    """Calculate expected value and decimal odds for a bet.

    Args:
        win_probability: Model's assessed probability of winning (0.0 to 1.0)
        american_odds: American odds format (e.g., -110, +130)

    Returns:
        Tuple of (expected_value, decimal_odds)
    """
    if american_odds > 0:
        decimal_odds = 1 + (american_odds / 100)
    else:
        decimal_odds = 1 + (100 / abs(american_odds))

    ev = (win_probability * (decimal_odds - 1)) - (1 - win_probability)
    return ev, decimal_odds


def american_to_implied_probability(american_odds: int) -> float:
    """Convert American odds to implied probability.

    Args:
        american_odds: American odds format (e.g., -110, +130)

    Returns:
        Implied probability (0.0 to 1.0)
    """
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)


def analyze_spread_value(game: pd.Series, market_spread: float, odds: int = -110) -> dict:
    """Analyze value in a point spread bet.

    Args:
        game: Game data from predictions CSV
        market_spread: Market spread (negative = home favored)
        odds: Odds for the bet (default -110)

    Returns:
        Dictionary with analysis results
    """
    predicted_margin = game["predicted_margin"]
    avg_sigma = game["avg_sigma"]

    # Calculate edge
    spread_edge = predicted_margin - market_spread

    # Calculate cover probability
    home_cover_prob = cover_probability(predicted_margin, market_spread, avg_sigma)
    away_cover_prob = 1 - home_cover_prob

    # Market implied probability (typically 52.4% for -110)
    market_implied = american_to_implied_probability(odds)

    # Expected value
    home_ev, _ = calculate_expected_value(home_cover_prob, odds)
    away_ev, _ = calculate_expected_value(away_cover_prob, odds)

    # Determine recommendation
    if abs(spread_edge) >= 2.0:
        strength = "STRONG"
    elif abs(spread_edge) >= 1.0:
        strength = "MODERATE"
    else:
        strength = "WEAK"

    if spread_edge > 0:
        # Home team undervalued (market spread too high)
        recommendation = f"Bet {game['home_team']} {market_spread:+.1f}"
        edge_team = game["home_team"]
        edge_ev = home_ev
    else:
        # Away team undervalued (market spread too low)
        recommendation = f"Bet {game['away_team']} {-market_spread:+.1f}"
        edge_team = game["away_team"]
        edge_ev = away_ev

    return {
        "game": f"{game['away_team']} @ {game['home_team']}",
        "model_spread": f"{game['home_team']} {predicted_margin:+.1f}",
        "market_spread": f"{game['home_team']} {market_spread:+.1f}",
        "spread_edge": spread_edge,
        "home_cover_prob": home_cover_prob,
        "away_cover_prob": away_cover_prob,
        "market_implied": market_implied,
        "recommendation": recommendation,
        "edge_team": edge_team,
        "expected_value": edge_ev,
        "strength": strength,
        "avg_sigma": avg_sigma,
    }


def analyze_moneyline_value(game: pd.Series, home_ml: int, away_ml: int) -> dict:
    """Analyze value in moneyline bets.

    Args:
        game: Game data from predictions CSV
        home_ml: Home team moneyline (American odds)
        away_ml: Away team moneyline (American odds)

    Returns:
        Dictionary with analysis results
    """
    model_home_prob = game["home_win_prob"]
    model_away_prob = game["away_win_prob"]

    # Market implied probabilities
    market_home_prob = american_to_implied_probability(home_ml)
    market_away_prob = american_to_implied_probability(away_ml)

    # Edge (difference in probability)
    home_edge = model_home_prob - market_home_prob
    away_edge = model_away_prob - market_away_prob

    # Expected values
    home_ev, _ = calculate_expected_value(model_home_prob, home_ml)
    away_ev, _ = calculate_expected_value(model_away_prob, away_ml)

    # Determine best bet
    if home_ev > away_ev and home_ev > 0:
        best_bet = game["home_team"]
        best_odds = home_ml
        best_ev = home_ev
        prob_edge = home_edge
    elif away_ev > 0:
        best_bet = game["away_team"]
        best_odds = away_ml
        best_ev = away_ev
        prob_edge = away_edge
    else:
        best_bet = "PASS"
        best_odds = 0
        best_ev = max(home_ev, away_ev)
        prob_edge = max(home_edge, away_edge)

    # Strength
    if abs(prob_edge) >= 0.05:
        strength = "STRONG"
    elif abs(prob_edge) >= 0.03:
        strength = "MODERATE"
    else:
        strength = "WEAK"

    return {
        "game": f"{game['away_team']} @ {game['home_team']}",
        "model_probs": f"{model_home_prob:.1%} / {model_away_prob:.1%}",
        "market_probs": f"{market_home_prob:.1%} / {market_away_prob:.1%}",
        "home_edge": home_edge,
        "away_edge": away_edge,
        "best_bet": best_bet,
        "best_odds": best_odds,
        "expected_value": best_ev,
        "prob_edge": prob_edge,
        "strength": strength,
    }


def main():
    """Analyze today's games for betting edge."""
    # Load predictions
    predictions_path = Path("data/todays_game_predictions_2025-12-21.csv")

    if not predictions_path.exists():
        print(f"ERROR: Predictions file not found at {predictions_path}")
        print("Run analyze_todays_games.py first to generate predictions")
        return

    df = pd.read_csv(predictions_path)
    print("=" * 80)
    print("BETTING EDGE ANALYSIS - December 21, 2025")
    print("=" * 80)
    print(f"\nAnalyzing {len(df)} games for value opportunities...\n")

    # =========================================================================
    # Example 1: Point Spread Analysis
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXAMPLE 1: POINT SPREAD VALUE ANALYSIS")
    print("=" * 80)
    print("\nScenario: You have market spreads and want to find edge\n")

    # Hypothetical market spreads for demonstration
    example_spreads = {
        "Oregon @ Gonzaga": -12.0,  # Gonzaga favored by 12
        "UConn @ DePaul": -22.0,  # UConn favored by 22
        "Pittsburgh @ Penn State": -3.5,  # Penn State favored by 3.5
    }

    spread_opportunities = []

    for matchup, market_spread in example_spreads.items():
        # Find game in predictions
        away, home = matchup.split(" @ ")
        game = df[(df["away_team"] == away) & (df["home_team"] == home)]

        if game.empty:
            print(f"Game not found: {matchup}")
            continue

        analysis = analyze_spread_value(game.iloc[0], market_spread)
        spread_opportunities.append(analysis)

        print(f"\nGame: {analysis['game']}")
        print(f"  Model: {analysis['model_spread']}")
        print(f"  Market: {analysis['market_spread']}")
        print(f"  Spread Edge: {analysis['spread_edge']:+.1f} points")
        print(
            f"  Cover Probability: Home {analysis['home_cover_prob']:.1%} "
            f"/ Away {analysis['away_cover_prob']:.1%}"
        )
        print(f"  Expected Value: {analysis['expected_value']:+.1%}")
        print(f"  Recommendation: {analysis['recommendation']} [{analysis['strength']}]")

    # =========================================================================
    # Example 2: Moneyline Value Analysis
    # =========================================================================
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: MONEYLINE VALUE ANALYSIS")
    print("=" * 80)
    print("\nScenario: Close games where moneyline offers better value than spread\n")

    # Find close games (predicted margin < 5)
    df[abs(df["predicted_margin"]) < 5].head(3)

    # Hypothetical moneylines for demonstration
    example_moneylines = [
        ("Vanderbilt @ Wake Forest", -150, 130),  # Wake Forest -150, Vanderbilt +130
        ("Pittsburgh @ Penn State", -140, 120),  # Penn State -140, Pittsburgh +120
        ("Cincinnati @ Clemson", 105, -125),  # Cincinnati +105, Clemson -125
    ]

    ml_opportunities = []

    for matchup, home_ml, away_ml in example_moneylines:
        away, home = matchup.split(" @ ")
        game = df[(df["away_team"] == away) & (df["home_team"] == home)]

        if game.empty:
            continue

        analysis = analyze_moneyline_value(game.iloc[0], home_ml, away_ml)
        ml_opportunities.append(analysis)

        print(f"\nGame: {analysis['game']}")
        print(f"  Model Win Probs: {analysis['model_probs']}")
        print(f"  Market Win Probs: {analysis['market_probs']}")
        print(f"  Probability Edge: {analysis['prob_edge']:+.1%}")
        print(f"  Best Bet: {analysis['best_bet']} ({analysis['best_odds']:+d})")
        print(f"  Expected Value: {analysis['expected_value']:+.1%} [{analysis['strength']}]")

    # =========================================================================
    # Example 3: Finding Best Opportunities
    # =========================================================================
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: TOP BETTING OPPORTUNITIES")
    print("=" * 80)
    print("\nBased on hypothetical market lines, here are the best value plays:\n")

    # Combine all opportunities
    all_opportunities = []

    # Spread opportunities
    for opp in spread_opportunities:
        if opp["strength"] in ["STRONG", "MODERATE"]:
            all_opportunities.append(
                {
                    "type": "SPREAD",
                    "recommendation": opp["recommendation"],
                    "edge": abs(opp["spread_edge"]),
                    "ev": opp["expected_value"],
                    "strength": opp["strength"],
                }
            )

    # Moneyline opportunities
    for opp in ml_opportunities:
        if opp["strength"] in ["STRONG", "MODERATE"] and opp["best_bet"] != "PASS":
            all_opportunities.append(
                {
                    "type": "MONEYLINE",
                    "recommendation": f"{opp['best_bet']} ML ({opp['best_odds']:+d})",
                    "edge": abs(opp["prob_edge"]) * 100,  # Convert to points for sorting
                    "ev": opp["expected_value"],
                    "strength": opp["strength"],
                }
            )

    # Sort by edge
    all_opportunities.sort(key=lambda x: x["edge"], reverse=True)

    # Print top opportunities
    for i, opp in enumerate(all_opportunities[:5], 1):
        print(f"{i}. {opp['recommendation']}")
        print(f"   Type: {opp['type']} | Strength: {opp['strength']}")
        print(f"   Expected Value: {opp['ev']:+.1%}")
        print()

    # =========================================================================
    # Example 4: Games to Avoid
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXAMPLE 4: GAMES TO AVOID (No Clear Edge)")
    print("=" * 80)
    print("\nGames where model and market are aligned (no value):\n")

    # Demonstrate with games where hypothetical market matches model
    avoid_examples = [
        "Gardner-Webb @ Tennessee",
        "Kennesaw State @ Alabama",
        "Southern @ Baylor",
    ]

    for matchup in avoid_examples:
        away, home = matchup.split(" @ ")
        game = df[(df["away_team"] == away) & (df["home_team"] == home)]

        if not game.empty:
            g = game.iloc[0]
            print(f"Game: {matchup}")
            print(f"  Model: {home} {g['predicted_margin']:+.1f}")
            print(f"  Hypothetical Market: {home} {g['predicted_margin']:+.1f} (same as model)")
            print("  Edge: 0.0 points -> PASS\n")

    # =========================================================================
    # Summary Statistics
    # =========================================================================
    print("\n" + "=" * 80)
    print("KEY TAKEAWAYS")
    print("=" * 80)
    print("\n1. Edge Identification:")
    print("   - Look for 2+ points of spread edge (STRONG value)")
    print("   - Look for 5%+ probability edge in moneylines (STRONG value)")
    print("   - Use sigma to assess risk (higher sigma = more variance)")
    print()
    print("2. Expected Value (EV):")
    print("   - Only bet when EV > 0% (positive expectation)")
    print("   - 2-5% EV is good, 5%+ is excellent")
    print("   - Track EV over time, not wins/losses")
    print()
    print("3. Bankroll Management:")
    print("   - Bet 1-3% of bankroll per game")
    print("   - Higher EV = higher bet size (within limits)")
    print("   - Never chase losses")
    print()
    print("4. Line Shopping:")
    print("   - Check multiple sportsbooks for best line")
    print("   - 0.5 point difference can add 2-3% to EV")
    print("   - Track closing line value (CLV)")
    print()
    print("5. Data Freshness:")
    print("   - Check for injury updates before betting")
    print("   - Use latest KenPom snapshot (updates daily)")
    print("   - Model doesn't know about late scratches")
    print()

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. Get real market lines from sportsbooks")
    print("2. Calculate edge for all games in today's slate")
    print("3. Filter for STRONG or MODERATE opportunities")
    print("4. Place bets with proper bankroll management")
    print("5. Track results and CLV for continuous improvement")
    print()
    print("For detailed methodology, see: INTERPRETING_PREDICTIONS.md")
    print()


if __name__ == "__main__":
    main()
