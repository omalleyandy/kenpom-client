from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd

from .client import KenPomClient
from .models import FourFactors, PointDistribution

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeamSnapshot:
    date: str
    season: int
    team_id: int
    team: str
    conf: str
    wins: int
    losses: int
    adj_em: float
    adj_oe: float
    adj_de: float
    adj_tempo: float
    tempo: float
    sos: float


@dataclass(frozen=True)
class EnrichedTeamSnapshot(TeamSnapshot):
    """Team snapshot enriched with four factors, point distribution, and sigma.

    Extends TeamSnapshot with optional enrichment fields. All enrichment fields
    are Optional to support partial enrichment and backward compatibility.
    """

    # Four Factors (8 fields) - core determinants of efficiency
    efg_pct: Optional[float] = None  # Effective FG%
    to_pct: Optional[float] = None  # Turnover %
    or_pct: Optional[float] = None  # Offensive Rebound %
    ft_rate: Optional[float] = None  # Free Throw Rate
    defg_pct: Optional[float] = None  # Defensive eFG%
    dto_pct: Optional[float] = None  # Defensive TO%
    dor_pct: Optional[float] = None  # Defensive OR%
    dft_rate: Optional[float] = None  # Defensive FT Rate

    # Point Distribution (6 fields) - scoring breakdown for sigma calculation
    off_ft: Optional[float] = None  # % points from FTs
    off_fg2: Optional[float] = None  # % points from 2PT
    off_fg3: Optional[float] = None  # % points from 3PT
    def_ft: Optional[float] = None  # % opponent points from FTs
    def_fg2: Optional[float] = None  # % opponent points from 2PT
    def_fg3: Optional[float] = None  # % opponent points from 3PT

    # Derived metric
    sigma: Optional[float] = None  # Scoring margin std dev (for win probability)

    # Metadata
    enrichment_date: Optional[str] = None  # When enrichment was added (YYYY-MM-DD)


def _calculate_sigma(
    off_fg3: float,
    def_fg3: float,
    tempo: float,
) -> float:
    """Calculate sigma (scoring margin std dev) from 3PT rate and tempo.

    Theory: Game variance primarily driven by 3-point shooting variance
    and tempo (more possessions = more variance).

    Args:
        off_fg3: Offensive % of points from 3-pointers
        def_fg3: Defensive % of points from 3-pointers allowed
        tempo: Adjusted tempo (possessions per game)

    Returns:
        Sigma value (typically 10-12 for college basketball)
    """
    base_variance = 11.0  # Empirical NCAA constant

    # Calculate average 3PT rate (higher 3PT = higher variance)
    avg_3pt_rate = (off_fg3 + def_fg3) / 2.0

    # Tempo adjustment (normalized to ~68 possessions)
    tempo_factor = (tempo / 68.0) ** 0.5

    # 3PT variance adjustment (30% baseline)
    three_pt_adjustment = 1.0 + (avg_3pt_rate - 30.0) / 100.0

    # Combined formula
    sigma = base_variance * tempo_factor * three_pt_adjustment

    # Clamp to reasonable range [9.5, 13.0]
    return max(9.5, min(13.0, sigma))


def _extract_season_from_archive_date(date: str) -> int:
    """Infer season year from archive date.

    Logic:
        - Nov-Dec: next year's season (Nov 2024 = 2025 season)
        - Jan-Oct: current year's season (Mar 2025 = 2025 season)

    Args:
        date: Archive date in YYYY-MM-DD format

    Returns:
        Season year (e.g., 2025)

    Examples:
        "2024-11-15" -> 2025
        "2025-03-15" -> 2025
        "2024-10-15" -> 2024
    """
    dt = datetime.strptime(date, "%Y-%m-%d")

    # Nov-Dec are next year's season
    if dt.month >= 11:
        return dt.year + 1
    else:
        return dt.year


def _merge_enrichment_data(
    base_rows: List[TeamSnapshot] | list,
    four_factors_data: Optional[List[FourFactors]],
    point_dist_data: Optional[List[PointDistribution]],
    include_sigma: bool,
    date: str,
) -> List[EnrichedTeamSnapshot]:
    """Merge base snapshot with enrichment data.

    Args:
        base_rows: List of TeamSnapshot or dict records
        four_factors_data: Optional four factors API data
        point_dist_data: Optional point distribution API data
        include_sigma: Whether to calculate sigma values
        date: Snapshot date for enrichment_date field

    Returns:
        List of EnrichedTeamSnapshot instances
    """
    # 1. Build lookup dicts by normalized TeamName (lowercase, strip)
    ff_lookup = {}
    if four_factors_data:
        ff_lookup = {t.TeamName.strip().lower(): t for t in four_factors_data}

    pd_lookup = {}
    if point_dist_data:
        pd_lookup = {t.TeamName.strip().lower(): t for t in point_dist_data}

    # 2. Iterate base rows, merge enrichment
    enriched_rows = []
    for base in base_rows:
        # Get team name (handle both TeamSnapshot and dict)
        if isinstance(base, dict):
            team_name = base["team"]
            tempo_val = base.get("tempo", base.get("adj_tempo", 68.0))
            # Ensure tempo is a float (fallback if None)
            tempo: float = float(tempo_val) if tempo_val is not None else 68.0
        else:
            team_name = base.team
            tempo = base.tempo

        norm_name = team_name.strip().lower()

        # Lookup enrichment data
        ff = ff_lookup.get(norm_name)
        pd = pd_lookup.get(norm_name)

        # Log warnings for missing data
        if four_factors_data and not ff:
            log.warning(f"No four_factors data for: {team_name}")
        if point_dist_data and not pd:
            log.warning(f"No point_dist data for: {team_name}")

        # Calculate sigma if requested and data available
        sigma_val = None
        if include_sigma and pd:
            sigma_val = _calculate_sigma(
                pd.OffFg3,
                pd.DefFg3,
                tempo,
            )

        # Create EnrichedTeamSnapshot
        # Convert base dict to TeamSnapshot first if needed
        if isinstance(base, dict):
            # Archive case - construct minimal TeamSnapshot
            # Use adj_tempo as fallback for tempo
            tempo_for_snapshot = base.get("tempo", base["adj_tempo"])
            if tempo_for_snapshot is None:
                tempo_for_snapshot = base["adj_tempo"]

            base_snapshot = TeamSnapshot(
                date=base["date"],
                season=base["season"],
                team_id=-1,  # Not available in archive
                team=base["team"],
                conf=base["conf"],
                wins=0,  # Not available in archive
                losses=0,
                adj_em=base["adj_em"],
                adj_oe=base["adj_oe"],
                adj_de=base["adj_de"],
                adj_tempo=base["adj_tempo"],
                tempo=tempo_for_snapshot,
                sos=0.0,  # Not available in archive
            )
        else:
            base_snapshot = base

        enriched = EnrichedTeamSnapshot(
            **asdict(base_snapshot),
            # Four factors
            efg_pct=ff.eFG_Pct if ff else None,
            to_pct=ff.TO_Pct if ff else None,
            or_pct=ff.OR_Pct if ff else None,
            ft_rate=ff.FT_Rate if ff else None,
            defg_pct=ff.DeFG_Pct if ff else None,
            dto_pct=ff.DTO_Pct if ff else None,
            dor_pct=ff.DOR_Pct if ff else None,
            dft_rate=ff.DFT_Rate if ff else None,
            # Point distribution
            off_ft=pd.OffFt if pd else None,
            off_fg2=pd.OffFg2 if pd else None,
            off_fg3=pd.OffFg3 if pd else None,
            def_ft=pd.DefFt if pd else None,
            def_fg2=pd.DefFg2 if pd else None,
            def_fg3=pd.DefFg3 if pd else None,
            # Derived
            sigma=sigma_val,
            enrichment_date=date,
        )

        enriched_rows.append(enriched)

    return enriched_rows


def build_snapshot_from_ratings(
    *,
    client: KenPomClient,
    date: str,
    season_y: int,
    include_four_factors: bool = False,
    include_point_dist: bool = False,
    calculate_sigma: bool = False,
) -> pd.DataFrame:
    """Build snapshot from current-season ratings with optional enrichment.

    Use current-season 'ratings' as a snapshot of "as of now".
    (Backtesting-safe snapshots should use archive(d=...)).

    Args:
        client: KenPomClient instance
        date: Label date (YYYY-MM-DD)
        season_y: Season year
        include_four_factors: Add four factors metrics (8 fields)
        include_point_dist: Add point distribution metrics (6 fields)
        calculate_sigma: Compute sigma from point_dist (requires include_point_dist=True)

    Returns:
        DataFrame with TeamSnapshot or EnrichedTeamSnapshot rows

    Raises:
        ValueError: If calculate_sigma=True but include_point_dist=False

    Note:
        - If any enrichment flag is True, returns EnrichedTeamSnapshot
        - calculate_sigma requires include_point_dist=True
        - Missing enrichment data logs warning, sets fields to None
    """
    # Validate parameters
    if calculate_sigma and not include_point_dist:
        raise ValueError("calculate_sigma requires include_point_dist=True")

    # Fetch base data
    teams = {t.TeamName: t.TeamID for t in client.teams(y=season_y)}
    ratings = client.ratings(y=season_y)

    rows: List[TeamSnapshot] = []
    for r in ratings:
        team_id = teams.get(r.TeamName, -1)
        if team_id == -1:
            # some naming edge case; keep record but flag with -1
            team_id = -1
        rows.append(
            TeamSnapshot(
                date=date,
                season=r.Season,
                team_id=team_id,
                team=r.TeamName,
                conf=r.ConfShort,
                wins=r.Wins,
                losses=r.Losses,
                adj_em=r.AdjEM,
                adj_oe=r.AdjOE,
                adj_de=r.AdjDE,
                adj_tempo=r.AdjTempo,
                tempo=r.Tempo,
                sos=r.SOS,
            )
        )

    # Early return if no enrichment requested
    if not (include_four_factors or include_point_dist):
        df = pd.DataFrame([asdict(x) for x in rows])
        return df

    # Fetch enrichment data
    ff_data = None
    if include_four_factors:
        ff_data = client.four_factors(y=season_y)

    pd_data = None
    if include_point_dist:
        pd_data = client.point_distribution(y=season_y)

    # Merge and return
    enriched = _merge_enrichment_data(rows, ff_data, pd_data, calculate_sigma, date)

    return pd.DataFrame([asdict(x) for x in enriched])


def build_snapshot_from_archive(
    *,
    client: KenPomClient,
    date: str,  # YYYY-MM-DD
    include_four_factors: bool = False,
    include_point_dist: bool = False,
    calculate_sigma: bool = False,
) -> pd.DataFrame:
    """Build snapshot from archived ratings with optional enrichment.

    Backtesting-safe: pulls archive(d=YYYY-MM-DD) so you can reproduce
    what the world looked like that day.

    Args:
        client: KenPomClient instance
        date: Archive date (YYYY-MM-DD)
        include_four_factors: Add four factors metrics (8 fields)
        include_point_dist: Add point distribution metrics (6 fields)
        calculate_sigma: Compute sigma from point_dist (requires include_point_dist=True)

    Returns:
        DataFrame with dict-based rows or EnrichedTeamSnapshot if enriched

    Raises:
        ValueError: If calculate_sigma=True but include_point_dist=False

    Note:
        - Base archive snapshot: dict-based (9 fields, no team_id/wins/losses)
        - Enriched archive snapshot: EnrichedTeamSnapshot (with None for unavailable fields)
        - Enrichment uses season-wide data, NOT point-in-time (temporal mismatch)
        - calculate_sigma requires include_point_dist=True
    """
    # Validate parameters
    if calculate_sigma and not include_point_dist:
        raise ValueError("calculate_sigma requires include_point_dist=True")

    # Fetch base archive data
    archived = client.archive(d=date)

    rows = []
    for a in archived:
        rows.append(
            {
                "date": a.ArchiveDate,
                "season": a.Season,
                "team": a.TeamName,
                "conf": a.ConfShort,
                "adj_em": a.AdjEM,
                "adj_oe": a.AdjOE,
                "adj_de": a.AdjDE,
                "adj_tempo": a.AdjTempo,
                "preseason": a.Preseason,
            }
        )

    # Early return if no enrichment
    if not (include_four_factors or include_point_dist):
        return pd.DataFrame(rows)

    # Infer season from archive date
    season_y = _extract_season_from_archive_date(date)
    log.info(f"Archive enrichment uses season-wide data (y={season_y})")

    # Fetch enrichment data (season-wide)
    ff_data = None
    if include_four_factors:
        ff_data = client.four_factors(y=season_y)

    pd_data = None
    if include_point_dist:
        pd_data = client.point_distribution(y=season_y)

    # Merge and return
    enriched = _merge_enrichment_data(rows, ff_data, pd_data, calculate_sigma, date)

    return pd.DataFrame([asdict(x) for x in enriched])
