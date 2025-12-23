"""Calculate real betting edge using actual market odds.

This script compares your model predictions to real market lines from ESPN/DraftKings
to identify actual betting opportunities with quantified edge.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pandas as pd


def normal_cdf(x: float) -> float:
    """Approximate the cumulative distribution function of standard normal."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def cover_probability(predicted_margin: float, spread: float, avg_sigma: float) -> float:
    """Calculate probability of covering a specific spread."""
    z_score = (predicted_margin - spread) / avg_sigma
    return normal_cdf(z_score)


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return 1 + (american_odds / 100)
    else:
        return 1 + (100 / abs(american_odds))


def american_to_implied_prob(american_odds: int) -> float:
    """Convert American odds to implied probability."""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)


def calculate_ev(win_prob: float, american_odds: int) -> float:
    """Calculate expected value of a bet."""
    decimal_odds = american_to_decimal(american_odds)
    return (win_prob * (decimal_odds - 1)) - (1 - win_prob)


def kelly_criterion(win_prob: float, decimal_odds: float) -> float:
    """Calculate optimal bet size using Kelly Criterion."""
    if decimal_odds <= 1:
        return 0.0
    kelly = (win_prob * decimal_odds - 1) / (decimal_odds - 1)
    return max(0.0, kelly)


def analyze_spread_edge(model_row: pd.Series, market_row: pd.Series) -> dict:
    """Analyze edge in point spread."""
    model_margin = model_row["predicted_margin"]
    market_spread = market_row["market_spread"]
    avg_sigma = model_row["avg_sigma"]

    # Market spread is from home team perspective
    # Negative = home favored, Positive = away favored
    # Need to flip sign for comparison
    market_spread_home = -market_spread

    # Calculate edge (model vs market)
    spread_edge = model_margin - market_spread_home

    # Cover probabilities
    home_cover_prob = cover_probability(model_margin, market_spread_home, avg_sigma)
    away_cover_prob = 1 - home_cover_prob

    # Market implied probability from odds
    market_odds = int(market_row["spread_odds"])
    market_implied = american_to_implied_prob(market_odds)

    # Calculate EVs
    home_ev = calculate_ev(home_cover_prob, market_odds)
    away_ev = calculate_ev(away_cover_prob, market_odds)

    # Determine best bet
    if abs(spread_edge) < 1.0:
        recommendation = "PASS"
        bet_team = None
        bet_ev = 0.0
        bet_prob = 0.5
    elif spread_edge > 0:
        # Home team undervalued by market
        recommendation = f"{model_row['home_team']} {market_spread_home:+.1f}"
        bet_team = model_row["home_team"]
        bet_ev = home_ev
        bet_prob = home_cover_prob
    else:
        # Away team undervalued by market
        recommendation = f"{model_row['away_team']} {-market_spread_home:+.1f}"
        bet_team = model_row["away_team"]
        bet_ev = away_ev
        bet_prob = away_cover_prob

    # Strength classification
    abs_edge = abs(spread_edge)
    if abs_edge >= 3.0:
        strength = "VERY STRONG"
    elif abs_edge >= 2.0:
        strength = "STRONG"
    elif abs_edge >= 1.0:
        strength = "MODERATE"
    else:
        strength = "WEAK"

    return {
        "game": f"{model_row['away_team']} @ {model_row['home_team']}",
        "model_spread": f"{model_row['home_team']} {model_margin:+.1f}",
        "market_spread": f"{model_row['home_team']} {market_spread_home:+.1f}",
        "spread_edge": spread_edge,
        "home_cover_prob": home_cover_prob,
        "away_cover_prob": away_cover_prob,
        "market_implied": market_implied,
        "recommendation": recommendation,
        "bet_team": bet_team,
        "expected_value": bet_ev,
        "bet_probability": bet_prob,
        "strength": strength,
        "avg_sigma": avg_sigma,
    }


def analyze_moneyline_edge(model_row: pd.Series, market_row: pd.Series) -> dict:
    """Analyze edge in moneyline."""
    model_home_prob = model_row["home_win_prob"]
    model_away_prob = model_row["away_win_prob"]

    # Parse market odds
    home_ml_str = str(market_row["home_ml"])
    away_ml_str = str(market_row["away_ml"])

    # Handle OFF (odds not offered)
    if home_ml_str == "OFF" or away_ml_str == "OFF":
        return {
            "game": f"{model_row['away_team']} @ {model_row['home_team']}",
            "recommendation": "MONEYLINE NOT OFFERED",
            "expected_value": 0.0,
            "strength": "N/A",
        }

    home_ml = int(home_ml_str)
    away_ml = int(away_ml_str)

    # Market implied probabilities
    market_home_prob = american_to_implied_prob(home_ml)
    market_away_prob = american_to_implied_prob(away_ml)

    # Edge (probability difference)
    home_edge = model_home_prob - market_home_prob
    away_edge = model_away_prob - market_away_prob

    # Expected values
    home_ev = calculate_ev(model_home_prob, home_ml)
    away_ev = calculate_ev(model_away_prob, away_ml)

    # Determine best bet
    if home_ev > away_ev and home_ev > 0:
        best_bet = model_row["home_team"]
        best_odds = home_ml
        best_ev = home_ev
        prob_edge = home_edge
        bet_prob = model_home_prob
    elif away_ev > 0:
        best_bet = model_row["away_team"]
        best_odds = away_ml
        best_ev = away_ev
        prob_edge = away_edge
        bet_prob = model_away_prob
    else:
        best_bet = "PASS"
        best_odds = 0
        best_ev = max(home_ev, away_ev)
        prob_edge = max(home_edge, away_edge)
        bet_prob = 0.5

    # Strength
    abs_edge = abs(prob_edge)
    if abs_edge >= 0.10:
        strength = "VERY STRONG"
    elif abs_edge >= 0.05:
        strength = "STRONG"
    elif abs_edge >= 0.03:
        strength = "MODERATE"
    else:
        strength = "WEAK"

    return {
        "game": f"{model_row['away_team']} @ {model_row['home_team']}",
        "model_probs": f"Home {model_home_prob:.1%} / Away {model_away_prob:.1%}",
        "market_probs": f"Home {market_home_prob:.1%} / Away {market_away_prob:.1%}",
        "home_edge": home_edge,
        "away_edge": away_edge,
        "best_bet": best_bet,
        "best_odds": best_odds,
        "expected_value": best_ev,
        "bet_probability": bet_prob,
        "prob_edge": prob_edge,
        "strength": strength,
    }


def main():
    """Calculate real betting edge using market odds."""
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    # Load predictions and market odds
    predictions_path = Path(f"data/todays_game_predictions_{date_str}.csv")
    market_path = Path(f"data/overtime_ncaab_odds_{date_str}.csv")

    if not predictions_path.exists():
        print(f"ERROR: Predictions file not found at {predictions_path}")
        print("Run: uv run python analyze_todays_games.py")
        return

    if not market_path.exists():
        print(f"ERROR: Market odds file not found at {market_path}")
        print("Run: uv run fetch-odds")
        return

    predictions = pd.read_csv(predictions_path)
    market = pd.read_csv(market_path)

    print("=" * 80)
    print(f"REAL BETTING EDGE ANALYSIS - {today.strftime('%B %d, %Y')}")
    print("Market Odds Source: overtime.ag")
    print("=" * 80)

    # Merge predictions with market odds
    merged = predictions.merge(market, on=["away_team", "home_team"], how="inner")

    print(f"\n{len(merged)} games with both model predictions and market odds\n")

    # =========================================================================
    # POINT SPREAD ANALYSIS
    # =========================================================================
    print("\n" + "=" * 80)
    print("POINT SPREAD EDGE ANALYSIS")
    print("=" * 80)

    spread_opportunities = []

    for _, row in merged.iterrows():
        analysis = analyze_spread_edge(row, row)
        if analysis["strength"] in ["VERY STRONG", "STRONG", "MODERATE"]:
            spread_opportunities.append(analysis)

    # Sort by absolute edge
    spread_opportunities.sort(key=lambda x: abs(x["spread_edge"]), reverse=True)

    print(f"\nFound {len(spread_opportunities)} spread opportunities\n")

    for opp in spread_opportunities:
        print(f"Game: {opp['game']}")
        print(f"  Model: {opp['model_spread']}")
        print(f"  Market: {opp['market_spread']}")
        print(f"  Edge: {opp['spread_edge']:+.1f} points [{opp['strength']}]")
        print(f"  Cover Probability: {opp['bet_probability']:.1%}")
        print(f"  Expected Value: {opp['expected_value']:+.1%}")
        print(f"  RECOMMENDATION: {opp['recommendation']}")

        # Kelly Criterion bet sizing
        if opp["recommendation"] != "PASS":
            market_odds = int(row["spread_odds"])
            decimal_odds = american_to_decimal(market_odds)
            kelly = kelly_criterion(opp["bet_probability"], decimal_odds)
            print(f"  Kelly Criterion: {kelly:.2%} of bankroll (use 1/4 Kelly = {kelly / 4:.2%})")
        print()

    # =========================================================================
    # MONEYLINE ANALYSIS
    # =========================================================================
    print("\n" + "=" * 80)
    print("MONEYLINE EDGE ANALYSIS")
    print("=" * 80)

    ml_opportunities = []

    for _, row in merged.iterrows():
        analysis = analyze_moneyline_edge(row, row)
        if analysis.get("strength") in ["VERY STRONG", "STRONG", "MODERATE"]:
            ml_opportunities.append(analysis)

    # Sort by EV
    ml_opportunities.sort(key=lambda x: x.get("expected_value", 0), reverse=True)

    print(f"\nFound {len(ml_opportunities)} moneyline opportunities\n")

    for opp in ml_opportunities[:10]:  # Top 10
        if opp.get("best_bet") == "PASS":
            continue
        print(f"Game: {opp['game']}")
        print(f"  Model: {opp['model_probs']}")
        print(f"  Market: {opp['market_probs']}")
        print(f"  Probability Edge: {opp['prob_edge']:+.1%} [{opp['strength']}]")
        print(f"  Best Bet: {opp['best_bet']} ({opp['best_odds']:+d})")
        print(f"  Win Probability: {opp['bet_probability']:.1%}")
        print(f"  Expected Value: {opp['expected_value']:+.1%}")

        # Kelly Criterion
        decimal_odds = american_to_decimal(opp["best_odds"])
        kelly = kelly_criterion(opp["bet_probability"], decimal_odds)
        print(f"  Kelly Criterion: {kelly:.2%} of bankroll (use 1/4 Kelly = {kelly / 4:.2%})")
        print()

    # =========================================================================
    # TOP OPPORTUNITIES SUMMARY
    # =========================================================================
    print("\n" + "=" * 80)
    print("TOP 10 BETTING OPPORTUNITIES (ALL MARKETS)")
    print("=" * 80)

    all_opportunities = []

    # Add spreads
    for opp in spread_opportunities:
        if opp["recommendation"] != "PASS":
            all_opportunities.append(
                {
                    "type": "SPREAD",
                    "game": opp["game"],
                    "bet": opp["recommendation"],
                    "ev": opp["expected_value"],
                    "strength": opp["strength"],
                    "prob": opp["bet_probability"],
                }
            )

    # Add moneylines
    for opp in ml_opportunities:
        if opp.get("best_bet") != "PASS" and opp.get("best_bet") != "MONEYLINE NOT OFFERED":
            all_opportunities.append(
                {
                    "type": "MONEYLINE",
                    "game": opp["game"],
                    "bet": f"{opp['best_bet']} ML ({opp['best_odds']:+d})",
                    "ev": opp["expected_value"],
                    "strength": opp["strength"],
                    "prob": opp["bet_probability"],
                }
            )

    # Sort by EV
    all_opportunities.sort(key=lambda x: x["ev"], reverse=True)

    print()
    for i, opp in enumerate(all_opportunities[:10], 1):
        print(f"{i}. {opp['bet']}")
        print(f"   Game: {opp['game']}")
        print(f"   Type: {opp['type']} | Strength: {opp['strength']}")
        print(f"   Win Probability: {opp['prob']:.1%}")
        print(f"   Expected Value: {opp['ev']:+.1%}")
        print()

    # =========================================================================
    # EXPORT RESULTS
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXPORTING RESULTS")
    print("=" * 80)

    # Create detailed results DataFrame
    results = []
    for _, row in merged.iterrows():
        spread_analysis = analyze_spread_edge(row, row)
        ml_analysis = analyze_moneyline_edge(row, row)

        results.append(
            {
                "away_team": row["away_team"],
                "home_team": row["home_team"],
                "model_margin": row["predicted_margin"],
                "market_spread": -row["market_spread"],
                "spread_edge": spread_analysis["spread_edge"],
                "spread_ev": spread_analysis["expected_value"],
                "spread_recommendation": spread_analysis["recommendation"],
                "spread_strength": spread_analysis["strength"],
                "model_home_prob": row["home_win_prob"],
                "model_away_prob": row["away_win_prob"],
                "market_home_ml": row["home_ml"],
                "market_away_ml": row["away_ml"],
                "ml_recommendation": ml_analysis.get("best_bet", "N/A"),
                "ml_ev": ml_analysis.get("expected_value", 0.0),
                "ml_strength": ml_analysis.get("strength", "N/A"),
                "avg_sigma": row["avg_sigma"],
            }
        )

    results_df = pd.DataFrame(results)
    output_path = Path(f"data/betting_edge_analysis_{date_str}.csv")
    results_df.to_csv(output_path, index=False)

    print(f"\nDetailed analysis exported to: {output_path}")
    print(f"Total opportunities: {len(all_opportunities)}")
    print(
        f"STRONG+ spreads: {len([o for o in spread_opportunities if o['strength'] in ['STRONG', 'VERY STRONG']])}"
    )
    print(
        f"STRONG+ moneylines: {len([o for o in ml_opportunities if o.get('strength') in ['STRONG', 'VERY STRONG']])}"
    )

    print("\n" + "=" * 80)
    print("BETTING GUIDELINES")
    print("=" * 80)
    print("\n1. Only bet opportunities with EV > 2%")
    print("2. Use 1/4 Kelly for bet sizing (never full Kelly)")
    print("3. Maximum 3% of bankroll per bet")
    print("4. Track Closing Line Value (CLV) for all bets")
    print("5. Check for injury updates before placing bets")
    print("\nGood luck and bet responsibly!")
    print()


if __name__ == "__main__":
    main()
