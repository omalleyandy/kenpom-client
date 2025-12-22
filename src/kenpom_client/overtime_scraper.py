"""Scraper for overtime.ag NCAA Basketball odds.

This module provides functionality to scrape current betting odds from
overtime.ag for NCAA Men's Basketball games.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

# Load environment variables
load_dotenv()


@dataclass
class GameOdds:
    """Betting odds for a single game."""

    away_team: str
    home_team: str
    market_spread: Optional[float]  # Home team perspective (neg = favored)
    spread_odds: Optional[int]  # American odds for spread (usually -110)
    home_ml: Optional[int]  # Home team moneyline
    away_ml: Optional[int]  # Away team moneyline
    total: Optional[float]  # Over/Under total points
    over_odds: Optional[int]  # Odds for over
    under_odds: Optional[int]  # Odds for under
    game_time: Optional[str]  # Game start time
    sport: str = "NCAAB"  # NCAA Men's Basketball


class OvertimeScraper:
    """Scraper for overtime.ag betting odds."""

    def __init__(
        self,
        customer_id: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = True,
    ):
        """Initialize the scraper.

        Args:
            customer_id: overtime.ag customer ID (from env if None)
            password: overtime.ag password (from env if None)
            headless: Run browser in headless mode
        """
        self.customer_id = customer_id or os.getenv("OV_CUSTOMER_ID")
        self.password = password or os.getenv("OV_PASSWORD")
        self.headless = headless

        if not self.customer_id or not self.password:
            raise ValueError(
                "OV_CUSTOMER_ID and OV_PASSWORD required (set in .env or pass as args)"
            )

    def login(self, page: Page) -> bool:
        """Log in to overtime.ag.

        Args:
            page: Playwright page object

        Returns:
            True if login successful, False otherwise
        """
        try:
            print("Navigating to overtime.ag...")
            page.goto("https://overtime.ag/sports#/", wait_until="networkidle")
            page.wait_for_timeout(2000)

            # Find username field
            username_selectors = [
                'input[placeholder*="Customer"]',
                'input[name="customerid"]',
                'input[name="customerId"]',
                'input[type="text"]',
            ]

            username_field = None
            for selector in username_selectors:
                try:
                    field = page.locator(selector).first
                    if field.is_visible(timeout=1000):
                        username_field = field
                        break
                except Exception:
                    continue

            if not username_field:
                print("ERROR: Could not find username field")
                return False

            # Fill login form
            assert self.customer_id is not None  # Validated in __init__
            username_field.fill(self.customer_id)
            page.wait_for_timeout(500)

            password_field = page.locator('input[type="password"]').first
            assert self.password is not None  # Validated in __init__
            password_field.fill(self.password)
            page.wait_for_timeout(500)

            # Click login button
            submit_selectors = [
                'button:has-text("Login")',
                'button[type="submit"]',
                'button:has-text("Sign In")',
            ]

            for selector in submit_selectors:
                try:
                    submit = page.locator(selector).first
                    if submit.is_visible(timeout=1000):
                        submit.click()
                        break
                except Exception:
                    continue

            # Wait for login to complete
            page.wait_for_timeout(3000)
            print("Login successful")
            return True

        except Exception as e:
            print(f"Login failed: {e}")
            return False

    def navigate_to_ncaab(self, page: Page) -> bool:
        """Navigate to NCAA Basketball section.

        Args:
            page: Playwright page object

        Returns:
            True if navigation successful, False otherwise
        """
        try:
            print("Navigating to NCAA Basketball section...")

            # Click Basketball icon to expand section
            basketball_icon = page.locator("#img_Basketball")
            if basketball_icon.is_visible(timeout=2000):
                basketball_icon.click()
                page.wait_for_timeout(1000)
                print("Clicked Basketball section")

            # Click College Basketball label (use JS if not enabled)
            college_selector = "label[for='gl_Basketball_College_Basketball_G']"

            try:
                college_bball = page.locator(college_selector)
                if college_bball.is_visible(timeout=2000):
                    # Force click using JS (bypasses enabled check)
                    page.evaluate(
                        "(element) => element.click()",
                        college_bball.element_handle(),
                    )
                    page.wait_for_timeout(2000)
                    print("Navigated to College Basketball (JS click)")
                    return True
            except Exception as e:
                print(f"JS click failed: {e}")

            print("ERROR: Could not navigate to College Basketball")
            return False

        except Exception as e:
            print(f"Navigation failed: {e}")
            return False

    def _extract_from_dom(self, page: Page) -> list[dict]:
        """Extract game data directly from DOM elements.

        This is a fallback method when Angular scope extraction fails.
        Parses the page text line by line, handling multi-line game data.
        """
        return page.evaluate("""
            () => {
                const games = [];
                const allText = document.body.innerText;
                const lines = allText.split('\\n').map(l => l.trim()).filter(l => l);

                // Debug: log first 50 lines to understand format
                console.log('First 50 lines:', lines.slice(0, 50));

                let currentTime = null;
                let awayData = null;

                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];

                    // Match time pattern like "6:00 PM (EST)"
                    const timeMatch = line.match(/^(\\d{1,2}:\\d{2}\\s*(AM|PM)\\s*\\(\\w+\\))/i);
                    if (timeMatch) {
                        currentTime = timeMatch[1];
                        continue;
                    }

                    // Match team line: "813 Siena" or "814 Indiana"
                    const teamMatch = line.match(/^(\\d{3})\\s+(.+)$/);
                    if (teamMatch) {
                        const teamNum = parseInt(teamMatch[1]);
                        const teamName = teamMatch[2].trim();

                        // Look ahead for odds data in next few lines
                        // Format: spread line, ml line, total line
                        let spread = null, spreadPrice = null, ml = null, total = null, totalPrice = null;

                        // Check next lines for odds
                        for (let j = 1; j <= 5 && i + j < lines.length; j++) {
                            const nextLine = lines[i + j];

                            // Spread: "+22 -111" or "-22 -109"
                            const spreadMatch = nextLine.match(/^([+-]?[\\d½.]+)\\s+(-?\\d+)$/);
                            if (spreadMatch && !spread) {
                                spread = spreadMatch[1].replace('½', '.5');
                                spreadPrice = spreadMatch[2];
                                continue;
                            }

                            // Moneyline: "+446" or "-600" or just "-"
                            const mlMatch = nextLine.match(/^([+-]\\d+)$/);
                            if (mlMatch) {
                                ml = mlMatch[1];
                                continue;
                            }

                            // Total: "O 146 -112" or "U 146 -108"
                            const totalMatch = nextLine.match(/^([OU])\\s*([\\d½.]+)\\s*(-?\\d+)$/);
                            if (totalMatch) {
                                total = totalMatch[2].replace('½', '.5');
                                totalPrice = totalMatch[3];
                                continue;
                            }

                            // Stop if we hit another team number
                            if (nextLine.match(/^\\d{3}\\s+/)) break;
                        }

                        // Odd team numbers are away, even are home
                        const isAway = teamNum % 2 === 1;

                        if (isAway) {
                            awayData = {
                                team: teamName,
                                spread: spread,
                                spreadPrice: spreadPrice,
                                ml: ml,
                                total: total,
                                totalPrice: totalPrice,
                                time: currentTime
                            };
                        } else if (awayData) {
                            // Home team - complete the game
                            games.push({
                                away_team: awayData.team,
                                home_team: teamName,
                                spread: spread,  // Home spread
                                spread_price: spreadPrice,
                                away_ml: awayData.ml ? parseInt(awayData.ml) : null,
                                home_ml: ml ? parseInt(ml) : null,
                                total: awayData.total || total,
                                over_price: awayData.totalPrice,
                                under_price: totalPrice,
                                game_time: awayData.time || currentTime,
                            });
                            awayData = null;
                        }
                    }
                }

                console.log('Extracted games:', games);
                return games;
            }
        """)

    def scrape_games(self, page: Page) -> list[GameOdds]:
        """Scrape all NCAA Basketball games and odds.

        Args:
            page: Playwright page object

        Returns:
            List of GameOdds objects
        """
        games = []

        try:
            print("Scraping games...")

            # Wait for games to load (longer wait for Angular)
            page.wait_for_timeout(5000)

            # Try to expand College Basketball section if collapsed
            try:
                expand_btn = page.locator("#subSportArrow_College_Basketball")
                if expand_btn.is_visible(timeout=1000):
                    expand_btn.click()
                    page.wait_for_timeout(2000)
                    print("Expanded College Basketball section")
            except Exception:
                pass

            # Scroll down to ensure all games are loaded
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # Save screenshot for debugging
            screenshots_dir = Path("data/screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            screenshot_path = screenshots_dir / "overtime_ncaab_games.png"
            page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

            # Save HTML for inspection
            html_content = page.content()
            html_path = screenshots_dir / "overtime_ncaab_games.html"
            html_path.write_text(html_content, encoding="utf-8")
            print(f"HTML saved to {html_path}")

            # Extract game data from Angular scope
            # overtime.ag uses AngularJS, so data is in scope
            scope_debug = page.evaluate("""
                () => {
                    // Find all scopes and check for Leagues
                    const allScopes = [];
                    let currentScope = angular.element(document.body).scope();

                    // Traverse scope tree
                    function findLeagues(scope, path = 'root', depth = 0) {
                        if (depth > 10) return null;  // Prevent infinite loops

                        if (scope && scope.Leagues) {
                            return {
                                path: path,
                                count: scope.Leagues.length,
                                leagues: scope.Leagues.map(
                                    l => l.LeagueName || 'unnamed'
                                ),
                            };
                        }

                        // Check children
                        if (scope.$$childHead) {
                            const result = findLeagues(
                                scope.$$childHead,
                                path + '.child',
                                depth + 1
                            );
                            if (result) return result;
                        }

                        // Check siblings
                        if (scope.$$nextSibling) {
                            const result = findLeagues(
                                scope.$$nextSibling,
                                path + '.sibling',
                                depth + 1
                            );
                            if (result) return result;
                        }

                        return null;
                    }

                    const result = findLeagues(currentScope);
                    return result || {error: 'Leagues not found in scope tree'};
                }
            """)
            print(f"\nAngular scope search: {scope_debug}")

            game_data = page.evaluate("""
                () => {
                    const games = [];
                    // Try body scope first (usually has root controller)
                    let scope = angular.element(document.body).scope();

                    // Fallback to gamesAccordion
                    if (!scope || !scope.Leagues) {
                        scope = angular.element(
                            document.getElementById('gamesAccordion')
                        ).scope();
                    }

                    if (scope && scope.Leagues) {
                        scope.Leagues.forEach(league => {
                            if (league.GameLines) {
                                league.GameLines.forEach(gl => {
                                    const hasTeams = gl.Team1ID && gl.Team2ID;
                                    if (!gl.IsTitle && hasTeams) {
                                        games.push({
                                            away_team: gl.Team1ID,
                                            home_team: gl.Team2ID,
                                            spread: gl.Spread2,
                                            spread_price: gl.SpreadPrice2,
                                            away_ml: gl.MoneyLine1,
                                            home_ml: gl.MoneyLine2,
                                            total: gl.Total,
                                            over_price: gl.TotalPrice1,
                                            under_price: gl.TotalPrice2,
                                            game_time: gl.GameDateTimeString,
                                            game_num: gl.GameNum,
                                        });
                                    }
                                });
                            }
                        });
                    }
                    return games;
                }
            """)

            print(f"\nExtracted {len(game_data)} games from Angular scope")

            # If Angular extraction failed, try DOM-based extraction
            if not game_data:
                print("\nAngular extraction failed. Trying DOM-based extraction...")
                game_data = self._extract_from_dom(page)
                print(f"Extracted {len(game_data)} games from DOM")

            # Convert to GameOdds objects
            for game in game_data:
                try:
                    odds = GameOdds(
                        away_team=game["away_team"],
                        home_team=game["home_team"],
                        market_spread=float(game["spread"]) if game["spread"] else None,
                        spread_odds=int(game["spread_price"]) if game["spread_price"] else None,
                        home_ml=int(game["home_ml"]) if game["home_ml"] else None,
                        away_ml=int(game["away_ml"]) if game["away_ml"] else None,
                        total=float(game["total"]) if game["total"] else None,
                        over_odds=int(game["over_price"]) if game["over_price"] else None,
                        under_odds=int(game["under_price"]) if game["under_price"] else None,
                        game_time=game["game_time"],
                    )
                    games.append(odds)
                    print(f"  {odds.away_team} @ {odds.home_team}")
                except Exception as e:
                    print(f"  Error parsing game: {e}")
                    print(f"  Data: {game}")

            return games

        except Exception as e:
            print(f"Scraping failed: {e}")
            return games

    def fetch_ncaab_odds(self) -> pd.DataFrame:
        """Fetch all NCAA Basketball odds from overtime.ag.

        Returns:
            DataFrame with columns: away_team, home_team, market_spread,
            spread_odds, home_ml, away_ml, total, over_odds, under_odds,
            game_time
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()

            try:
                # Login
                if not self.login(page):
                    raise RuntimeError("Login failed")

                # Navigate to NCAA Basketball
                if not self.navigate_to_ncaab(page):
                    raise RuntimeError("Could not navigate to NCAA Basketball")

                # Scrape games
                games = self.scrape_games(page)

                # Convert to DataFrame
                if games:
                    df = pd.DataFrame([vars(game) for game in games])
                else:
                    # Return empty DataFrame with correct schema
                    df = pd.DataFrame(
                        columns=[
                            "away_team",
                            "home_team",
                            "market_spread",
                            "spread_odds",
                            "home_ml",
                            "away_ml",
                            "total",
                            "over_odds",
                            "under_odds",
                            "game_time",
                            "sport",
                        ]
                    )

                return df

            finally:
                browser.close()


def main():
    """CLI entry point for scraping overtime.ag odds."""
    scraper = OvertimeScraper(headless=False)  # Headed for debugging
    df = scraper.fetch_ncaab_odds()

    if not df.empty:
        output_path = Path("data/overtime_odds.csv")
        df.to_csv(output_path, index=False)
        print(f"\nScraped {len(df)} games")
        print(f"Odds exported to: {output_path}")
    else:
        print("\nNo games scraped. Check screenshots to debug.")


if __name__ == "__main__":
    main()
