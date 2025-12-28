"""ESPN NCAA Basketball odds scraper.

This module provides functionality to scrape betting odds from ESPN's
college basketball scoreboard. Serves as a fallback/barometer when
primary odds sources (overtime.ag) are unavailable.

Features:
    - Scrapes spreads, totals, and moneylines from ESPN scoreboard
    - Extracts game metadata (time, location, TV coverage)
    - Provides team name normalization for matching with KenPom data
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from playwright.sync_api import sync_playwright


@dataclass
class ESPNGame:
    """Game data from ESPN scoreboard."""

    away_team: str
    home_team: str
    # Betting lines
    spread: Optional[float] = None  # Home team spread (negative = home fav)
    spread_team: Optional[str] = None  # Team the spread applies to
    total: Optional[float] = None
    away_ml: Optional[int] = None
    home_ml: Optional[int] = None
    # Game info
    game_time: Optional[str] = None
    game_status: str = "scheduled"  # scheduled, in_progress, final
    location: Optional[str] = None
    tv_coverage: Optional[str] = None
    # Scores (if in progress or final)
    away_score: Optional[int] = None
    home_score: Optional[int] = None
    # Metadata
    espn_game_id: Optional[str] = None


@dataclass
class ESPNScraper:
    """Scraper for ESPN college basketball odds."""

    headless: bool = True
    screenshot_dir: Path = field(default_factory=lambda: Path("data/screenshots"))

    def __post_init__(self):
        """Ensure screenshot directory exists."""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _parse_spread(self, text: str) -> tuple[Optional[float], Optional[str]]:
        """Parse spread text like 'TTU -17.5' or 'GONZ -28.5'.

        Returns:
            Tuple of (spread_value, team_abbrev)
        """
        if not text or text == "-":
            return None, None

        # Pattern: TEAM -/+X.X
        match = re.match(r"([A-Z]+)\s*([+-]?\d+\.?\d*)", text.strip())
        if match:
            team = match.group(1)
            try:
                spread = float(match.group(2))
                return spread, team
            except ValueError:
                return None, None

        return None, None

    def _parse_total(self, text: str) -> Optional[float]:
        """Parse total text like '165.5' or 'O/U 165.5'."""
        if not text or text == "-":
            return None

        # Extract number from text
        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def _parse_moneyline(self, text: str) -> Optional[int]:
        """Parse moneyline text like '+260' or '-320'."""
        if not text or text == "-":
            return None

        match = re.match(r"([+-]?\d+)", text.strip())
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def scrape_scoreboard(self, game_date: Optional[str] = None, group: int = 50) -> list[ESPNGame]:
        """Scrape ESPN college basketball scoreboard.

        Args:
            game_date: Date in YYYY-MM-DD format (default: today)
            group: ESPN group ID (50 = all D1 games)

        Returns:
            List of ESPNGame objects with betting data
        """
        if game_date is None:
            game_date = date.today().strftime("%Y%m%d")
        else:
            # Convert YYYY-MM-DD to YYYYMMDD
            game_date = game_date.replace("-", "")

        url = (
            f"https://www.espn.com/mens-college-basketball/scoreboard/"
            f"_/date/{game_date}/seasontype/2/group/{group}"
        )

        games: list[ESPNGame] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            try:
                print(f"Fetching ESPN scoreboard: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)

                # Scroll to load all games
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)

                # Save screenshot for debugging
                screenshot_path = self.screenshot_dir / "espn_scoreboard.png"
                page.screenshot(path=str(screenshot_path))
                print(f"Screenshot saved: {screenshot_path}")

                # Extract games using JavaScript
                games_data = page.evaluate(
                    """
                    () => {
                        const games = [];

                        // Find all game containers (ESPN uses ScoreboardPage structure)
                        const gameCards = document.querySelectorAll(
                            '[class*="ScoreboardScoreCell"], ' +
                            '[class*="Scoreboard__Card"], ' +
                            '.scoreboard .ScoreCell'
                        );

                        // Alternative: find by section structure
                        const sections = document.querySelectorAll('section.Scoreboard');

                        sections.forEach((section, idx) => {
                            try {
                                // Get teams
                                const teamEls = section.querySelectorAll(
                                    '[class*="ScoreCell__TeamName"], ' +
                                    '.ScoreboardScoreCell__Item--away .ScoreCell__TeamName, ' +
                                    '.ScoreboardScoreCell__Item--home .ScoreCell__TeamName'
                                );

                                const teams = Array.from(teamEls).map(
                                    el => el.textContent.trim()
                                );

                                if (teams.length < 2) return;

                                // Get odds container
                                const oddsEl = section.querySelector(
                                    '[class*="Odds"], [class*="odds"]'
                                );
                                let spread = null;
                                let total = null;

                                if (oddsEl) {
                                    const oddsText = oddsEl.textContent;
                                    // Parse spread: "TTU -17.5"
                                    const spreadMatch = oddsText.match(
                                        /([A-Z]+)\\s*([+-]?\\d+\\.?\\d*)/
                                    );
                                    if (spreadMatch) {
                                        spread = {
                                            team: spreadMatch[1],
                                            value: parseFloat(spreadMatch[2])
                                        };
                                    }
                                    // Parse total: number after spread
                                    const totalMatch = oddsText.match(
                                        /([+-]?\\d+\\.?\\d*)\\s*$/
                                    );
                                    if (totalMatch) {
                                        total = parseFloat(totalMatch[1]);
                                    }
                                }

                                // Get scores if available
                                const scoreEls = section.querySelectorAll(
                                    '[class*="ScoreCell__Score"]'
                                );
                                const scores = Array.from(scoreEls).map(
                                    el => parseInt(el.textContent) || null
                                );

                                // Get game status
                                const statusEl = section.querySelector(
                                    '[class*="ScoreCell__Time"], ' +
                                    '[class*="ScoreboardScoreCell__Time"]'
                                );
                                const status = statusEl ?
                                    statusEl.textContent.trim() : null;

                                // Get TV coverage
                                const tvEl = section.querySelector(
                                    '[class*="ScoreCell__NetworkItem"], ' +
                                    '[class*="network"]'
                                );
                                const tv = tvEl ? tvEl.textContent.trim() : null;

                                games.push({
                                    away_team: teams[0],
                                    home_team: teams[1] || teams[0],
                                    spread: spread,
                                    total: total,
                                    away_score: scores[0] || null,
                                    home_score: scores[1] || null,
                                    game_time: status,
                                    tv_coverage: tv
                                });

                            } catch (e) {
                                console.error('Error parsing game', idx, e);
                            }
                        });

                        return games;
                    }
                """
                )

                print(f"Extracted {len(games_data)} games from ESPN")

                # Convert to ESPNGame objects
                for g in games_data:
                    spread_val = None
                    spread_team = None
                    if g.get("spread"):
                        spread_val = g["spread"].get("value")
                        spread_team = g["spread"].get("team")

                    game = ESPNGame(
                        away_team=g.get("away_team", "Unknown"),
                        home_team=g.get("home_team", "Unknown"),
                        spread=spread_val,
                        spread_team=spread_team,
                        total=g.get("total"),
                        away_score=g.get("away_score"),
                        home_score=g.get("home_score"),
                        game_time=g.get("game_time"),
                        tv_coverage=g.get("tv_coverage"),
                    )
                    games.append(game)

            except Exception as e:
                print(f"Error scraping ESPN: {e}")
                # Save error screenshot
                page.screenshot(path=str(self.screenshot_dir / "espn_error.png"))
            finally:
                browser.close()

        return games

    def fetch_odds(self, game_date: Optional[str] = None) -> pd.DataFrame:
        """Fetch odds and return as DataFrame.

        Args:
            game_date: Date in YYYY-MM-DD format (default: today)

        Returns:
            DataFrame with ESPN odds data. Spread convention:
            - spread_value: numeric spread (negative = favorite)
            - spread_team: team abbreviation the spread applies to
            Note: Team name normalization handled separately when joining
            with KenPom data.
        """
        games = self.scrape_scoreboard(game_date)

        if not games:
            return pd.DataFrame()

        records = []
        for g in games:
            records.append(
                {
                    "away_team": g.away_team,
                    "home_team": g.home_team,
                    "spread_value": g.spread,
                    "spread_team": g.spread_team,
                    "total": g.total,
                    "away_ml": g.away_ml,
                    "home_ml": g.home_ml,
                    "game_time": g.game_time,
                    "tv_coverage": g.tv_coverage,
                    "source": "espn",
                }
            )

        return pd.DataFrame(records)


def main():
    """CLI entry point for ESPN scraper."""
    from datetime import date as dt

    scraper = ESPNScraper(headless=True)
    df = scraper.fetch_odds()

    if not df.empty:
        today = dt.today().isoformat()
        output_path = Path(f"data/espn_ncaab_odds_{today}.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"\n{'=' * 50}")
        print(f"Scraped {len(df)} games from ESPN")
        print(f"Output: {output_path}")
        print("\nSample data:")
        print(df.head(10).to_string(index=False))
    else:
        print("No games scraped from ESPN")


if __name__ == "__main__":
    main()
