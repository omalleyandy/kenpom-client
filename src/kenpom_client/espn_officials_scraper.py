"""Scraper for ESPN game officials assignments.

This module scrapes ESPN's college basketball schedule and gamecast pages
to get officiating crew assignments, then matches them to KenPom FAA ratings.

Officials are typically posted 1-2 hours before tip-off, so this scraper
handles the case where refs aren't yet available gracefully.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from playwright.sync_api import Page, sync_playwright

from kenpom_client.ref_ratings_scraper import (
    RefRatingsSnapshot,
    load_ref_ratings_snapshot,
)


# Team name normalization mapping (ESPN name -> KenPom name)
# This handles common differences between ESPN and KenPom naming conventions
TEAM_NAME_MAP: dict[str, str] = {
    # Common variations
    "UConn": "Connecticut",
    "UCONN": "Connecticut",
    "UNC": "North Carolina",
    "USC": "Southern California",
    "UCF": "Central Florida",
    "UNLV": "UNLV",
    "SMU": "SMU",
    "LSU": "LSU",
    "TCU": "TCU",
    "BYU": "BYU",
    "VCU": "VCU",
    "UAB": "UAB",
    "UTEP": "UTEP",
    "UTSA": "UT San Antonio",
    "UMass": "Massachusetts",
    "UIC": "Illinois Chicago",
    "SIUE": "SIU Edwardsville",
    "SIU": "Southern Illinois",
    "NIU": "Northern Illinois",
    "FIU": "Florida International",
    "FAU": "Florida Atlantic",
    "FDU": "Fairleigh Dickinson",
    "LIU": "Long Island University",
    "NJIT": "NJIT",
    "NC State": "N.C. State",
    "Ole Miss": "Mississippi",
    "Pitt": "Pittsburgh",
    "Miami (FL)": "Miami FL",
    "Miami": "Miami FL",
    "Saint Mary's": "Saint Mary's",
    "St. Mary's": "Saint Mary's",
    "Saint John's": "St. John's",
    "St. Joseph's": "Saint Joseph's",
    "Saint Peter's": "Saint Peter's",
    "St. Peter's": "Saint Peter's",
    "St. Bonaventure": "St. Bonaventure",
    "Saint Bonaventure": "St. Bonaventure",
    "Loyola Chicago": "Loyola Chicago",
    "Loyola (MD)": "Loyola MD",
    "Loyola Marymount": "Loyola Marymount",
    "Texas A&M": "Texas A&M",
    "Texas A&M-CC": "Texas A&M Corpus Chris",
    "Texas A&M-Commerce": "Texas A&M Commerce",
    "Penn": "Pennsylvania",
    "Army": "Army",
    "Navy": "Navy",
    "Air Force": "Air Force",
    # Add more as needed
}


@dataclass
class GameOfficials:
    """Officials assignment for a single game."""

    game_id: str  # ESPN game ID
    home_team: str  # Home team name (ESPN)
    away_team: str  # Away team name (ESPN)
    home_team_kenpom: Optional[str]  # Normalized name for KenPom matching
    away_team_kenpom: Optional[str]  # Normalized name for KenPom matching
    game_time: Optional[str]  # Game time string
    officials: list[str]  # List of referee names (empty if not posted)
    officials_posted: bool  # Whether officials have been posted
    crew_faa: Optional[float]  # Combined FAA for the crew (None if not calculable)
    individual_faa: dict[str, float]  # FAA for each official


@dataclass
class DailyOfficialsSnapshot:
    """Snapshot of all game officials for a day."""

    date: str  # Date of snapshot (YYYY-MM-DD)
    games: list[GameOfficials]
    games_with_officials: int  # Count of games where officials are posted
    games_without_officials: int  # Count of games where officials not yet posted

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        rows = []
        for g in self.games:
            rows.append(
                {
                    "game_id": g.game_id,
                    "home_team": g.home_team,
                    "away_team": g.away_team,
                    "home_team_kenpom": g.home_team_kenpom,
                    "away_team_kenpom": g.away_team_kenpom,
                    "game_time": g.game_time,
                    "officials": ", ".join(g.officials) if g.officials else "",
                    "officials_posted": g.officials_posted,
                    "crew_faa": g.crew_faa,
                    "ref_1": g.officials[0] if len(g.officials) > 0 else None,
                    "ref_2": g.officials[1] if len(g.officials) > 1 else None,
                    "ref_3": g.officials[2] if len(g.officials) > 2 else None,
                    "ref_1_faa": g.individual_faa.get(g.officials[0])
                    if len(g.officials) > 0
                    else None,
                    "ref_2_faa": g.individual_faa.get(g.officials[1])
                    if len(g.officials) > 1
                    else None,
                    "ref_3_faa": g.individual_faa.get(g.officials[2])
                    if len(g.officials) > 2
                    else None,
                }
            )
        return pd.DataFrame(rows)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "date": self.date,
                "games_with_officials": self.games_with_officials,
                "games_without_officials": self.games_without_officials,
                "games": [asdict(g) for g in self.games],
            },
            indent=2,
        )


def normalize_team_name(espn_name: str) -> str:
    """Normalize ESPN team name to KenPom format.

    Args:
        espn_name: Team name as shown on ESPN

    Returns:
        Normalized team name for KenPom matching
    """
    # Check direct mapping first
    if espn_name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[espn_name]

    # Clean up common patterns
    name = espn_name.strip()

    # Remove "State" abbreviation issues
    # e.g., "Ohio St." -> "Ohio State" (but careful with actual "St." names)
    if name.endswith(" St.") and "Saint" not in name:
        name = name[:-4] + " State"

    return name


class ESPNOfficialsScraper:
    """Scraper for ESPN game officials assignments."""

    def __init__(self, headless: bool = True):
        """Initialize the scraper.

        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self.ref_ratings: Optional[RefRatingsSnapshot] = None

    def _load_ref_ratings(self) -> None:
        """Load the latest referee ratings snapshot."""
        data_dir = Path("data")
        ref_files = sorted(data_dir.glob("kenpom_ref_ratings_*.json"), reverse=True)
        if ref_files:
            self.ref_ratings = load_ref_ratings_snapshot(ref_files[0])
            if self.ref_ratings:
                print(f"Loaded ref ratings from {ref_files[0].name}")
        else:
            print("WARNING: No referee ratings snapshot found")

    def _get_ref_faa(self, ref_name: str) -> Optional[float]:
        """Get FAA for a referee by name."""
        if not self.ref_ratings:
            return None
        return self.ref_ratings.get_ref_faa(ref_name)

    def _calculate_crew_faa(self, officials: list[str]) -> tuple[Optional[float], dict[str, float]]:
        """Calculate combined FAA for a crew.

        Returns:
            Tuple of (combined FAA, dict of individual FAAs)
        """
        individual_faa: dict[str, float] = {}
        total_faa = 0.0
        found_count = 0

        for ref in officials:
            faa = self._get_ref_faa(ref)
            if faa is not None:
                individual_faa[ref] = faa
                total_faa += faa
                found_count += 1

        if found_count == 0:
            return None, individual_faa

        return total_faa, individual_faa

    def scrape_schedule(self, page: Page, target_date: date) -> list[dict]:
        """Scrape ESPN schedule page for game IDs and teams.

        Args:
            page: Playwright page object
            target_date: Date to get schedule for

        Returns:
            List of game info dicts with game_id, home_team, away_team, game_time
        """
        date_str = target_date.strftime("%Y%m%d")
        url = f"https://www.espn.com/mens-college-basketball/schedule/_/date/{date_str}"

        print(f"Fetching schedule from: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Extract games from schedule page
        games = page.evaluate("""
            () => {
                const games = [];

                // Find all game links on the schedule page
                // ESPN schedule shows games in a table/list format
                const gameLinks = document.querySelectorAll('a[href*="/game/_/gameId/"]');

                const seen = new Set();
                gameLinks.forEach(link => {
                    const href = link.getAttribute('href');
                    const match = href.match(/gameId\\/([0-9]+)/);
                    if (match && !seen.has(match[1])) {
                        seen.add(match[1]);

                        // Try to get team names from surrounding context
                        const row = link.closest('tr') || link.closest('div[class*="Schedule"]');
                        let homeTeam = '';
                        let awayTeam = '';
                        let gameTime = '';

                        // Look for team name elements
                        if (row) {
                            const teamLinks = row.querySelectorAll('a[href*="/team/_/"]');
                            if (teamLinks.length >= 2) {
                                awayTeam = teamLinks[0].textContent.trim();
                                homeTeam = teamLinks[1].textContent.trim();
                            }

                            // Try to get game time
                            const timeEl = row.querySelector('td[data-behavior="date_time"], .date__col, [class*="time"]');
                            if (timeEl) {
                                gameTime = timeEl.textContent.trim();
                            }
                        }

                        games.push({
                            game_id: match[1],
                            home_team: homeTeam,
                            away_team: awayTeam,
                            game_time: gameTime,
                        });
                    }
                });

                return games;
            }
        """)

        print(f"Found {len(games)} games on schedule")
        return games

    def scrape_game_officials(self, page: Page, game_id: str) -> tuple[list[str], str, str, str]:
        """Scrape officials from a single game's gamecast page.

        Args:
            page: Playwright page object
            game_id: ESPN game ID

        Returns:
            Tuple of (officials list, home_team, away_team, game_time)
        """
        url = f"https://www.espn.com/mens-college-basketball/game/_/gameId/{game_id}"

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Extract officials and team info
        result = page.evaluate("""
            () => {
                const officials = [];
                let homeTeam = '';
                let awayTeam = '';
                let gameTime = '';

                // Find officiating crew section
                // Structure: <h4>Officiating Crew</h4> followed by <p>Referee:<span>Name</span></p>
                const crewHeader = Array.from(document.querySelectorAll('h4'))
                    .find(h => h.textContent.includes('Officiating Crew'));

                if (crewHeader) {
                    // Get the parent container and find referee spans
                    const container = crewHeader.parentElement;
                    if (container) {
                        const refSpans = container.querySelectorAll('span.LiUVm, span[class*="LiUVm"]');
                        refSpans.forEach(span => {
                            const name = span.textContent.trim();
                            if (name && name.length > 2) {
                                officials.push(name);
                            }
                        });
                    }
                }

                // Alternative: look for any "Referee:" labels
                if (officials.length === 0) {
                    const refLabels = Array.from(document.querySelectorAll('p'))
                        .filter(p => p.textContent.includes('Referee:'));
                    refLabels.forEach(p => {
                        const span = p.querySelector('span');
                        if (span) {
                            const name = span.textContent.trim();
                            if (name && name.length > 2) {
                                officials.push(name);
                            }
                        }
                    });
                }

                // Get team names from the page
                const teamNames = document.querySelectorAll('.ScoreCell__TeamName, [class*="TeamName"]');
                if (teamNames.length >= 2) {
                    awayTeam = teamNames[0].textContent.trim();
                    homeTeam = teamNames[1].textContent.trim();
                }

                // Alternative team name extraction
                if (!homeTeam || !awayTeam) {
                    const teamLinks = document.querySelectorAll('a[href*="/mens-college-basketball/team/_/"]');
                    const names = [];
                    teamLinks.forEach(link => {
                        const name = link.textContent.trim();
                        if (name && name.length > 1 && !names.includes(name)) {
                            names.push(name);
                        }
                    });
                    if (names.length >= 2) {
                        awayTeam = names[0];
                        homeTeam = names[1];
                    }
                }

                // Get game time
                const timeEl = document.querySelector('[class*="GameInfo__Time"], .game-time, time');
                if (timeEl) {
                    gameTime = timeEl.textContent.trim();
                }

                return {
                    officials: officials,
                    home_team: homeTeam,
                    away_team: awayTeam,
                    game_time: gameTime,
                };
            }
        """)

        return (
            result.get("officials", []),
            result.get("home_team", ""),
            result.get("away_team", ""),
            result.get("game_time", ""),
        )

    def fetch_daily_officials(
        self,
        target_date: Optional[date] = None,
        game_ids: Optional[list[str]] = None,
    ) -> DailyOfficialsSnapshot:
        """Fetch officials for all games on a given date.

        Args:
            target_date: Date to fetch (defaults to today)
            game_ids: Optional list of specific game IDs to check

        Returns:
            DailyOfficialsSnapshot with all game officials data
        """
        if target_date is None:
            target_date = date.today()

        # Load referee ratings for FAA calculation
        self._load_ref_ratings()

        games: list[GameOfficials] = []
        with_officials = 0
        without_officials = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            try:
                # Get game list from schedule if not provided
                if game_ids is None:
                    schedule = self.scrape_schedule(page, target_date)
                    game_ids = [g["game_id"] for g in schedule]
                    game_info = {g["game_id"]: g for g in schedule}
                else:
                    game_info = {}

                print(f"\nChecking {len(game_ids)} games for officials...")

                for i, game_id in enumerate(game_ids):
                    print(f"  [{i + 1}/{len(game_ids)}] Game {game_id}...", end=" ")

                    try:
                        officials, home, away, game_time = self.scrape_game_officials(page, game_id)

                        # Use schedule info if gamecast didn't have team names
                        if not home and game_id in game_info:
                            home = game_info[game_id].get("home_team", "")
                            away = game_info[game_id].get("away_team", "")
                            game_time = game_info[game_id].get("game_time", "") or game_time

                        # Normalize team names
                        home_kenpom = normalize_team_name(home) if home else None
                        away_kenpom = normalize_team_name(away) if away else None

                        # Calculate crew FAA
                        crew_faa, individual_faa = self._calculate_crew_faa(officials)

                        officials_posted = len(officials) > 0

                        if officials_posted:
                            with_officials += 1
                            print(f"✓ {len(officials)} officials: {', '.join(officials)}")
                        else:
                            without_officials += 1
                            print("✗ Officials not yet posted")

                        games.append(
                            GameOfficials(
                                game_id=game_id,
                                home_team=home,
                                away_team=away,
                                home_team_kenpom=home_kenpom,
                                away_team_kenpom=away_kenpom,
                                game_time=game_time,
                                officials=officials,
                                officials_posted=officials_posted,
                                crew_faa=crew_faa,
                                individual_faa=individual_faa,
                            )
                        )

                    except Exception as e:
                        print(f"ERROR: {e}")
                        games.append(
                            GameOfficials(
                                game_id=game_id,
                                home_team="",
                                away_team="",
                                home_team_kenpom=None,
                                away_team_kenpom=None,
                                game_time=None,
                                officials=[],
                                officials_posted=False,
                                crew_faa=None,
                                individual_faa={},
                            )
                        )
                        without_officials += 1

                    # Small delay between requests
                    page.wait_for_timeout(500)

            finally:
                browser.close()

        return DailyOfficialsSnapshot(
            date=target_date.isoformat(),
            games=games,
            games_with_officials=with_officials,
            games_without_officials=without_officials,
        )


def main():
    """CLI entry point for fetching ESPN game officials."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch game officials from ESPN and calculate crew FAA",
        prog="fetch-officials",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date to fetch (YYYY-MM-DD, defaults to today)",
    )
    parser.add_argument(
        "--game-id",
        type=str,
        help="Specific ESPN game ID to check (can be repeated)",
        action="append",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    args = parser.parse_args()

    # Parse date
    target_date = date.today()
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    scraper = ESPNOfficialsScraper(headless=args.headless)
    print(f"Fetching officials for {target_date.isoformat()}")
    print(f"Running in {'headless' if args.headless else 'headed'} mode")
    print("-" * 60)

    snapshot = scraper.fetch_daily_officials(
        target_date=target_date,
        game_ids=args.game_id,
    )

    if snapshot.games:
        # Save to JSON
        json_path = Path(f"data/espn_officials_{target_date.isoformat()}.json")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(snapshot.to_json())
        print(f"\nOfficials snapshot saved to: {json_path}")

        # Save to CSV
        csv_path = Path(f"data/espn_officials_{target_date.isoformat()}.csv")
        df = snapshot.to_dataframe()
        df.to_csv(csv_path, index=False)
        print(f"Officials CSV saved to: {csv_path}")

        # Print summary
        print(f"\n{'=' * 60}")
        print(f"ESPN GAME OFFICIALS - {target_date.isoformat()}")
        print(f"{'=' * 60}")
        print(f"Total games: {len(snapshot.games)}")
        print(f"Officials posted: {snapshot.games_with_officials}")
        print(f"Officials pending: {snapshot.games_without_officials}")

        # Show games with officials and FAA
        games_with_faa = [g for g in snapshot.games if g.crew_faa is not None]
        if games_with_faa:
            print("\nGames with Crew FAA calculated:")
            # Sort by absolute FAA for interesting matchups
            games_with_faa.sort(key=lambda g: abs(g.crew_faa or 0), reverse=True)
            for g in games_with_faa[:10]:
                faa_sign = "+" if (g.crew_faa or 0) >= 0 else ""
                print(f"  {g.away_team} @ {g.home_team}")
                print(f"    Crew: {', '.join(g.officials)}")
                print(f"    Combined FAA: {faa_sign}{g.crew_faa:.2f}")
                if g.individual_faa:
                    for ref, faa in g.individual_faa.items():
                        faa_sign = "+" if faa >= 0 else ""
                        print(f"      - {ref}: {faa_sign}{faa:.2f}")
                print()

        # Show games without officials
        games_pending = [g for g in snapshot.games if not g.officials_posted]
        if games_pending:
            print(f"\nGames awaiting official assignments ({len(games_pending)}):")
            for g in games_pending[:10]:
                print(f"  {g.away_team} @ {g.home_team} ({g.game_time or 'TBD'})")

    else:
        print("No games found for this date")


if __name__ == "__main__":
    main()
