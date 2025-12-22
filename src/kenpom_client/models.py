from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Team(BaseModel):
    Season: int
    TeamName: str
    TeamID: int
    ConfShort: str
    Coach: Optional[str] = None
    Arena: Optional[str] = None
    ArenaCity: Optional[str] = None
    ArenaState: Optional[str] = None


class Conference(BaseModel):
    Season: int
    ConfID: int
    ConfShort: str
    ConfLong: str


class Rating(BaseModel):
    DataThrough: str
    Season: int
    TeamName: str
    ConfShort: str
    Coach: Optional[str] = None
    Wins: int
    Losses: int
    AdjEM: float
    AdjOE: float
    AdjDE: float
    AdjTempo: float
    Tempo: float
    SOS: float
    Luck: float | None = None
    Seed: Optional[int] = None


class ArchiveRating(BaseModel):
    ArchiveDate: str
    Season: int
    Preseason: str
    TeamName: str
    ConfShort: str
    AdjEM: float
    AdjOE: float
    AdjDE: float
    AdjTempo: float
    Seed: Optional[int] = None


class FanmatchGame(BaseModel):
    Season: int
    GameID: int
    DateOfGame: str
    Visitor: str
    Home: str
    HomeRank: Optional[int] = None
    VisitorRank: Optional[int] = None
    HomePred: float
    VisitorPred: float
    HomeWP: float
    PredTempo: float
    ThrillScore: float


class FourFactors(BaseModel):
    """Four Factors analytics - the four key stats that determine game outcomes."""

    DataThrough: str
    ConfOnly: str
    TeamName: str
    Season: int
    # Offensive Four Factors
    eFG_Pct: float  # Effective FG%
    RankeFG_Pct: int
    TO_Pct: float  # Turnover %
    RankTO_Pct: int
    OR_Pct: float  # Offensive Rebound %
    RankOR_Pct: int
    FT_Rate: float  # Free Throw Rate
    RankFT_Rate: int
    # Defensive Four Factors
    DeFG_Pct: float
    RankDeFG_Pct: int
    DTO_Pct: float
    RankDTO_Pct: int
    DOR_Pct: float
    RankDOR_Pct: int
    DFT_Rate: float
    RankDFT_Rate: int
    # Efficiency & Tempo
    OE: float  # Raw Offensive Efficiency
    RankOE: int
    DE: float  # Raw Defensive Efficiency
    RankDE: int
    Tempo: float
    RankTempo: int
    AdjOE: float  # Adjusted Offensive Efficiency
    RankAdjOE: int
    AdjDE: float  # Adjusted Defensive Efficiency
    RankAdjDE: int
    AdjTempo: float
    RankAdjTempo: int


class PointDistribution(BaseModel):
    """Point distribution - where teams get/allow their points from."""

    DataThrough: str
    ConfOnly: str
    Season: int
    TeamName: str
    ConfShort: str
    # Offensive point distribution (% of points from each source)
    OffFt: float  # % from free throws
    RankOffFt: int
    OffFg2: float  # % from 2-pointers
    RankOffFg2: int
    OffFg3: float  # % from 3-pointers
    RankOffFg3: int
    # Defensive point distribution (% allowed from each source)
    DefFt: float
    RankDefFt: int
    DefFg2: float
    RankDefFg2: int
    DefFg3: float
    RankDefFg3: int


class Height(BaseModel):
    """Height, experience, and roster continuity data."""

    DataThrough: str
    Season: int
    TeamName: str
    ConfShort: str
    AvgHgt: float  # Average height in inches
    AvgHgtRank: int
    HgtEff: float  # Effective height
    HgtEffRank: int
    # Height advantage by position (1=PG through 5=C)
    Hgt5: float
    Hgt5Rank: int
    Hgt4: float
    Hgt4Rank: int
    Hgt3: float
    Hgt3Rank: int
    Hgt2: float
    Hgt2Rank: int
    Hgt1: float
    Hgt1Rank: int
    # Experience and continuity
    Exp: float  # Average experience (eligibility-weighted)
    ExpRank: int
    Bench: float  # Bench minutes %
    BenchRank: int
    Continuity: float  # Roster continuity %
    RankContinuity: int


class MiscStats(BaseModel):
    """Miscellaneous team statistics - shooting, blocks, steals, assists."""

    DataThrough: str
    ConfOnly: str
    Season: int
    TeamName: str
    ConfShort: str
    # Offensive stats
    FG3Pct: float  # 3-point %
    RankFG3Pct: int
    FG2Pct: float  # 2-point %
    RankFG2Pct: int
    FTPct: float  # Free throw %
    RankFTPct: int
    BlockPct: float  # Block %
    RankBlockPct: int
    StlRate: float  # Steal rate
    RankStlRate: int
    NSTRate: float  # Non-steal turnover rate
    RankNSTRate: int
    ARate: float  # Assist rate
    RankARate: int
    F3GRate: float  # 3-point attempt rate
    RankF3GRate: int
    AdjOE: float
    RankAdjOE: int
    # Defensive stats (opponent stats)
    OppFG3Pct: float
    RankOppFG3Pct: int
    OppFG2Pct: float
    RankOppFG2Pct: int
    OppFTPct: float
    RankOppFTPct: int
    OppBlockPct: float
    RankOppBlockPct: int
    OppStlRate: float
    RankOppStlRate: int
    OppNSTRate: float
    RankOppNSTRate: int
    OppARate: float
    RankOppARate: int
    OppF3GRate: float
    RankOppF3GRate: int
    AdjDE: float
    RankAdjDE: int
