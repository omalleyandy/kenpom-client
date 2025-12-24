"""Slate table builder for fanmatch game predictions.

Builds projection tables for a given date with optional archive features
for backtesting and odds joining for edge calculation.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .client import KenPomClient
from .config import Settings

log = logging.getLogger(__name__)

# Default model parameters
DEFAULT_K = 11.0
DEFAULT_HOME_ADV = 3.0


# =============================================================================
# Team Name Normalization (Overtime → KenPom)
# =============================================================================

OVERTIME_TO_KENPOM: Dict[str, str] = {
    # Common variations
    "UConn": "Connecticut",
    "UCONN": "Connecticut",
    "UNC": "North Carolina",
    "USC": "Southern California",
    "UCF": "Central Florida",
    "UNLV": "Nevada Las Vegas",
    "SMU": "Southern Methodist",
    "TCU": "Texas Christian",
    "VCU": "Virginia Commonwealth",
    "BYU": "Brigham Young",
    "LSU": "Louisiana St.",
    "Ole Miss": "Mississippi",
    "Pitt": "Pittsburgh",
    "Miami FL": "Miami FL",
    "Miami (FL)": "Miami FL",
    "Miami (OH)": "Miami OH",
    "NC State": "N.C. State",
    "Penn St": "Penn St.",
    "Ohio St": "Ohio St.",
    "Michigan St": "Michigan St.",
    "Florida St": "Florida St.",
    "Kansas St": "Kansas St.",
    "Iowa St": "Iowa St.",
    "Oklahoma St": "Oklahoma St.",
    "Oregon St": "Oregon St.",
    "Washington St": "Washington St.",
    "Colorado St": "Colorado St.",
    "San Diego St": "San Diego St.",
    "Boise St": "Boise St.",
    "Utah St": "Utah St.",
    "Fresno St": "Fresno St.",
    "Arizona St": "Arizona St.",
    "App State": "Appalachian St.",
    "Appalachian State": "Appalachian St.",
    "St. Johns": "St. John's",
    # Apostrophe variants
    "St. Johns": "St. John's",
    # State -> St. abbreviations
    "Morgan State": "Morgan St.",
}


def normalize_team_name(name: str) -> str:
    if name in OVERTIME_TO_KENPOM:
        return OVERTIME_TO_KENPOM[name]
    # Suffix normalization
    if name.endswith(" State") and not name.endswith(" St."):
        candidate = name.replace(" State", " St.")
        if candidate != name:
            return candidate
    return name


# =============================================================================
# Retry/Backoff Hooks (placeholder for custom retry logic)
# =============================================================================


def on_retry(attempt: int, exception: Exception, delay: float) -> None:
    """Hook called before each retry attempt.

    Override this function to customize retry behavior (e.g., logging, metrics).

    Args:
        attempt: Current attempt number (1-indexed)
        exception: The exception that triggered the retry
        delay: Seconds before next attempt
    """
    log.warning(f"Retry {attempt} after {delay:.1f}s due to: {exception}")


def on_request_complete(endpoint: str, duration_ms: float, cached: bool) -> None:
    """Hook called after each API request completes.

    Override this function to add metrics/tracing.

    Args:
        endpoint: API endpoint called
        duration_ms: Request duration in milliseconds
        cached: Whether the response was served from cache
    """
    log.debug(f"{endpoint} completed in {duration_ms:.0f}ms (cached={cached})")


# =============================================================================
# Core Functions
# =============================================================================


def _row(resp: Any) -> Dict[str, Any]:
    """Extract first row from API response."""
    if isinstance(resp, list) and resp:
        r = resp[0]
        return r.model_dump() if hasattr(r, "model_dump") else r
    if hasattr(resp, "model_dump"):
        return resp.model_dump()
    if isinstance(resp, dict):
        return resp
    return {}


def _sigmoid(x: float) -> float:
    """Sigmoid function for win probability."""
    return 1.0 / (1.0 + math.exp(-x))


def _f(obj: Dict[str, Any], *keys: str) -> float:
    """Get float from dict using first key that exists."""
    for k in keys:
        if k in obj and obj[k] is not None:
            try:
                return float(obj[k])
            except (TypeError, ValueError):
                continue
    raise KeyError(f"None of keys present/convertible: {keys}")


def fanmatch_slate_table(
    *,
    d: str,
    k: float = DEFAULT_K,
    home_adv: float = DEFAULT_HOME_ADV,
    use_fanmatch_scores: bool = False,
    include_raw_fanmatch: bool = True,
    use_archive: bool = False,
    archive_fallback_to_ratings: bool = True,
    client: Optional[KenPomClient] = None,
) -> pd.DataFrame:
    """Build a full slate table for a given Fanmatch date.

    Outputs (per game):
      - projected score (home, visitor)
      - projected total
      - projected margin (home - visitor)
      - win probability (home, visitor)

    Feature source:
      - If use_archive=True: pulls time-correct features from archive endpoint
      - Else: pulls current-season features from ratings endpoint

    Args:
        d: Date in YYYY-MM-DD format
        k: Win-prob calibration scale (~10-12 typical)
        home_adv: Points added to home margin (~2.5-3.5 typical)
        use_fanmatch_scores: Use Fanmatch HomePred/VisitorPred instead of model
        include_raw_fanmatch: Include raw Fanmatch fields for traceability
        use_archive: Use archive features for date d (time-correct for backtesting)
        archive_fallback_to_ratings: Fall back to ratings if archive fails
        client: Optional KenPomClient instance (creates new one if None)

    Returns:
        DataFrame with game projections, sorted by absolute margin
    """
    c = client or KenPomClient(Settings.from_env())
    close_client = client is None

    try:
        # 1) Pull slate
        slate_raw = c.fanmatch(d=d)
        slate = [g.model_dump() if hasattr(g, "model_dump") else g for g in slate_raw]

        if not slate:
            return pd.DataFrame()

        # 2) Determine season from slate
        season = int(slate[0].get("Season"))

        # 3) Build TeamName -> TeamID map
        teams_raw = c.teams(y=season)
        if not teams_raw:
            raise RuntimeError("Teams endpoint returned no data")

        name_to_id: Dict[str, int] = {}
        for t in teams_raw:
            tm = t.model_dump() if hasattr(t, "model_dump") else t
            nm = tm.get("TeamName")
            tid = tm.get("TeamID")
            if isinstance(nm, str) and isinstance(tid, int):
                name_to_id[nm.strip().lower()] = tid

        def lookup_team_id(team_name: str) -> Optional[int]:
            return name_to_id.get(team_name.strip().lower())

        # 4) Caches keyed by (season, team_id) for ratings and (d, team_id) for archive
        ratings_cache: Dict[Tuple[int, int], Dict[str, Any]] = {}
        archive_cache: Dict[Tuple[str, int], Dict[str, Any]] = {}

        def get_ratings(team_id: int) -> Dict[str, Any]:
            key = (season, team_id)
            if key in ratings_cache:
                return ratings_cache[key]
            r = _row(c.ratings(y=season, team_id=team_id))
            if not r:
                raise RuntimeError(f"Ratings empty for team_id={team_id}, season={season}")
            ratings_cache[key] = r
            return r

        def get_archive(team_id: int) -> Dict[str, Any]:
            key = (d, team_id)
            if key in archive_cache:
                return archive_cache[key]
            a = _row(c.archive(d=d, team_id=team_id))
            if not a:
                raise RuntimeError(f"Archive empty for team_id={team_id}, d={d}")
            archive_cache[key] = a
            return a

        def get_features(team_id: int) -> Tuple[Dict[str, Any], str, Optional[str]]:
            """Returns (feature_row, source_label, warning)."""
            if not use_archive:
                return get_ratings(team_id), "ratings", None

            try:
                a = get_archive(team_id)
                # Validate required keys exist
                _ = _f(a, "AdjOE")
                _ = _f(a, "AdjDE")
                _ = _f(a, "AdjTempo", "Tempo")
                return a, "archive", None
            except Exception as e:
                if archive_fallback_to_ratings:
                    r = get_ratings(team_id)
                    warn = f"archive_failed_fallback_to_ratings: {type(e).__name__}"
                    return r, "ratings_fallback", warn
                raise

        # 5) Build output rows
        rows: List[Dict[str, Any]] = []

        for g in slate:
            home_name = g.get("Home")
            vis_name = g.get("Visitor")
            if not isinstance(home_name, str) or not isinstance(vis_name, str):
                continue

            home_id = lookup_team_id(home_name)
            vis_id = lookup_team_id(vis_name)

            if home_id is None or vis_id is None:
                row: Dict[str, Any] = {
                    "date": g.get("DateOfGame", d),
                    "season": season,
                    "home": home_name,
                    "visitor": vis_name,
                    "error": "TeamID mapping failed",
                }
                if include_raw_fanmatch:
                    for kk in ["GameID", "HomeRank", "VisitorRank", "PredTempo",
                               "ThrillScore", "HomePred", "VisitorPred", "HomeWP"]:
                        if kk in g:
                            row[f"fanmatch_{kk}"] = g[kk]
                rows.append(row)
                continue

            fh, src_h, warn_h = get_features(home_id)
            fv, src_v, warn_v = get_features(vis_id)

            # Expected possessions (per 40 min)
            poss = (_f(fh, "AdjTempo", "Tempo") + _f(fv, "AdjTempo", "Tempo")) / 2.0

            # Expected efficiency (points per 100 poss)
            E_home = (_f(fh, "AdjOE") + _f(fv, "AdjDE")) / 2.0
            E_vis = (_f(fv, "AdjOE") + _f(fh, "AdjDE")) / 2.0

            # Base projected scores
            score_home = poss * (E_home / 100.0)
            score_vis = poss * (E_vis / 100.0)

            # Optionally use Fanmatch scores
            if use_fanmatch_scores:
                try:
                    score_home = float(g["HomePred"])
                    score_vis = float(g["VisitorPred"])
                except (KeyError, TypeError, ValueError):
                    pass

            # Apply home advantage
            score_home += home_adv / 2.0
            score_vis -= home_adv / 2.0

            margin = score_home - score_vis
            total = score_home + score_vis

            p_home = _sigmoid(margin / k)
            p_vis = 1.0 - p_home

            row = {
                "date": g.get("DateOfGame", d),
                "season": season,
                "home": home_name,
                "visitor": vis_name,
                "proj_home": round(score_home, 1),
                "proj_visitor": round(score_vis, 1),
                "proj_total": round(total, 1),
                "proj_margin": round(margin, 1),
                "win_prob_home": round(p_home, 4),
                "win_prob_visitor": round(p_vis, 4),
                "possessions": round(poss, 2),
                "eff_home_pp100": round(E_home, 2),
                "eff_visitor_pp100": round(E_vis, 2),
                "feature_source_home": src_h,
                "feature_source_visitor": src_v,
                "method": ("fanmatch_scores" if use_fanmatch_scores
                           else ("archive_to_points" if use_archive else "ratings_to_points")),
            }

            # Attach warnings
            warnings: List[str] = []
            if warn_h:
                warnings.append(f"home_{warn_h}")
            if warn_v:
                warnings.append(f"visitor_{warn_v}")
            if warnings:
                row["warnings"] = ";".join(warnings)

            if include_raw_fanmatch:
                for kk in ["GameID", "HomeRank", "VisitorRank", "PredTempo",
                           "ThrillScore", "HomePred", "VisitorPred", "HomeWP"]:
                    if kk in g:
                        row[f"fanmatch_{kk}"] = g[kk]

            rows.append(row)

        df = pd.DataFrame(rows)
        if "proj_margin" in df.columns and len(df) > 0:
            df = df.sort_values(by="proj_margin", key=lambda s: s.abs(), ascending=False)
        return df

    finally:
        if close_client:
            c.close()


def join_with_odds(
    slate_df: pd.DataFrame,
    odds_path: Optional[Path] = None,
    odds_date: Optional[str] = None,
) -> pd.DataFrame:
    """Join slate projections with market odds.

    Args:
        slate_df: DataFrame from fanmatch_slate_table
        odds_path: Path to odds CSV (e.g., data/overtime_ncaab_odds_YYYY-MM-DD.csv)
        odds_date: Date for auto-locating odds file (uses first date in slate if None)

    Returns:
        DataFrame with model projections and market odds merged
    """
    if slate_df.empty:
        return slate_df

    # Determine odds file path
    if odds_path is None:
        settings = Settings.from_env()
        if odds_date is None:
            odds_date = slate_df["date"].iloc[0] if "date" in slate_df.columns else None
        if odds_date is None:
            log.warning("No odds_date specified and slate has no date column")
            return slate_df
        odds_path = Path(settings.out_dir) / f"overtime_ncaab_odds_{odds_date}.csv"

    if not odds_path.exists():
        log.warning(f"Odds file not found: {odds_path}")
        slate_df["odds_joined"] = False
        return slate_df

    # Load odds
    odds_df = pd.read_csv(odds_path)

    # Normalize team names for matching
    odds_df["home_norm"] = odds_df["home_team"].apply(normalize_team_name).str.strip().str.lower()
    odds_df["away_norm"] = odds_df["away_team"].apply(normalize_team_name).str.strip().str.lower()

    slate_df = slate_df.copy()
    slate_df["home_norm"] = slate_df["home"].str.strip().str.lower()
    slate_df["visitor_norm"] = slate_df["visitor"].str.strip().str.lower()

    # Merge on normalized names
    merged = slate_df.merge(
        odds_df[["home_norm", "away_norm", "home_spread", "home_spread_odds",
                 "home_ml", "away_ml", "total", "over_odds", "under_odds", "game_time"]],
        left_on=["home_norm", "visitor_norm"],
        right_on=["home_norm", "away_norm"],
        how="left",
        suffixes=("", "_odds"),
    )

    # Rename odds columns for clarity
    merged = merged.rename(columns={
        "home_spread": "odds_spread",
        "home_spread_odds": "odds_spread_odds",
        "total": "odds_total",
        "home_ml": "odds_home_ml",
        "away_ml": "odds_away_ml",
    })

    # Mark which rows got odds
    merged["odds_joined"] = merged["odds_spread"].notna()

    # Calculate edge (model margin - market spread)
    # Note: market_spread is from home perspective, negative = home favored
    if "odds_spread" in merged.columns:
        # Edge = our projected margin minus what market says
        # If we project home +5 and market says home -3, edge = 5 - (-3) = 8 (bet home)
        merged["spread_edge"] = merged["proj_margin"] - merged["odds_spread"].fillna(0)

    # Clean up temp columns
    merged = merged.drop(columns=["home_norm", "visitor_norm", "away_norm"], errors="ignore")

    return merged


def validate_backtest(slate_df: pd.DataFrame, as_of_date: str) -> List[str]:
    """Validate that slate uses only time-correct (non-lookahead) features.

    Args:
        slate_df: DataFrame from fanmatch_slate_table
        as_of_date: The date we're simulating predictions for

    Returns:
        List of validation warnings (empty = valid for backtesting)
    """
    warnings = []

    if slate_df.empty:
        return warnings

    # Check feature sources
    for col in ["feature_source_home", "feature_source_visitor"]:
        if col in slate_df.columns:
            non_archive = slate_df[slate_df[col] != "archive"]
            if len(non_archive) > 0:
                count = len(non_archive)
                warnings.append(
                    f"LOOKAHEAD: {count} games used '{col}' != 'archive' "
                    f"(ratings may contain future data)"
                )

    # Check for fallback warnings
    if "warnings" in slate_df.columns:
        fallback_rows = slate_df[slate_df["warnings"].notna()]
        if len(fallback_rows) > 0:
            warnings.append(
                f"FALLBACK: {len(fallback_rows)} games fell back to ratings "
                f"(archive unavailable)"
            )

    # Check method column
    if "method" in slate_df.columns:
        methods = slate_df["method"].unique()
        non_archive_methods = [m for m in methods if "archive" not in str(m)]
        if non_archive_methods:
            warnings.append(
                f"LOOKAHEAD: methods used: {non_archive_methods} "
                f"(should be 'archive_to_points' for backtesting)"
            )

    return warnings
