"""Calculate real betting edge using actual market odds.

This script compares your model predictions to real market lines from overtime.ag
to identify actual betting opportunities with quantified edge.

Workflow:
1. Run `uv run fetch-odds` to get today's market odds
2. Run `uv run python analyze_todays_games.py` to generate predictions
3. Run `uv run python calculate_real_edge.py` to calculate edges
"""

from __future__ import annotations

import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))
from kenpom_client.validation import (
    PipelineValidator,
    RunHistoryLogger,
    create_run_stats,
)


def normal_cdf(x: float) -> float:
    """Approximate the cumulative distribution function of standard normal."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def cover_probability(predicted_margin: float, spread: float, avg_sigma: float) -> float:
    """Calculate probability of covering a specific spread.

    Args:
        predicted_margin: Model's predicted margin (positive = home wins by X)
        spread: Market spread in betting convention (negative = home favored)
        avg_sigma: Standard deviation of game outcomes

    Returns:
        Probability that home team covers the spread

    Example:
        If predicted_margin=20.7 and spread=-18 (home favored by 18):
        Home covers if they win by MORE than 18.
        z = (20.7 + (-18)) / sigma = 2.7 / sigma
        P(cover) ≈ 60% (not 100%)
    """
    # Home covers if actual_margin > -spread
    # P(margin > -spread) = Φ((predicted_margin - (-spread)) / sigma)
    #                     = Φ((predicted_margin + spread) / sigma)
    z_score = (predicted_margin + spread) / avg_sigma
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
    """Calculate expected value of a bet.

    Args:
        win_prob: Probability of winning (0-1)
        american_odds: American odds format (+150, -110, etc.)

    Returns:
        Expected value as decimal (0.05 = 5% EV)
    """
    decimal_odds = american_to_decimal(american_odds)
    return (win_prob * (decimal_odds - 1)) - (1 - win_prob)


def kelly_criterion(win_prob: float, decimal_odds: float) -> float:
    """Calculate optimal bet size using Kelly Criterion.

    Args:
        win_prob: Probability of winning
        decimal_odds: Decimal odds (2.0 = even money)

    Returns:
        Fraction of bankroll to bet (0.0-1.0)
    """
    if decimal_odds <= 1:
        return 0.0
    kelly = (win_prob * decimal_odds - 1) / (decimal_odds - 1)
    return max(0.0, kelly)


def analyze_spread_edge(
    home_team: str,
    away_team: str,
    predicted_margin: float,
    market_spread: float,
    spread_odds: int,
    avg_sigma: float,
) -> dict:
    """Analyze edge in point spread.

    Args:
        home_team: Home team name
        away_team: Away team name
        predicted_margin: Model's predicted margin (positive = home wins)
        market_spread: Market spread (negative = home favored)
        spread_odds: Odds on the spread (usually -110)
        avg_sigma: Standard deviation of predictions

    Returns:
        Dictionary with spread edge analysis
    """
    # Calculate edge (model vs market)
    # market_spread uses betting convention: negative = home favored
    # predicted_margin: positive = home wins by X
    # If model says home wins by 20.7 and market has home -18.0 (favored by 18):
    #   edge = 20.7 + (-18.0) = 2.7 points on home
    spread_edge = predicted_margin + market_spread

    # Cover probabilities
    home_cover_prob = cover_probability(predicted_margin, market_spread, avg_sigma)
    away_cover_prob = 1 - home_cover_prob

    # Market implied probability from odds
    market_implied = american_to_implied_prob(spread_odds)

    # Calculate EVs
    home_ev = calculate_ev(home_cover_prob, spread_odds)
    away_ev = calculate_ev(away_cover_prob, spread_odds)

    # Determine best bet
    if abs(spread_edge) < 1.0:
        recommendation = "PASS"
        bet_team = None
        bet_ev = 0.0
        bet_prob = 0.5
    elif spread_edge > 0:
        # Home team undervalued by market
        recommendation = f"{home_team} {market_spread:+.1f}"
        bet_team = home_team
        bet_ev = home_ev
        bet_prob = home_cover_prob
    else:
        # Away team undervalued by market
        recommendation = f"{away_team} {-market_spread:+.1f}"
        bet_team = away_team
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
        "game": f"{away_team} @ {home_team}",
        "model_spread": f"{home_team} {predicted_margin:+.1f}",
        "market_spread_str": f"{home_team} {market_spread:+.1f}",
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
        "spread_odds": spread_odds,
    }


def analyze_moneyline_edge(
    home_team: str,
    away_team: str,
    home_win_prob: float,
    away_win_prob: float,
    home_ml: Optional[int],
    away_ml: Optional[int],
) -> dict:
    """Analyze edge in moneyline.

    Args:
        home_team: Home team name
        away_team: Away team name
        home_win_prob: Model's probability home team wins
        away_win_prob: Model's probability away team wins
        home_ml: Home team moneyline odds
        away_ml: Away team moneyline odds

    Returns:
        Dictionary with moneyline edge analysis
    """
    # Handle missing/invalid odds
    if home_ml is None or away_ml is None:
        return {
            "game": f"{away_team} @ {home_team}",
            "recommendation": "MONEYLINE NOT OFFERED",
            "expected_value": 0.0,
            "strength": "N/A",
        }

    try:
        home_ml = int(home_ml)
        away_ml = int(away_ml)
    except (ValueError, TypeError):
        return {
            "game": f"{away_team} @ {home_team}",
            "recommendation": "MONEYLINE NOT OFFERED",
            "expected_value": 0.0,
            "strength": "N/A",
        }

    # Market implied probabilities
    market_home_prob = american_to_implied_prob(home_ml)
    market_away_prob = american_to_implied_prob(away_ml)

    # Edge (probability difference)
    home_edge = home_win_prob - market_home_prob
    away_edge = away_win_prob - market_away_prob

    # Expected values
    home_ev = calculate_ev(home_win_prob, home_ml)
    away_ev = calculate_ev(away_win_prob, away_ml)

    # Determine best bet
    if home_ev > away_ev and home_ev > 0:
        best_bet = home_team
        best_odds = home_ml
        best_ev = home_ev
        prob_edge = home_edge
        bet_prob = home_win_prob
    elif away_ev > 0:
        best_bet = away_team
        best_odds = away_ml
        best_ev = away_ev
        prob_edge = away_edge
        bet_prob = away_win_prob
    else:
        best_bet = "PASS"
        best_odds = 0
        best_ev = max(home_ev, away_ev)
        prob_edge = max(home_edge, away_edge)
        bet_prob = 0.5

    # Strength classification
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
        "game": f"{away_team} @ {home_team}",
        "model_probs": f"Home {home_win_prob:.1%} / Away {away_win_prob:.1%}",
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

    # Initialize validation and logging
    validator = PipelineValidator()
    history_logger = RunHistoryLogger()
    run_stats = create_run_stats(stage="edge_analysis", run_date=today)

    # Load predictions and market odds
    predictions_path = Path(f"data/todays_game_predictions_{date_str}.csv")
    market_path = Path(f"data/overtime_ncaab_odds_{date_str}.csv")

    if not predictions_path.exists():
        print(f"ERROR: Predictions file not found at {predictions_path}")
        print("Run: uv run python analyze_todays_games.py")
        run_stats.odds_issues.append("Predictions file not found")
        history_logger.log_run(run_stats)
        return

    if not market_path.exists():
        print(f"ERROR: Market odds file not found at {market_path}")
        print("Run: uv run fetch-odds")
        run_stats.odds_issues.append("Market odds file not found")
        history_logger.log_run(run_stats)
        return

    predictions = pd.read_csv(predictions_path)
    market = pd.read_csv(market_path)

    # Validate input files
    print("=" * 60)
    print("VALIDATING INPUT FILES")
    print("=" * 60)

    odds_validation = validator.validate_odds(market)
    if not odds_validation.passed:
        print("\nMarket odds validation issues:")
        for issue in odds_validation.issues:
            print(f"  ERROR: {issue}")
    if odds_validation.warnings:
        for warning in odds_validation.warnings[:3]:
            print(f"  WARNING: {warning}")
    if odds_validation.passed:
        print("  Market odds validation passed")

    pred_validation = validator.validate_predictions(predictions)
    if not pred_validation.passed:
        print("\nPredictions validation issues:")
        for issue in pred_validation.issues:
            print(f"  ERROR: {issue}")
    if pred_validation.passed:
        print("  Predictions validation passed")
    print()

    print("=" * 80)
    print(f"REAL BETTING EDGE ANALYSIS - {today.strftime('%B %d, %Y')}")
    print("Market Odds Source: overtime.ag")
    print("=" * 80)

    # Merge predictions with market odds
    # Use suffixes to handle overlapping column names
    merged = predictions.merge(
        market,
        on=["away_team", "home_team"],
        how="inner",
        suffixes=("_pred", "_mkt"),
    )

    print(f"\n{len(merged)} games with both model predictions and market odds\n")

    if len(merged) == 0:
        print("No games matched. Check that team names match between files.")
        print(f"\nPredictions teams: {predictions[['away_team', 'home_team']].head()}")
        print(f"\nMarket teams: {market[['away_team', 'home_team']].head()}")
        return

    # Determine which columns to use for market data
    # After merge, market_spread might be _pred (from predictions) or _mkt (from market)
    # Also handles new column names (home_spread) vs old (market_spread)
    def get_col(
        df: pd.DataFrame, base_name: str, prefer_suffix: str = "_mkt", alt_name: str | None = None
    ) -> str:
        """Get the correct column name after merge."""
        # Try base name first
        if base_name in df.columns:
            return base_name
        # Try with suffix
        if f"{base_name}{prefer_suffix}" in df.columns:
            return f"{base_name}{prefer_suffix}"
        if f"{base_name}_pred" in df.columns:
            return f"{base_name}_pred"
        # Try alternate name (for column renames)
        if alt_name:
            if alt_name in df.columns:
                return alt_name
            if f"{alt_name}{prefer_suffix}" in df.columns:
                return f"{alt_name}{prefer_suffix}"
            if f"{alt_name}_pred" in df.columns:
                return f"{alt_name}_pred"
        return base_name  # Will fail, but gives useful error

    # Column mappings - use market file columns where available
    # Handle both old (market_spread) and new (home_spread) column names
    spread_col = get_col(merged, "market_spread", "_mkt", alt_name="home_spread")
    spread_odds_col = get_col(merged, "spread_odds", "_mkt", alt_name="home_spread_odds")
    home_ml_col = get_col(merged, "home_ml", "_mkt")
    away_ml_col = get_col(merged, "away_ml", "_mkt")

    # =========================================================================
    # POINT SPREAD ANALYSIS
    # =========================================================================
    print("\n" + "=" * 80)
    print("POINT SPREAD EDGE ANALYSIS")
    print("=" * 80)

    spread_opportunities = []

    for _, row in merged.iterrows():
        # Get values, handling potential NaN
        market_spread = row.get(spread_col)
        spread_odds = row.get(spread_odds_col, -110)

        if pd.isna(market_spread) or pd.isna(spread_odds):
            continue

        analysis = analyze_spread_edge(
            home_team=row["home_team"],
            away_team=row["away_team"],
            predicted_margin=row["predicted_margin"],
            market_spread=float(market_spread),
            spread_odds=int(spread_odds),
            avg_sigma=row["avg_sigma"],
        )

        if analysis["strength"] in ["VERY STRONG", "STRONG", "MODERATE"]:
            spread_opportunities.append(analysis)

    # Sort by absolute edge
    spread_opportunities.sort(key=lambda x: abs(x["spread_edge"]), reverse=True)

    print(f"\nFound {len(spread_opportunities)} spread opportunities\n")

    for opp in spread_opportunities:
        print(f"Game: {opp['game']}")
        print(f"  Model: {opp['model_spread']}")
        print(f"  Market: {opp['market_spread_str']}")
        print(f"  Edge: {opp['spread_edge']:+.1f} points [{opp['strength']}]")
        print(f"  Cover Probability: {opp['bet_probability']:.1%}")
        print(f"  Expected Value: {opp['expected_value']:+.1%}")
        print(f"  RECOMMENDATION: {opp['recommendation']}")

        # Kelly Criterion bet sizing
        if opp["recommendation"] != "PASS":
            decimal_odds = american_to_decimal(opp["spread_odds"])
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
        home_ml = row.get(home_ml_col)
        away_ml = row.get(away_ml_col)

        analysis = analyze_moneyline_edge(
            home_team=row["home_team"],
            away_team=row["away_team"],
            home_win_prob=row["home_win_prob"],
            away_win_prob=row["away_win_prob"],
            home_ml=home_ml if not pd.isna(home_ml) else None,
            away_ml=away_ml if not pd.isna(away_ml) else None,
        )

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
        if opp.get("best_bet") not in ["PASS", "MONEYLINE NOT OFFERED", None]:
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
        market_spread = row.get(spread_col)
        spread_odds = row.get(spread_odds_col, -110)
        home_ml = row.get(home_ml_col)
        away_ml = row.get(away_ml_col)

        if pd.isna(market_spread):
            continue

        spread_analysis = analyze_spread_edge(
            home_team=row["home_team"],
            away_team=row["away_team"],
            predicted_margin=row["predicted_margin"],
            market_spread=float(market_spread),
            spread_odds=int(spread_odds) if not pd.isna(spread_odds) else -110,
            avg_sigma=row["avg_sigma"],
        )

        ml_analysis = analyze_moneyline_edge(
            home_team=row["home_team"],
            away_team=row["away_team"],
            home_win_prob=row["home_win_prob"],
            away_win_prob=row["away_win_prob"],
            home_ml=home_ml if not pd.isna(home_ml) else None,
            away_ml=away_ml if not pd.isna(away_ml) else None,
        )

        results.append(
            {
                "away_team": row["away_team"],
                "home_team": row["home_team"],
                "model_margin": row["predicted_margin"],
                "market_spread": market_spread,
                "spread_edge": spread_analysis["spread_edge"],
                "spread_ev": spread_analysis["expected_value"],
                "spread_recommendation": spread_analysis["recommendation"],
                "spread_strength": spread_analysis["strength"],
                "model_home_prob": row["home_win_prob"],
                "model_away_prob": row["away_win_prob"],
                "market_home_ml": home_ml,
                "market_away_ml": away_ml,
                "ml_recommendation": ml_analysis.get("best_bet", "N/A"),
                "ml_ev": ml_analysis.get("expected_value", 0.0),
                "ml_strength": ml_analysis.get("strength", "N/A"),
                "avg_sigma": row["avg_sigma"],
            }
        )

    results_df = pd.DataFrame(results)
    output_path = Path(f"data/betting_edge_analysis_{date_str}.csv")

    # Handle locked file gracefully
    try:
        results_df.to_csv(output_path, index=False)
        print(f"\nDetailed analysis exported to: {output_path}")
    except PermissionError:
        timestamp = datetime.now().strftime("%H%M%S")
        backup_path = Path(f"data/betting_edge_analysis_{date_str}_{timestamp}.csv")
        results_df.to_csv(backup_path, index=False)
        print(f"\nWARNING: Could not write to {output_path} (file locked)")
        print(f"Detailed analysis exported to backup: {backup_path}")

    # Update run stats
    run_stats.games_scraped = len(merged)
    run_stats.spread_opportunities = len(spread_opportunities)
    run_stats.ml_opportunities = len(ml_opportunities)
    run_stats.strong_opportunities = len(
        [o for o in spread_opportunities if o["strength"] in ["STRONG", "VERY STRONG"]]
    ) + len([o for o in ml_opportunities if o.get("strength") in ["STRONG", "VERY STRONG"]])

    print(f"Total opportunities: {len(all_opportunities)}")
    print(
        f"STRONG+ spreads: {len([o for o in spread_opportunities if o['strength'] in ['STRONG', 'VERY STRONG']])}"
    )
    print(
        f"STRONG+ moneylines: {len([o for o in ml_opportunities if o.get('strength') in ['STRONG', 'VERY STRONG']])}"
    )

    # Validate edge analysis output
    print("\n" + "=" * 60)
    print("EDGE ANALYSIS VALIDATION")
    print("=" * 60)
    edge_validation = validator.validate_edge_analysis(results_df)
    if not edge_validation.passed:
        print("  VALIDATION FAILED:")
        for issue in edge_validation.issues:
            print(f"    ERROR: {issue}")
    if edge_validation.warnings:
        for warning in edge_validation.warnings:
            print(f"    WARNING: {warning}")
    if edge_validation.passed and not edge_validation.warnings:
        print("  All edge analysis validation checks passed")

    # Log run statistics
    history_logger.log_run(run_stats)
    print("\n" + "=" * 60)
    print("RUN STATISTICS LOGGED")
    print("=" * 60)
    print(f"  Date: {run_stats.run_date}")
    print(f"  Games analyzed: {run_stats.games_scraped}")
    print(f"  Spread opportunities: {run_stats.spread_opportunities}")
    print(f"  ML opportunities: {run_stats.ml_opportunities}")
    print(f"  Strong+ opportunities: {run_stats.strong_opportunities}")
    print(f"\n  History saved to: {history_logger.history_file}")

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
