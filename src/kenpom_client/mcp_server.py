"""KenPom MCP Server - Exposes KenPom API as MCP tools for Claude.

This server provides direct access to KenPom basketball analytics data
through the Model Context Protocol (MCP). Works with Claude Code, Claude
Desktop, and any MCP-compatible client.

Features:
    - Dynamic effort classification for optimal model routing
    - Effort metadata on all tools for intelligent resource allocation
    - Query classification endpoint for pre-flight effort estimation

Usage:
    # Run directly
    uv run kenpom-mcp

    # Or via Python
    uv run python -m kenpom_client.mcp_server
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .client import KenPomClient
from .config import Settings
from .effort import EffortLevel, classify_effort
from .prediction import DEFAULT_HOME_COURT_ADVANTAGE, DEFAULT_SIGMOID_K, project_scores
from .slate import DEFAULT_HOME_ADV, DEFAULT_K, fanmatch_slate_table, join_with_odds

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Initialize server
server = Server("kenpom")

# Global client instance (lazy initialization)
_client: KenPomClient | None = None


def get_client() -> KenPomClient:
    """Get or create the KenPom client instance."""
    global _client
    if _client is None:
        settings = Settings.from_env()
        _client = KenPomClient(settings)
    return _client


def get_current_season() -> int:
    """Get the current basketball season year.

    The college basketball season runs from November to April. The season is
    named after the year it ends in (e.g., Nov 2024 - Apr 2025 = "2025 season").

    Returns:
        The season year (e.g., 2025 for the 2024-25 season).
    """
    today = date.today()
    # If we're in November or December, we're in next year's season
    if today.month >= 11:
        return today.year + 1
    # Otherwise (January-October), we're in the current year's season
    return today.year


# =============================================================================
# Tool Effort Metadata Registry
# =============================================================================


@dataclass
class ToolMetadata:
    """Metadata for a tool including effort classification hints."""

    name: str
    effort_level: EffortLevel
    description: str
    is_read_only: bool = True
    requires_reasoning: bool = False


# Registry of tool metadata with effort hints
TOOL_METADATA: dict[str, ToolMetadata] = {
    # Low effort - simple data retrieval
    "kenpom_teams": ToolMetadata(
        name="kenpom_teams",
        effort_level=EffortLevel.LOW,
        description="Simple team roster lookup",
        is_read_only=True,
    ),
    "kenpom_conferences": ToolMetadata(
        name="kenpom_conferences",
        effort_level=EffortLevel.LOW,
        description="Simple conference list lookup",
        is_read_only=True,
    ),
    "kenpom_ratings": ToolMetadata(
        name="kenpom_ratings",
        effort_level=EffortLevel.LOW,
        description="Current ratings lookup",
        is_read_only=True,
    ),
    "kenpom_predictions": ToolMetadata(
        name="kenpom_predictions",
        effort_level=EffortLevel.LOW,
        description="Game predictions for a date",
        is_read_only=True,
    ),
    "kenpom_fourfactors": ToolMetadata(
        name="kenpom_fourfactors",
        effort_level=EffortLevel.LOW,
        description="Four factors stats lookup",
        is_read_only=True,
    ),
    "kenpom_pointdist": ToolMetadata(
        name="kenpom_pointdist",
        effort_level=EffortLevel.LOW,
        description="Point distribution lookup",
        is_read_only=True,
    ),
    "kenpom_height": ToolMetadata(
        name="kenpom_height",
        effort_level=EffortLevel.LOW,
        description="Height and experience lookup",
        is_read_only=True,
    ),
    "kenpom_miscstats": ToolMetadata(
        name="kenpom_miscstats",
        effort_level=EffortLevel.LOW,
        description="Miscellaneous stats lookup",
        is_read_only=True,
    ),
    "kenpom_archive": ToolMetadata(
        name="kenpom_archive",
        effort_level=EffortLevel.LOW,
        description="Historical ratings lookup",
        is_read_only=True,
    ),
    # Medium effort - requires some analysis
    "kenpom_matchup": ToolMetadata(
        name="kenpom_matchup",
        effort_level=EffortLevel.MEDIUM,
        description="Head-to-head team comparison",
        is_read_only=True,
        requires_reasoning=True,
    ),
    "kenpom_top_teams": ToolMetadata(
        name="kenpom_top_teams",
        effort_level=EffortLevel.MEDIUM,
        description="Ranked team list by metric",
        is_read_only=True,
        requires_reasoning=True,
    ),
    "kenpom_project": ToolMetadata(
        name="kenpom_project",
        effort_level=EffortLevel.MEDIUM,
        description="Project game scores using efficiency model",
        is_read_only=True,
        requires_reasoning=True,
    ),
    "kenpom_slate": ToolMetadata(
        name="kenpom_slate",
        effort_level=EffortLevel.MEDIUM,
        description="Build full slate projection table with optional odds join",
        is_read_only=True,
        requires_reasoning=True,
    ),
    # Meta tools
    "classify_effort": ToolMetadata(
        name="classify_effort",
        effort_level=EffortLevel.LOW,
        description="Classify query effort level",
        is_read_only=True,
    ),
    "get_tool_effort": ToolMetadata(
        name="get_tool_effort",
        effort_level=EffortLevel.LOW,
        description="Get effort metadata for a tool",
        is_read_only=True,
    ),
}


def get_tool_metadata(tool_name: str) -> ToolMetadata | None:
    """Get metadata for a tool by name."""
    return TOOL_METADATA.get(tool_name)


def get_effort_for_tool(tool_name: str) -> EffortLevel:
    """Get the effort level for a tool, defaulting to MEDIUM if unknown."""
    metadata = get_tool_metadata(tool_name)
    return metadata.effort_level if metadata else EffortLevel.MEDIUM


def format_team_data(data: list[Any], fields: list[str] | None = None) -> str:
    """Format team data as a readable table."""
    if not data:
        return "No data found."

    # Convert Pydantic models to dicts
    records = [d.model_dump() if hasattr(d, "model_dump") else d for d in data]

    if fields:
        records = [{k: r[k] for k in fields if k in r} for r in records]

    # Build simple text table
    if not records:
        return "No data found."

    headers = list(records[0].keys())
    lines = [" | ".join(str(h) for h in headers)]
    lines.append("-" * len(lines[0]))

    for r in records[:50]:  # Limit to 50 rows for readability
        lines.append(" | ".join(str(r.get(h, "")) for h in headers))

    if len(records) > 50:
        lines.append(f"... and {len(records) - 50} more rows")

    return "\n".join(lines)


def format_single_team(data: list[Any], team_name: str) -> str:
    """Format data for a single team as key-value pairs."""
    records = [d.model_dump() if hasattr(d, "model_dump") else d for d in data]

    # Find matching team (case-insensitive partial match)
    team_lower = team_name.lower()
    matches = [r for r in records if team_lower in r.get("TeamName", "").lower()]

    if not matches:
        return f"No team found matching '{team_name}'"

    team = matches[0]
    lines = [f"Team: {team.get('TeamName', 'Unknown')}"]
    lines.append("-" * 40)

    for key, value in team.items():
        if key != "TeamName":
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


# =============================================================================
# Tool Definitions
# =============================================================================


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available KenPom tools."""
    return [
        # Core data tools
        Tool(
            name="kenpom_teams",
            description="Get team rosters with coach, arena, and conference info for a season.",
            inputSchema={
                "type": "object",
                "properties": {
                    "season": {
                        "type": "integer",
                        "description": "Season year (e.g., 2025 for 2024-25 season)",
                    },
                    "team": {
                        "type": "string",
                        "description": "Optional: Filter to specific team name",
                    },
                },
                "required": ["season"],
            },
        ),
        Tool(
            name="kenpom_conferences",
            description="Get list of conferences for a season.",
            inputSchema={
                "type": "object",
                "properties": {
                    "season": {
                        "type": "integer",
                        "description": "Season year (e.g., 2025)",
                    },
                },
                "required": ["season"],
            },
        ),
        Tool(
            name="kenpom_ratings",
            description="Get current efficiency ratings (AdjOE, AdjDE, AdjEM) for all teams. "
            "This is the core KenPom ranking data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "season": {
                        "type": "integer",
                        "description": "Season year (e.g., 2025)",
                    },
                    "team": {
                        "type": "string",
                        "description": "Optional: Filter to specific team name",
                    },
                },
                "required": ["season"],
            },
        ),
        Tool(
            name="kenpom_predictions",
            description="Get KenPom game predictions (FanMatch) for a specific date. "
            "Includes predicted scores, win probability, and spread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "game_date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (default: today)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="kenpom_fourfactors",
            description="Get Four Factors data: eFG%, TO%, OR%, FT Rate for offense and defense. "
            "These are the key stats that determine game outcomes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "season": {
                        "type": "integer",
                        "description": "Season year (e.g., 2025)",
                    },
                    "team": {
                        "type": "string",
                        "description": "Optional: Filter to specific team name",
                    },
                },
                "required": ["season"],
            },
        ),
        Tool(
            name="kenpom_pointdist",
            description="Get point distribution data: percentage of points from FTs, 2-pointers, "
            "and 3-pointers for offense and defense.",
            inputSchema={
                "type": "object",
                "properties": {
                    "season": {
                        "type": "integer",
                        "description": "Season year (e.g., 2025)",
                    },
                    "team": {
                        "type": "string",
                        "description": "Optional: Filter to specific team name",
                    },
                },
                "required": ["season"],
            },
        ),
        Tool(
            name="kenpom_height",
            description="Get height, experience, and roster continuity data for teams.",
            inputSchema={
                "type": "object",
                "properties": {
                    "season": {
                        "type": "integer",
                        "description": "Season year (e.g., 2025)",
                    },
                    "team": {
                        "type": "string",
                        "description": "Optional: Filter to specific team name",
                    },
                },
                "required": ["season"],
            },
        ),
        Tool(
            name="kenpom_miscstats",
            description="Get miscellaneous stats: shooting percentages, block/steal rates, "
            "assist rates, 3-point attempt rates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "season": {
                        "type": "integer",
                        "description": "Season year (e.g., 2025)",
                    },
                    "team": {
                        "type": "string",
                        "description": "Optional: Filter to specific team name",
                    },
                },
                "required": ["season"],
            },
        ),
        Tool(
            name="kenpom_archive",
            description="Get historical ratings from a specific past date. "
            "Use this for backtesting or historical analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "archive_date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
                    },
                },
                "required": ["archive_date"],
            },
        ),
        # Smart analytics tools
        Tool(
            name="kenpom_matchup",
            description="Compare two teams head-to-head with key metrics side by side. "
            "Great for analyzing upcoming games.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team1": {
                        "type": "string",
                        "description": "First team name (e.g., 'Duke')",
                    },
                    "team2": {
                        "type": "string",
                        "description": "Second team name (e.g., 'North Carolina')",
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season year (default: current)",
                    },
                },
                "required": ["team1", "team2"],
            },
        ),
        Tool(
            name="kenpom_top_teams",
            description="Get top N teams by a specific metric (AdjEM, AdjOE, AdjDE, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "description": "Metric to rank by: AdjEM, AdjOE, AdjDE, AdjTempo, SOS",
                        "enum": ["AdjEM", "AdjOE", "AdjDE", "AdjTempo", "SOS"],
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of teams to return (default: 25)",
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season year (default: current)",
                    },
                },
                "required": ["metric"],
            },
        ),
        # Score projection tool
        Tool(
            name="kenpom_project",
            description="Project game score, margin, total, and win probability for a matchup. "
            "Uses OE/DE crossover method with configurable home court advantage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "home_team": {
                        "type": "string",
                        "description": "Home team name (e.g., 'Duke')",
                    },
                    "visitor_team": {
                        "type": "string",
                        "description": "Visitor team name (e.g., 'North Carolina')",
                    },
                    "archive_date": {
                        "type": "string",
                        "description": "Optional: Use archive ratings from this date (YYYY-MM-DD) "
                        "for backtesting. If omitted, uses current ratings.",
                    },
                    "home_adv": {
                        "type": "number",
                        "description": f"Home court advantage in points (default: {DEFAULT_HOME_COURT_ADVANTAGE})",
                    },
                    "k": {
                        "type": "number",
                        "description": f"Sigmoid scaling factor for win probability (default: {DEFAULT_SIGMOID_K})",
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season year (default: current, ignored if archive_date set)",
                    },
                },
                "required": ["home_team", "visitor_team"],
            },
        ),
        # Slate table tool
        Tool(
            name="kenpom_slate",
            description="Build full projection slate table for a date. "
            "Returns all games with projected scores, margins, win probabilities, and optional market odds. "
            "Use backtest=true for time-correct archive features.",
            inputSchema={
                "type": "object",
                "properties": {
                    "game_date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (default: today)",
                    },
                    "backtest": {
                        "type": "boolean",
                        "description": "Use archive features for time-correct backtesting (default: false)",
                    },
                    "join_odds": {
                        "type": "boolean",
                        "description": "Join with market odds if available (default: false)",
                    },
                    "home_adv": {
                        "type": "number",
                        "description": f"Home court advantage in points (default: {DEFAULT_HOME_ADV})",
                    },
                    "k": {
                        "type": "number",
                        "description": f"Sigmoid scaling factor for win probability (default: {DEFAULT_K})",
                    },
                },
                "required": [],
            },
        ),
        # Meta tools for effort classification
        Tool(
            name="classify_effort",
            description="Classify a query's effort level for dynamic model routing. "
            "Returns recommended effort level (low/medium/high), model hint, and thinking budget. "
            "Use this to determine appropriate reasoning depth before executing complex tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user query or task description to classify",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_tool_effort",
            description="Get the effort level metadata for a specific tool. "
            "Returns the tool's default effort level and whether it requires reasoning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to get effort metadata for",
                    },
                },
                "required": ["tool_name"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    client = get_client()
    current_year = get_current_season()

    try:
        if name == "kenpom_teams":
            season = arguments.get("season", current_year)
            team = arguments.get("team")
            data = client.teams(y=season)
            if team:
                result = format_single_team(data, team)
            else:
                result = format_team_data(
                    data, ["TeamName", "ConfShort", "Coach", "Arena", "ArenaCity"]
                )

        elif name == "kenpom_conferences":
            season = arguments.get("season", current_year)
            data = client.conferences(y=season)
            result = format_team_data(data)

        elif name == "kenpom_ratings":
            season = arguments.get("season", current_year)
            team = arguments.get("team")
            data = client.ratings(y=season)
            if team:
                result = format_single_team(data, team)
            else:
                # Sort by AdjEM and show key fields
                records = sorted(
                    [d.model_dump() for d in data], key=lambda x: x["AdjEM"], reverse=True
                )
                fields = ["TeamName", "ConfShort", "AdjEM", "AdjOE", "AdjDE", "Wins", "Losses"]
                result = format_team_data(records, fields)

        elif name == "kenpom_predictions":
            game_date = arguments.get("game_date", date.today().isoformat())
            data = client.fanmatch(d=game_date)
            if not data:
                result = f"No games found for {game_date}"
            else:
                lines = [f"KenPom Predictions for {game_date}", "=" * 50]
                for game in data:
                    g = game.model_dump()
                    spread = g["HomePred"] - g["VisitorPred"]
                    if spread > 0:
                        spread_str = f"{g['Home']} -{abs(spread):.1f}"
                    else:
                        spread_str = f"{g['Visitor']} -{abs(spread):.1f}"
                    lines.append(
                        f"{g['Visitor']} @ {g['Home']}: {g['VisitorPred']:.1f}-{g['HomePred']:.1f} "
                        f"(Line: {spread_str}, WP: {g['HomeWP'] * 100:.0f}%)"
                    )
                result = "\n".join(lines)

        elif name == "kenpom_fourfactors":
            season = arguments.get("season", current_year)
            team = arguments.get("team")
            data = client.four_factors(y=season)
            if team:
                result = format_single_team(data, team)
            else:
                fields = [
                    "TeamName",
                    "eFG_Pct",
                    "TO_Pct",
                    "OR_Pct",
                    "FT_Rate",
                    "AdjOE",
                    "AdjDE",
                ]
                result = format_team_data(data, fields)

        elif name == "kenpom_pointdist":
            season = arguments.get("season", current_year)
            team = arguments.get("team")
            data = client.point_distribution(y=season)
            if team:
                result = format_single_team(data, team)
            else:
                fields = [
                    "TeamName",
                    "ConfShort",
                    "OffFt",
                    "OffFg2",
                    "OffFg3",
                    "DefFt",
                    "DefFg2",
                    "DefFg3",
                ]
                result = format_team_data(data, fields)

        elif name == "kenpom_height":
            season = arguments.get("season", current_year)
            team = arguments.get("team")
            data = client.height(y=season)
            if team:
                result = format_single_team(data, team)
            else:
                fields = ["TeamName", "ConfShort", "AvgHgt", "HgtEff", "Exp", "Continuity"]
                result = format_team_data(data, fields)

        elif name == "kenpom_miscstats":
            season = arguments.get("season", current_year)
            team = arguments.get("team")
            data = client.misc_stats(y=season)
            if team:
                result = format_single_team(data, team)
            else:
                fields = ["TeamName", "FG3Pct", "FG2Pct", "FTPct", "ARate", "StlRate"]
                result = format_team_data(data, fields)

        elif name == "kenpom_archive":
            archive_date = arguments["archive_date"]
            data = client.archive(d=archive_date)
            fields = ["TeamName", "ConfShort", "AdjEM", "AdjOE", "AdjDE", "AdjTempo"]
            result = format_team_data(data, fields)

        elif name == "kenpom_matchup":
            team1 = arguments["team1"]
            team2 = arguments["team2"]
            season = arguments.get("season", current_year)

            ratings = client.ratings(y=season)
            ff = client.four_factors(y=season)

            # Find teams
            def find_team(data: list, name: str) -> dict | None:
                name_lower = name.lower()
                for d in data:
                    r = d.model_dump() if hasattr(d, "model_dump") else d
                    if name_lower in r.get("TeamName", "").lower():
                        return r
                return None

            r1 = find_team(ratings, team1)
            r2 = find_team(ratings, team2)
            ff1 = find_team(ff, team1)
            ff2 = find_team(ff, team2)

            if not r1 or not r2:
                result = f"Could not find one or both teams: {team1}, {team2}"
            else:
                lines = [
                    f"MATCHUP: {r1['TeamName']} vs {r2['TeamName']}",
                    "=" * 50,
                    "",
                    f"{'Metric':<20} {r1['TeamName']:<15} {r2['TeamName']:<15}",
                    "-" * 50,
                    f"{'AdjEM':<20} {r1['AdjEM']:<15.1f} {r2['AdjEM']:<15.1f}",
                    f"{'AdjOE':<20} {r1['AdjOE']:<15.1f} {r2['AdjOE']:<15.1f}",
                    f"{'AdjDE':<20} {r1['AdjDE']:<15.1f} {r2['AdjDE']:<15.1f}",
                    f"{'AdjTempo':<20} {r1['AdjTempo']:<15.1f} {r2['AdjTempo']:<15.1f}",
                    f"{'Record':<20} {r1['Wins']}-{r1['Losses']:<12} {r2['Wins']}-{r2['Losses']}",
                ]
                if ff1 and ff2:
                    lines.extend(
                        [
                            "",
                            "Four Factors (Offense):",
                            f"{'eFG%':<20} {ff1['eFG_Pct']:<15.1f} {ff2['eFG_Pct']:<15.1f}",
                            f"{'TO%':<20} {ff1['TO_Pct']:<15.1f} {ff2['TO_Pct']:<15.1f}",
                            f"{'OR%':<20} {ff1['OR_Pct']:<15.1f} {ff2['OR_Pct']:<15.1f}",
                            f"{'FT Rate':<20} {ff1['FT_Rate']:<15.1f} {ff2['FT_Rate']:<15.1f}",
                        ]
                    )
                result = "\n".join(lines)

        elif name == "kenpom_top_teams":
            metric = arguments["metric"]
            count = arguments.get("count", 25)
            season = arguments.get("season", current_year)

            data = client.ratings(y=season)
            records = [d.model_dump() for d in data]

            # Sort by metric (descending for most, ascending for AdjDE)
            reverse = metric != "AdjDE"
            sorted_data = sorted(records, key=lambda x: x.get(metric, 0), reverse=reverse)[:count]

            lines = [f"Top {count} Teams by {metric} ({season})", "=" * 50]
            for i, team in enumerate(sorted_data, 1):
                lines.append(
                    f"{i:2}. {team['TeamName']:<25} {metric}: {team[metric]:.1f} "
                    f"(Record: {team['Wins']}-{team['Losses']})"
                )
            result = "\n".join(lines)

        elif name == "kenpom_project":
            home_team = arguments["home_team"]
            visitor_team = arguments["visitor_team"]
            archive_date = arguments.get("archive_date")
            home_adv = arguments.get("home_adv", DEFAULT_HOME_COURT_ADVANTAGE)
            k = arguments.get("k", DEFAULT_SIGMOID_K)
            season = arguments.get("season", current_year)

            # Get ratings (archive or current)
            if archive_date:
                data = client.archive(d=archive_date)
            else:
                data = client.ratings(y=season)

            # Find teams (case-insensitive partial match)
            def find_rating(name: str):
                name_lower = name.lower()
                for r in data:
                    if name_lower in r.TeamName.lower():
                        return r
                return None

            home = find_rating(home_team)
            visitor = find_rating(visitor_team)

            if not home or not visitor:
                missing = []
                if not home:
                    missing.append(home_team)
                if not visitor:
                    missing.append(visitor_team)
                result = f"Could not find team(s): {', '.join(missing)}"
            else:
                proj = project_scores(home, visitor, home_adv=home_adv, k=k)
                lines = [
                    f"PROJECTION: {visitor.TeamName} @ {home.TeamName}",
                    "=" * 50,
                    "",
                    f"Projected Score: {proj.proj_visitor:.1f} - {proj.proj_home:.1f}",
                    f"Projected Total: {proj.proj_total:.1f}",
                    f"Projected Margin: {proj.proj_margin:+.1f} (home)",
                    f"Possessions: {proj.possessions:.1f}",
                    "",
                    "Win Probability:",
                    f"  {home.TeamName}: {proj.win_prob_home:.1%}",
                    f"  {visitor.TeamName}: {proj.win_prob_visitor:.1%}",
                    "",
                    "Parameters:",
                    f"  Home Adv: {proj.home_adv}",
                    f"  Sigmoid k: {proj.k}",
                    f"  Method: {proj.method}",
                    f"  Source: {proj.feature_source}",
                ]
                result = "\n".join(lines)

        elif name == "kenpom_slate":
            game_date = arguments.get("game_date", date.today().isoformat())
            backtest = arguments.get("backtest", False)
            do_join_odds = arguments.get("join_odds", False)
            home_adv = arguments.get("home_adv", DEFAULT_HOME_ADV)
            k_val = arguments.get("k", DEFAULT_K)

            df = fanmatch_slate_table(
                d=game_date,
                k=k_val,
                home_adv=home_adv,
                use_archive=backtest,
                archive_fallback_to_ratings=True,
                client=client,
            )

            if df.empty:
                result = f"No games found for {game_date}"
            else:
                # Join odds if requested
                if do_join_odds:
                    df = join_with_odds(df, odds_date=game_date)

                # Format output
                lines = [
                    f"SLATE TABLE: {game_date}",
                    f"Mode: {'Backtest (archive)' if backtest else 'Live (ratings)'}",
                    f"Games: {len(df)}",
                    "=" * 70,
                    "",
                ]

                # Column subset for display
                display_cols = ["visitor", "home", "proj_margin", "proj_total",
                                "win_prob_home", "feature_source_home"]
                if do_join_odds and "odds_spread" in df.columns:
                    display_cols.extend(["odds_spread", "spread_edge"])

                for _, row in df.iterrows():
                    margin = row.get("proj_margin", 0)
                    wp = row.get("win_prob_home", 0.5)
                    line = f"{row['visitor']} @ {row['home']}: "
                    line += f"Margin {margin:+.1f}, Total {row.get('proj_total', 0):.1f}, "
                    line += f"WP {wp:.0%}"

                    if do_join_odds and "odds_spread" in row and row.get("odds_joined"):
                        odds_spread = row.get("odds_spread", 0)
                        edge = row.get("spread_edge", 0)
                        line += f" | Mkt {odds_spread:+.1f}, Edge {edge:+.1f}"

                    # Add warning indicator
                    if row.get("warnings"):
                        line += " [!]"

                    lines.append(line)

                # Summary stats
                if do_join_odds and "spread_edge" in df.columns:
                    edges = df["spread_edge"].dropna()
                    if len(edges) > 0:
                        lines.append("")
                        lines.append(f"Avg Edge: {edges.mean():+.1f} | "
                                     f"Max Edge: {edges.max():+.1f} | "
                                     f"Odds Joined: {df['odds_joined'].sum()}/{len(df)}")

                result = "\n".join(lines)

        elif name == "classify_effort":
            query = arguments["query"]
            classification = classify_effort(query)
            lines = [
                "Effort Classification",
                "=" * 40,
                f"Query: {query[:100]}{'...' if len(query) > 100 else ''}",
                "",
                f"Level: {classification.level.value.upper()}",
                f"Confidence: {classification.confidence:.0%}",
                f"Model Hint: {classification.model_hint}",
                f"Thinking Budget: {classification.thinking_budget:,} tokens",
                "",
                f"Reasoning: {classification.reasoning}",
            ]
            if classification.signals_matched:
                lines.append(f"Signals: {', '.join(classification.signals_matched[:5])}")
            result = "\n".join(lines)

        elif name == "get_tool_effort":
            tool_name = arguments["tool_name"]
            metadata = get_tool_metadata(tool_name)
            if metadata:
                lines = [
                    f"Tool Effort Metadata: {tool_name}",
                    "=" * 40,
                    f"Effort Level: {metadata.effort_level.value.upper()}",
                    f"Model Hint: {metadata.effort_level.model_hint}",
                    f"Thinking Budget: {metadata.effort_level.thinking_budget:,} tokens",
                    f"Read-Only: {metadata.is_read_only}",
                    f"Requires Reasoning: {metadata.requires_reasoning}",
                    f"Description: {metadata.description}",
                ]
                result = "\n".join(lines)
            else:
                available = ", ".join(TOOL_METADATA.keys())
                result = f"Unknown tool: {tool_name}. Available tools: {available}"

        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        log.exception(f"Error in tool {name}")
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def run_server() -> None:
    """Run the MCP server."""
    log.info("Starting KenPom MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point for the MCP server."""
    import asyncio

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
