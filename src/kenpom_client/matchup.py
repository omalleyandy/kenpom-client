"""Matchup feature engineering for game predictions.

This module provides matchup-specific features that compare team strengths/weaknesses,
identify style mismatches, and enhance prediction accuracy beyond simple efficiency
differentials.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import pandas as pd

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from kenpom_client.hca_scraper import HCASnapshot

# Module-level HCA snapshot cache
_hca_snapshot_cache: Optional["HCASnapshot"] = None

# Default HCA when no team-specific data is available
DEFAULT_HCA = 3.5


@dataclass(frozen=True)
class MatchupFeatures:
    """Matchup-specific features derived from team comparisons.

    This dataclass encapsulates all comparative metrics between two teams,
    including efficiency deltas, style signals, and placeholder hooks for
    future enhancements (rest, travel, etc.).

    All delta fields are calculated as: away_team - home_team
    (negative values indicate home team advantage)
    """

    # Efficiency deltas (away - home, so negative = home advantage)
    delta_adj_em: float  # Overall efficiency differential
    delta_adj_oe: float  # Offensive efficiency differential
    delta_adj_de: float  # Defensive efficiency differential (lower is better)
    delta_tempo: float  # Tempo differential

    # Shooting matchup signals
    shooting_advantage: float  # Away eFG% vs Home DeFG% mismatch
    shooting_defense_advantage: float  # Home eFG% vs Away DeFG% mismatch

    # Ball control signals
    turnover_advantage: float  # Away TO% vs Home DTO% forcing
    rebounding_advantage: float  # Away OR% vs Home DOR% prevention

    # Style classification signals
    tempo_mismatch: float  # Absolute tempo difference (matchup volatility)
    pace_control: str  # "home_controls" | "away_controls" | "neutral"

    # Shooting style signals
    home_3pt_reliance: float  # % of points from 3PT (home)
    away_3pt_reliance: float  # % of points from 3PT (away)
    style_clash: str  # "3pt_vs_interior" | "similar" | "balanced"

    # Placeholder hooks (future enhancement)
    home_court_factor: float  # Currently constant 3.5, future: team-specific
    rest_advantage: Optional[int]  # Days rest differential (future)
    travel_distance: Optional[float]  # Miles traveled (future)

    # Metadata
    feature_version: str  # "1.0" for tracking feature evolution


def _safe_get(row: pd.Series, key: str, default: float) -> float:
    """Safely get value from pandas Series, handling None and missing keys.

    Args:
        row: Pandas Series (team data)
        key: Column name to retrieve
        default: Default value if missing or None

    Returns:
        Value from series or default
    """
    value = row.get(key)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return float(value)


def calculate_matchup_features(
    away: pd.Series, home: pd.Series, game_context: Optional["GameContext"] = None
) -> MatchupFeatures:
    """Calculate matchup-specific features from team data.

    This function derives comparative metrics between two teams, including:
    - Efficiency differentials (ΔAdjEM, ΔAdjO, ΔAdjD, ΔTempo)
    - Shooting matchup advantages (offense vs defense eFG%)
    - Ball control signals (turnovers, rebounding)
    - Style classification (tempo control, 3PT reliance, style clash)
    - Rest advantage and travel distance (if game_context provided)

    Args:
        away: Team data for away team (pandas Series from enriched snapshot)
        home: Team data for home team (pandas Series from enriched snapshot)
        game_context: Optional game context with rest days and venue info

    Returns:
        MatchupFeatures dataclass with all comparative metrics

    Example:
        >>> df = load_enriched_snapshot("data/kenpom_ratings_2025_2025-12-21_enriched.csv")
        >>> oregon = find_team(df, "Oregon")
        >>> gonzaga = find_team(df, "Gonzaga")
        >>> matchup = calculate_matchup_features(oregon, gonzaga)
        >>> print(f"Tempo mismatch: {matchup.tempo_mismatch:.1f}")
    """
    # =========================================================================
    # A. Efficiency Deltas
    # =========================================================================
    delta_adj_em = _safe_get(away, "adj_em", 0.0) - _safe_get(home, "adj_em", 0.0)
    delta_adj_oe = _safe_get(away, "adj_oe", 105.0) - _safe_get(home, "adj_oe", 105.0)
    delta_adj_de = _safe_get(away, "adj_de", 100.0) - _safe_get(home, "adj_de", 100.0)
    delta_tempo = _safe_get(away, "adj_tempo", 68.0) - _safe_get(home, "adj_tempo", 68.0)

    # =========================================================================
    # B. Shooting Matchup
    # =========================================================================
    # Away offense vs Home defense
    away_efg = _safe_get(away, "efg_pct", 50.0)
    home_defg = _safe_get(home, "defg_pct", 50.0)
    shooting_advantage = away_efg - home_defg

    # Home offense vs Away defense
    home_efg = _safe_get(home, "efg_pct", 50.0)
    away_defg = _safe_get(away, "defg_pct", 50.0)
    shooting_defense_advantage = home_efg - away_defg

    # =========================================================================
    # C. Ball Control Signals
    # =========================================================================
    # Turnover battle: Can away team protect vs home pressure?
    home_dto = _safe_get(home, "dto_pct", 20.0)  # Home forces turnovers
    away_to = _safe_get(away, "to_pct", 20.0)  # Away commits turnovers
    turnover_advantage = home_dto - away_to
    # Positive = home forces more TOs than away commits

    # Rebounding battle: Can away team crash boards vs home defense?
    away_or = _safe_get(away, "or_pct", 30.0)  # Away offensive rebounds
    home_dor = _safe_get(home, "dor_pct", 30.0)  # Home allows offensive rebounds
    rebounding_advantage = away_or - home_dor
    # Positive = away team gets more offensive boards than home allows

    # =========================================================================
    # D. Tempo & Pace Control
    # =========================================================================
    tempo_mismatch = abs(delta_tempo)

    # Determine pace control (who dictates tempo)
    if tempo_mismatch > 5.0:
        if delta_tempo > 0:
            pace_control = "away_controls"  # Away plays faster
        else:
            pace_control = "home_controls"  # Home plays faster
    else:
        pace_control = "neutral"

    # =========================================================================
    # E. Style Classification
    # =========================================================================
    # 3PT reliance (from point distribution)
    home_3pt_reliance = _safe_get(home, "off_fg3", 30.0)
    away_3pt_reliance = _safe_get(away, "off_fg3", 30.0)

    # Style clash detection
    three_pt_diff = abs(home_3pt_reliance - away_3pt_reliance)
    if three_pt_diff > 10.0:
        # One team relies heavily on 3PT, other doesn't
        style_clash = "3pt_vs_interior"
    else:
        style_clash = "similar"

    # =========================================================================
    # F. Context-Dependent Features (Rest & Travel)
    # =========================================================================
    home_court_factor = calculate_home_court_factor(home)

    # Rest advantage: days rest differential (positive = home has more rest)
    if game_context is not None and game_context.rest_advantage is not None:
        rest_advantage = game_context.rest_advantage
    else:
        rest_advantage = None

    # Travel distance: miles from away team's home venue to game venue
    if game_context is not None:
        travel_distance = calculate_travel_distance(
            game_context.away_venue, game_context.home_venue
        )
    else:
        travel_distance = None

    return MatchupFeatures(
        # Efficiency deltas
        delta_adj_em=delta_adj_em,
        delta_adj_oe=delta_adj_oe,
        delta_adj_de=delta_adj_de,
        delta_tempo=delta_tempo,
        # Shooting matchup
        shooting_advantage=shooting_advantage,
        shooting_defense_advantage=shooting_defense_advantage,
        # Ball control
        turnover_advantage=turnover_advantage,
        rebounding_advantage=rebounding_advantage,
        # Style signals
        tempo_mismatch=tempo_mismatch,
        pace_control=pace_control,
        home_3pt_reliance=home_3pt_reliance,
        away_3pt_reliance=away_3pt_reliance,
        style_clash=style_clash,
        # Placeholder hooks
        home_court_factor=home_court_factor,
        rest_advantage=rest_advantage,
        travel_distance=travel_distance,
        # Metadata
        feature_version="1.0",
    )


def load_hca_snapshot() -> Optional["HCASnapshot"]:
    """Load the most recent HCA snapshot from disk.

    Caches the result to avoid repeated file reads. Logs a warning if the
    snapshot is older than 7 days to encourage fresh data fetching.

    Returns:
        HCASnapshot or None if no snapshot file exists
    """
    global _hca_snapshot_cache

    if _hca_snapshot_cache is not None:
        return _hca_snapshot_cache

    # Import here to avoid circular imports
    from kenpom_client.hca_scraper import HCASnapshot

    # Find most recent HCA snapshot
    data_dir = Path("data")
    if not data_dir.exists():
        logger.warning("No data directory found - using default HCA of %.1f", DEFAULT_HCA)
        return None

    hca_files = sorted(data_dir.glob("kenpom_hca_*.json"), reverse=True)
    if not hca_files:
        logger.warning("No HCA snapshot files found - using default HCA of %.1f", DEFAULT_HCA)
        return None

    try:
        latest_file = hca_files[0]
        _hca_snapshot_cache = HCASnapshot.from_json(latest_file.read_text())

        # Check freshness - warn if snapshot is older than 7 days
        match = re.search(r"kenpom_hca_(\d{4}-\d{2}-\d{2})\.json", latest_file.name)
        if match:
            snapshot_date = datetime.strptime(match.group(1), "%Y-%m-%d")
            age_days = (datetime.now() - snapshot_date).days
            if age_days > 7:
                logger.warning(
                    "HCA snapshot is %d days old (%s) - consider running 'uv run fetch-hca'",
                    age_days,
                    latest_file.name,
                )
            else:
                logger.info("Using HCA snapshot from %s (%d days old)", latest_file.name, age_days)

        return _hca_snapshot_cache
    except Exception as e:
        logger.warning(
            "Failed to load HCA snapshot: %s - using default HCA of %.1f", e, DEFAULT_HCA
        )
        return None


def clear_hca_cache() -> None:
    """Clear the HCA snapshot cache (useful for testing)."""
    global _hca_snapshot_cache
    _hca_snapshot_cache = None


def calculate_home_court_factor(
    home: pd.Series, hca_snapshot: Optional["HCASnapshot"] = None
) -> float:
    """Calculate team-specific home court advantage.

    Uses KenPom HCA data scraped from kenpom.com/hca.php to get team-specific
    home court advantage values. Falls back to DEFAULT_HCA (3.5) if no data
    is available.

    Args:
        home: Team data for home team (pandas Series with 'team' column)
        hca_snapshot: Optional pre-loaded HCA snapshot (loads from disk if None)

    Returns:
        Home court advantage in points (team-specific or 3.5 default)

    Example:
        >>> home_team = df[df['team'] == 'Kansas'].iloc[0]
        >>> hca = calculate_home_court_factor(home_team)
        >>> print(f"Kansas HCA: {hca:.2f}")  # Phog Allen is legendary
    """
    # Get team name from Series
    team_name = home.get("team")
    if team_name is None:
        return DEFAULT_HCA

    # Load HCA snapshot if not provided
    if hca_snapshot is None:
        hca_snapshot = load_hca_snapshot()

    if hca_snapshot is None:
        return DEFAULT_HCA

    # Look up team-specific HCA
    team_hca = hca_snapshot.get_team_hca(str(team_name))
    if team_hca is not None:
        return team_hca

    # Fall back to national average from snapshot
    return hca_snapshot.national_avg_hca


@dataclass
class GameContext:
    """Game context metadata (future enhancement).

    This dataclass is a placeholder for future enhancements that require
    game-specific context beyond team statistics, such as:
    - Rest days since last game
    - Travel distance from home venue
    - Back-to-back game flags
    - Injury reports
    """

    away_days_rest: Optional[int] = None
    home_days_rest: Optional[int] = None
    away_venue: Optional[str] = None
    home_venue: Optional[str] = None

    @property
    def rest_advantage(self) -> Optional[int]:
        """Calculate days rest differential (positive = home has more rest).

        Returns:
            Days rest difference or None if data unavailable
        """
        if self.away_days_rest is not None and self.home_days_rest is not None:
            return self.home_days_rest - self.away_days_rest
        return None


def calculate_travel_distance(
    away_venue: Optional[str], home_venue: Optional[str]
) -> Optional[float]:
    """Calculate travel distance in miles between venues.

    Uses a simple distance estimation based on venue names and states.
    For neutral site games or missing venue data, returns None.

    Future enhancement: Use geocoding API for precise coordinates and
    haversine formula for accurate great circle distance.

    Args:
        away_venue: Away team's home venue name (e.g., "Matthew Knight Arena, Eugene, OR")
        home_venue: Host venue name (e.g., "McCarthey Athletic Center, Spokane, WA")

    Returns:
        Estimated travel distance in miles or None if data unavailable
    """
    if not away_venue or not home_venue:
        return None

    # Extract state abbreviations from venue strings (common pattern: "City, ST")
    import re

    # Try to extract state codes (2-letter uppercase)
    away_state_match = re.search(r",\s*([A-Z]{2})\b", away_venue)
    home_state_match = re.search(r",\s*([A-Z]{2})\b", home_venue)

    if not away_state_match or not home_state_match:
        # If we can't extract states, return None (would need geocoding)
        return None

    away_state = away_state_match.group(1)
    home_state = home_state_match.group(1)

    # If same state, estimate short distance (0-200 miles)
    if away_state == home_state:
        # Same state: estimate 50-200 miles (conference games often closer)
        return 100.0  # Conservative estimate for same-state games

    # Different states: use rough distance estimates for common conference patterns
    # This is a simplified approach - full implementation would use geocoding
    # For now, return a placeholder that indicates travel is required
    # Typical cross-state travel: 200-2000 miles
    return 500.0  # Conservative estimate for cross-state travel
