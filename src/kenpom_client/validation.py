"""Pipeline validation module for data correctness and accuracy.

Provides validation checks at each pipeline stage:
- Odds data sanity checks (spread bounds, vig calculation)
- Schema validation for output files
- Team matching success rate tracking
- Run statistics logging

Usage:
    from kenpom_client.validation import PipelineValidator, RunStats

    validator = PipelineValidator()
    result = validator.validate_odds(odds_df)
    if not result.passed:
        for issue in result.issues:
            print(f"WARNING: {issue}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        lines = [f"Validation {status}"]
        if self.issues:
            lines.append(f"  Issues ({len(self.issues)}):")
            for issue in self.issues:
                lines.append(f"    - {issue}")
        if self.warnings:
            lines.append(f"  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"    - {warning}")
        return "\n".join(lines)


@dataclass
class RunStats:
    """Statistics for a pipeline run."""

    run_date: str
    run_timestamp: str
    stage: str

    # Odds stats
    games_scraped: int = 0
    games_with_spread: int = 0
    games_with_moneyline: int = 0
    games_with_total: int = 0

    # Validation stats
    odds_validation_passed: bool = True
    odds_issues: list[str] = field(default_factory=list)
    odds_warnings: list[str] = field(default_factory=list)

    # Team matching stats
    teams_matched: int = 0
    teams_unmatched: int = 0
    match_rate: float = 0.0

    # Prediction stats
    predictions_generated: int = 0
    predictions_with_edge: int = 0
    avg_edge_magnitude: float = 0.0

    # Edge stats
    spread_opportunities: int = 0
    ml_opportunities: int = 0
    strong_opportunities: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_date": self.run_date,
            "run_timestamp": self.run_timestamp,
            "stage": self.stage,
            "games_scraped": self.games_scraped,
            "games_with_spread": self.games_with_spread,
            "games_with_moneyline": self.games_with_moneyline,
            "games_with_total": self.games_with_total,
            "odds_validation_passed": self.odds_validation_passed,
            "odds_issues": self.odds_issues,
            "odds_warnings": self.odds_warnings,
            "teams_matched": self.teams_matched,
            "teams_unmatched": self.teams_unmatched,
            "match_rate": self.match_rate,
            "predictions_generated": self.predictions_generated,
            "predictions_with_edge": self.predictions_with_edge,
            "avg_edge_magnitude": self.avg_edge_magnitude,
            "spread_opportunities": self.spread_opportunities,
            "ml_opportunities": self.ml_opportunities,
            "strong_opportunities": self.strong_opportunities,
        }


class PipelineValidator:
    """Validates data quality at each pipeline stage."""

    # Spread bounds - typical college basketball spreads are -35 to +35
    SPREAD_MIN = -40.0
    SPREAD_MAX = 40.0

    # Vig bounds - typical vig is 2-5%, anything outside 1-10% is suspicious
    VIG_MIN = 0.01
    VIG_MAX = 0.12

    # Team matching threshold - fail if less than 80% of teams match
    TEAM_MATCH_THRESHOLD = 0.80

    # Edge bounds - edges > 10 points are likely data errors
    EDGE_WARNING_THRESHOLD = 7.0
    EDGE_ERROR_THRESHOLD = 12.0

    # Required columns for each output type
    ODDS_REQUIRED_COLS = ["away_team", "home_team", "market_spread"]
    ODDS_OPTIONAL_COLS = ["spread_odds", "home_ml", "away_ml", "total", "game_time"]

    PREDICTIONS_REQUIRED_COLS = [
        "away_team",
        "home_team",
        "predicted_margin",
        "avg_sigma",
        "home_win_prob",
        "away_win_prob",
    ]

    EDGE_ANALYSIS_REQUIRED_COLS = [
        "away_team",
        "home_team",
        "model_margin",
        "market_spread",
        "spread_edge",
        "spread_recommendation",
    ]

    def calculate_vig(self, home_ml: float, away_ml: float) -> Optional[float]:
        """Calculate the vig (juice) from moneyline odds.

        Args:
            home_ml: Home team moneyline (American odds)
            away_ml: Away team moneyline (American odds)

        Returns:
            Vig as decimal (0.045 = 4.5%), or None if calculation fails
        """
        try:
            # Convert to implied probabilities
            if home_ml > 0:
                home_prob = 100 / (home_ml + 100)
            else:
                home_prob = abs(home_ml) / (abs(home_ml) + 100)

            if away_ml > 0:
                away_prob = 100 / (away_ml + 100)
            else:
                away_prob = abs(away_ml) / (abs(away_ml) + 100)

            # Vig = total implied probability - 1
            vig = home_prob + away_prob - 1.0
            return vig
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    def validate_odds(self, df: pd.DataFrame) -> ValidationResult:
        """Validate odds data quality.

        Checks:
        - Required columns present
        - Spread values within bounds
        - Vig calculation within expected range
        - No duplicate games

        Args:
            df: DataFrame with odds data

        Returns:
            ValidationResult with pass/fail status and issues
        """
        issues = []
        warnings = []
        stats = {
            "total_games": len(df),
            "games_with_spread": 0,
            "games_with_ml": 0,
            "spreads_out_of_bounds": 0,
            "unusual_vig_games": 0,
            "duplicate_games": 0,
        }

        if df.empty:
            issues.append("Odds DataFrame is empty")
            return ValidationResult(passed=False, issues=issues, stats=stats)

        # Check required columns
        missing_cols = [col for col in self.ODDS_REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            issues.append(f"Missing required columns: {missing_cols}")
            return ValidationResult(passed=False, issues=issues, stats=stats)

        # Count games with spread
        if "market_spread" in df.columns:
            valid_spreads = df["market_spread"].notna()
            stats["games_with_spread"] = int(valid_spreads.sum())

        # Count games with moneyline
        if "home_ml" in df.columns and "away_ml" in df.columns:
            valid_ml = df["home_ml"].notna() & df["away_ml"].notna()
            stats["games_with_ml"] = int(valid_ml.sum())

        # Check spread bounds
        if "market_spread" in df.columns:
            out_of_bounds = df[
                (df["market_spread"].notna())
                & (
                    (df["market_spread"] < self.SPREAD_MIN)
                    | (df["market_spread"] > self.SPREAD_MAX)
                )
            ]
            stats["spreads_out_of_bounds"] = len(out_of_bounds)
            if len(out_of_bounds) > 0:
                for _, row in out_of_bounds.iterrows():
                    issues.append(
                        f"Spread out of bounds ({row['market_spread']:.1f}): "
                        f"{row['away_team']} @ {row['home_team']}"
                    )

        # Check vig on moneylines
        if "home_ml" in df.columns and "away_ml" in df.columns:
            for _, row in df.iterrows():
                if pd.notna(row.get("home_ml")) and pd.notna(row.get("away_ml")):
                    vig = self.calculate_vig(row["home_ml"], row["away_ml"])
                    if vig is not None:
                        if vig < self.VIG_MIN:
                            stats["unusual_vig_games"] += 1
                            warnings.append(
                                f"Low vig ({vig:.1%}): {row['away_team']} @ {row['home_team']} "
                                f"(ML: {row['home_ml']:+.0f}/{row['away_ml']:+.0f})"
                            )
                        elif vig > self.VIG_MAX:
                            stats["unusual_vig_games"] += 1
                            warnings.append(
                                f"High vig ({vig:.1%}): {row['away_team']} @ {row['home_team']} "
                                f"(ML: {row['home_ml']:+.0f}/{row['away_ml']:+.0f})"
                            )

        # Check for duplicate games
        if "away_team" in df.columns and "home_team" in df.columns:
            duplicates = df.duplicated(subset=["away_team", "home_team"], keep=False)
            stats["duplicate_games"] = int(duplicates.sum() // 2)  # Each duplicate counted twice
            if stats["duplicate_games"] > 0:
                dup_games = df[duplicates][["away_team", "home_team"]].drop_duplicates()
                for _, row in dup_games.iterrows():
                    issues.append(f"Duplicate game: {row['away_team']} @ {row['home_team']}")

        passed = len(issues) == 0
        return ValidationResult(passed=passed, issues=issues, warnings=warnings, stats=stats)

    def validate_predictions(self, df: pd.DataFrame) -> ValidationResult:
        """Validate predictions output quality.

        Checks:
        - Required columns present
        - No null values in required fields
        - Edge values within reasonable bounds
        - Win probabilities sum to ~1.0

        Args:
            df: DataFrame with predictions

        Returns:
            ValidationResult with pass/fail status and issues
        """
        issues = []
        warnings = []
        stats = {
            "total_predictions": len(df),
            "predictions_with_edge": 0,
            "extreme_edges": 0,
            "null_required_fields": 0,
        }

        if df.empty:
            issues.append("Predictions DataFrame is empty")
            return ValidationResult(passed=False, issues=issues, stats=stats)

        # Check required columns
        missing_cols = [col for col in self.PREDICTIONS_REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            issues.append(f"Missing required columns: {missing_cols}")
            return ValidationResult(passed=False, issues=issues, stats=stats)

        # Check for null values in required fields
        for col in self.PREDICTIONS_REQUIRED_COLS:
            if col in df.columns:
                null_count = df[col].isna().sum()
                if null_count > 0:
                    stats["null_required_fields"] += null_count
                    warnings.append(f"Null values in {col}: {null_count}")

        # Check edge bounds (if edge columns exist)
        edge_cols = ["edge_points", "kenpom_edge_points", "spread_edge"]
        for col in edge_cols:
            if col in df.columns:
                valid_edges = df[col].notna()
                stats["predictions_with_edge"] = int(valid_edges.sum())

                # Warning threshold
                high_edges = df[(df[col].notna()) & (df[col].abs() > self.EDGE_WARNING_THRESHOLD)]
                if len(high_edges) > 0:
                    for _, row in high_edges.iterrows():
                        edge_val = row[col]
                        if abs(edge_val) > self.EDGE_ERROR_THRESHOLD:
                            stats["extreme_edges"] += 1
                            issues.append(
                                f"Extreme edge ({edge_val:+.1f} pts): "
                                f"{row['away_team']} @ {row['home_team']} - possible data error"
                            )
                        else:
                            warnings.append(
                                f"Large edge ({edge_val:+.1f} pts): "
                                f"{row['away_team']} @ {row['home_team']}"
                            )
                break  # Only check first available edge column

        # Check win probabilities
        if "home_win_prob" in df.columns and "away_win_prob" in df.columns:
            prob_sum = df["home_win_prob"] + df["away_win_prob"]
            bad_probs = df[(prob_sum < 0.99) | (prob_sum > 1.01)]
            if len(bad_probs) > 0:
                for _, row in bad_probs.iterrows():
                    warnings.append(
                        f"Win probs don't sum to 1.0: {row['away_team']} @ {row['home_team']} "
                        f"(sum={row['home_win_prob'] + row['away_win_prob']:.3f})"
                    )

        passed = len(issues) == 0
        return ValidationResult(passed=passed, issues=issues, warnings=warnings, stats=stats)

    def validate_edge_analysis(self, df: pd.DataFrame) -> ValidationResult:
        """Validate edge analysis output quality.

        Args:
            df: DataFrame with edge analysis

        Returns:
            ValidationResult with pass/fail status and issues
        """
        issues = []
        warnings = []
        stats = {
            "total_games": len(df),
            "spread_opportunities": 0,
            "ml_opportunities": 0,
            "strong_opportunities": 0,
        }

        if df.empty:
            issues.append("Edge analysis DataFrame is empty")
            return ValidationResult(passed=False, issues=issues, stats=stats)

        # Check required columns
        missing_cols = [col for col in self.EDGE_ANALYSIS_REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            issues.append(f"Missing required columns: {missing_cols}")
            return ValidationResult(passed=False, issues=issues, stats=stats)

        # Count opportunities
        if "spread_recommendation" in df.columns:
            opportunities = df[df["spread_recommendation"] != "PASS"]
            stats["spread_opportunities"] = len(opportunities)

        if "ml_recommendation" in df.columns:
            ml_opps = df[
                (df["ml_recommendation"] != "PASS")
                & (df["ml_recommendation"] != "N/A")
                & (df["ml_recommendation"] != "MONEYLINE NOT OFFERED")
            ]
            stats["ml_opportunities"] = len(ml_opps)

        if "spread_strength" in df.columns:
            strong = df[df["spread_strength"].isin(["STRONG", "VERY STRONG"])]
            stats["strong_opportunities"] = len(strong)

        passed = len(issues) == 0
        return ValidationResult(passed=passed, issues=issues, warnings=warnings, stats=stats)

    def validate_team_matching(
        self,
        total_games: int,
        matched_games: int,
        unmatched_teams: list[str],
    ) -> ValidationResult:
        """Validate team matching success rate.

        Args:
            total_games: Total number of games from odds
            matched_games: Number of games successfully matched
            unmatched_teams: List of team names that couldn't be matched

        Returns:
            ValidationResult with pass/fail status and issues
        """
        issues = []
        warnings = []

        if total_games == 0:
            issues.append("No games to match")
            return ValidationResult(
                passed=False,
                issues=issues,
                stats={"match_rate": 0.0, "total_games": 0, "matched": 0, "unmatched": 0},
            )

        match_rate = matched_games / total_games

        stats = {
            "match_rate": match_rate,
            "total_games": total_games,
            "matched": matched_games,
            "unmatched": total_games - matched_games,
            "unmatched_teams": unmatched_teams,
        }

        if match_rate < self.TEAM_MATCH_THRESHOLD:
            issues.append(
                f"Team matching rate ({match_rate:.1%}) below threshold "
                f"({self.TEAM_MATCH_THRESHOLD:.0%})"
            )
            for team in unmatched_teams[:10]:  # Show first 10
                issues.append(f"  Unmatched: {team}")
            if len(unmatched_teams) > 10:
                issues.append(f"  ... and {len(unmatched_teams) - 10} more")
        elif unmatched_teams:
            for team in unmatched_teams:
                warnings.append(f"Unmatched team: {team}")

        passed = match_rate >= self.TEAM_MATCH_THRESHOLD
        return ValidationResult(passed=passed, issues=issues, warnings=warnings, stats=stats)


class RunHistoryLogger:
    """Logs pipeline run statistics to a history file."""

    def __init__(self, history_dir: Path = Path("data")):
        self.history_dir = history_dir
        self.history_file = history_dir / "pipeline_run_history.jsonl"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def log_run(self, stats: RunStats) -> None:
        """Append run statistics to history file.

        Args:
            stats: RunStats object with run details
        """
        with open(self.history_file, "a") as f:
            f.write(json.dumps(stats.to_dict()) + "\n")

    def get_recent_runs(self, n: int = 10) -> list[dict]:
        """Get the most recent N runs from history.

        Args:
            n: Number of recent runs to retrieve

        Returns:
            List of run statistics dictionaries
        """
        if not self.history_file.exists():
            return []

        runs = []
        with open(self.history_file) as f:
            for line in f:
                if line.strip():
                    try:
                        runs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return runs[-n:]

    def get_runs_for_date(self, target_date: date) -> list[dict]:
        """Get all runs for a specific date.

        Args:
            target_date: Date to filter by

        Returns:
            List of run statistics dictionaries
        """
        date_str = target_date.strftime("%Y-%m-%d")
        runs = []

        if not self.history_file.exists():
            return []

        with open(self.history_file) as f:
            for line in f:
                if line.strip():
                    try:
                        run = json.loads(line)
                        if run.get("run_date") == date_str:
                            runs.append(run)
                    except json.JSONDecodeError:
                        continue

        return runs

    def print_summary(self, n: int = 5) -> None:
        """Print a summary of recent runs.

        Args:
            n: Number of recent runs to summarize
        """
        runs = self.get_recent_runs(n)

        if not runs:
            print("No run history found")
            return

        print("\n" + "=" * 60)
        print("RECENT PIPELINE RUNS")
        print("=" * 60)

        for run in reversed(runs):
            print(f"\n{run['run_date']} {run['run_timestamp']} - {run['stage']}")
            print(f"  Games: {run.get('games_scraped', 'N/A')}")
            print(f"  Match rate: {run.get('match_rate', 0) * 100:.1f}%")
            print(f"  Predictions: {run.get('predictions_generated', 'N/A')}")
            print(f"  Opportunities: {run.get('strong_opportunities', 'N/A')} strong")

            if run.get("odds_issues"):
                print(f"  Issues: {len(run['odds_issues'])}")


def create_run_stats(
    stage: str,
    run_date: Optional[date] = None,
) -> RunStats:
    """Create a new RunStats object for the current run.

    Args:
        stage: Pipeline stage name (e.g., "odds", "predictions", "edge_analysis")
        run_date: Date of the run (defaults to today)

    Returns:
        Initialized RunStats object
    """
    if run_date is None:
        run_date = date.today()

    return RunStats(
        run_date=run_date.strftime("%Y-%m-%d"),
        run_timestamp=datetime.now().strftime("%H:%M:%S"),
        stage=stage,
    )
