"""Scraper for KenPom Home Court Advantage (HCA) data.

This module provides functionality to scrape team-specific home court advantage
data from kenpom.com/hca.php using Playwright for browser automation.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

# Load environment variables
load_dotenv()


@dataclass
class TeamHCA:
    """Home Court Advantage data for a single team."""

    team: str  # Team name as shown on KenPom
    conference: str  # Conference abbreviation
    hca: float  # Home court advantage in points
    hca_rank: int  # Rank among all teams (1 = highest HCA)
    home_em: Optional[float] = None  # Home efficiency margin (if available)
    away_em: Optional[float] = None  # Away efficiency margin (if available)
    home_record: Optional[str] = None  # Home W-L record (if available)
    away_record: Optional[str] = None  # Away W-L record (if available)


@dataclass
class HCASnapshot:
    """Snapshot of all team HCA values."""

    date: str  # Date of snapshot (YYYY-MM-DD)
    season: int  # Season year (e.g., 2025)
    national_avg_hca: float  # National average HCA
    teams: list[TeamHCA]  # All team HCA values

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        data = [asdict(t) for t in self.teams]
        df = pd.DataFrame(data)
        df["snapshot_date"] = self.date
        df["season"] = self.season
        df["national_avg_hca"] = self.national_avg_hca
        return df

    def get_team_hca(self, team_name: str) -> Optional[float]:
        """Get HCA for a specific team (case-insensitive fuzzy match).

        Args:
            team_name: Team name to search for

        Returns:
            HCA value in points, or None if not found
        """
        team_lower = team_name.lower()

        # Try exact match first
        for t in self.teams:
            if t.team.lower() == team_lower:
                return t.hca

        # Try partial match
        for t in self.teams:
            if team_lower in t.team.lower() or t.team.lower() in team_lower:
                return t.hca

        return None

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "date": self.date,
                "season": self.season,
                "national_avg_hca": self.national_avg_hca,
                "teams": [asdict(t) for t in self.teams],
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "HCASnapshot":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        teams = [TeamHCA(**t) for t in data["teams"]]
        return cls(
            date=data["date"],
            season=data["season"],
            national_avg_hca=data["national_avg_hca"],
            teams=teams,
        )


class HCAScraper:
    """Scraper for KenPom Home Court Advantage data."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = True,
    ):
        """Initialize the scraper.

        Args:
            username: KenPom username/email (from KENPOM_EMAIL env if None)
            password: KenPom password (from KENPOM_PASSWORD env if None)
            headless: Run browser in headless mode
        """
        self.username = username or os.getenv("KENPOM_EMAIL")
        self.password = password or os.getenv("KENPOM_PASSWORD")
        self.headless = headless

        if not self.username or not self.password:
            raise ValueError(
                "KENPOM_EMAIL and KENPOM_PASSWORD required (set in .env or pass as args)"
            )

    def login(self, page: Page) -> bool:
        """Log in to KenPom.

        Args:
            page: Playwright page object

        Returns:
            True if login successful, False otherwise
        """
        try:
            print("Navigating to KenPom login page...")
            page.goto("https://kenpom.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            # Check if already logged in (look for logout link or subscriber content)
            try:
                if page.locator("a:has-text('logout')").is_visible(timeout=2000):
                    print("Already logged in")
                    return True
            except Exception:
                pass

            # Navigate directly to login page
            print("Navigating to login page...")
            page.goto("https://kenpom.com/login.php", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            # Fill login form - KenPom uses 'email' and 'password' fields
            email_field = page.locator('input[name="email"]')
            if not email_field.is_visible(timeout=5000):
                print("ERROR: Could not find email field on login page")
                screenshots_dir = Path("data/screenshots")
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots_dir / "kenpom_login_failed.png"))
                return False

            assert self.username is not None
            email_field.fill(self.username)
            page.wait_for_timeout(300)

            # Find and fill password field
            password_field = page.locator('input[name="password"]')
            assert self.password is not None
            password_field.fill(self.password)
            page.wait_for_timeout(300)

            # Submit login form
            submit_button = page.locator('input[type="submit"][value="Login"]')
            if not submit_button.is_visible(timeout=2000):
                # Try alternative submit button
                submit_button = page.locator('button[type="submit"], input[type="submit"]').first

            submit_button.click()
            print("Submitted login form...")

            # Wait for redirect after login
            page.wait_for_timeout(3000)

            # Check for CAPTCHA or human verification
            captcha_selectors = [
                "iframe[src*='captcha']",
                "iframe[src*='recaptcha']",
                "#captcha",
                ".g-recaptcha",
                "[class*='captcha']",
                "text=verify you are human",
                "text=I'm not a robot",
            ]

            captcha_detected = False
            for selector in captcha_selectors:
                try:
                    if page.locator(selector).is_visible(timeout=1000):
                        captcha_detected = True
                        break
                except Exception:
                    continue

            if captcha_detected:
                if not self.headless:
                    print("\n" + "=" * 60)
                    print("CAPTCHA DETECTED!")
                    print("Please complete it in the browser window.")
                    print("=" * 60)
                    input("Press ENTER after completing the CAPTCHA...")
                    print("Continuing...")
                    page.wait_for_timeout(2000)
                else:
                    print("ERROR: CAPTCHA detected but running in headless mode")
                    print("Try running with --headed flag to complete CAPTCHA manually")
                    return False

            # Verify login success by checking URL or page content
            current_url = page.url
            if "login" not in current_url.lower():
                print("Login successful (redirected away from login page)")
                return True

            # Check for error message
            error_msg = page.locator(".error, .alert-danger, .login-error")
            if error_msg.is_visible(timeout=1000):
                print(f"Login error: {error_msg.text_content()}")
                return False

            # If we're still on login page, might have failed
            print("WARNING: May still be on login page, proceeding anyway...")
            return True

        except Exception as e:
            print(f"Login failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def scrape_hca(self, page: Page, season: int = 2025) -> Optional[HCASnapshot]:
        """Scrape HCA data from kenpom.com/hca.php.

        Args:
            page: Playwright page object
            season: Season year to scrape

        Returns:
            HCASnapshot with all team HCA data, or None on failure
        """
        try:
            print(f"Navigating to HCA page for season {season}...")
            page.goto(
                f"https://kenpom.com/hca.php?y={season}",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(3000)

            # Take screenshot for debugging
            screenshots_dir = Path("data/screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshots_dir / "kenpom_hca_page.png"))
            print(f"Screenshot saved to {screenshots_dir / 'kenpom_hca_page.png'}")

            # Extract HCA data from table using JavaScript
            hca_data = page.evaluate("""
                () => {
                    const result = {
                        teams: [],
                        national_avg: null,
                    };

                    // Find the main data table
                    const table = document.getElementById('ratings-table') ||
                                  document.querySelector('table.sortable') ||
                                  document.querySelector('table');

                    if (!table) {
                        console.log('No table found');
                        return result;
                    }

                    // Get header row to determine column indices
                    const headerRow = table.querySelector('thead tr') ||
                                      table.querySelector('tr:first-child');
                    const headers = headerRow ? Array.from(headerRow.querySelectorAll('th, td'))
                                                     .map(h => h.textContent.trim().toLowerCase()) : [];

                    console.log('Headers found:', headers);

                    // Find column indices
                    const teamIdx = headers.findIndex(h => h.includes('team') || h === '');
                    const confIdx = headers.findIndex(h => h.includes('conf'));
                    const hcaIdx = headers.findIndex(h => h.includes('hca') || h.includes('home court'));
                    const homeEmIdx = headers.findIndex(h => h.includes('home') && h.includes('em'));
                    const awayEmIdx = headers.findIndex(h => h.includes('away') && h.includes('em'));

                    console.log('Column indices:', {teamIdx, confIdx, hcaIdx, homeEmIdx, awayEmIdx});

                    // Get all data rows
                    const tbody = table.querySelector('tbody') || table;
                    const rows = Array.from(tbody.querySelectorAll('tr'));

                    let rank = 0;
                    rows.forEach((row, idx) => {
                        // Skip header rows
                        if (row.querySelector('th')) return;

                        const cells = Array.from(row.querySelectorAll('td'));
                        if (cells.length < 3) return;

                        // Try to extract team name
                        let teamName = '';
                        let conf = '';

                        // Look for team link
                        const teamLink = row.querySelector('a[href*="team.php"]');
                        if (teamLink) {
                            teamName = teamLink.textContent.trim();
                        } else if (cells[0]) {
                            teamName = cells[0].textContent.trim();
                        }

                        // Skip if no team name
                        if (!teamName) return;

                        // Get conference
                        if (confIdx >= 0 && cells[confIdx]) {
                            conf = cells[confIdx].textContent.trim();
                        }

                        // Get HCA value (look for the numeric column)
                        let hca = null;
                        for (let i = 0; i < cells.length; i++) {
                            const text = cells[i].textContent.trim();
                            // HCA values are typically in the 2-7 range
                            const num = parseFloat(text);
                            if (!isNaN(num) && num > 0 && num < 15 && i !== 0) {
                                // This is likely the HCA value
                                hca = num;
                                break;
                            }
                        }

                        if (hca !== null) {
                            rank++;
                            result.teams.push({
                                team: teamName,
                                conference: conf,
                                hca: hca,
                                hca_rank: rank,
                            });
                        }
                    });

                    // Calculate national average
                    if (result.teams.length > 0) {
                        const sum = result.teams.reduce((acc, t) => acc + t.hca, 0);
                        result.national_avg = sum / result.teams.length;
                    }

                    console.log('Extracted', result.teams.length, 'teams');
                    return result;
                }
            """)

            print(f"Extracted {len(hca_data['teams'])} teams from HCA table")

            if not hca_data["teams"]:
                # Try alternative extraction using simpler DOM parsing
                print("Primary extraction failed, trying alternative method...")
                hca_data = self._extract_hca_alternative(page)

            if not hca_data["teams"]:
                print("ERROR: Could not extract HCA data")
                return None

            # Convert to TeamHCA objects
            teams = [
                TeamHCA(
                    team=t["team"],
                    conference=t.get("conference", ""),
                    hca=t["hca"],
                    hca_rank=t.get("hca_rank", 0),
                    home_em=t.get("home_em"),
                    away_em=t.get("away_em"),
                    home_record=t.get("home_record"),
                    away_record=t.get("away_record"),
                )
                for t in hca_data["teams"]
            ]

            return HCASnapshot(
                date=date.today().isoformat(),
                season=season,
                national_avg_hca=hca_data.get("national_avg") or 3.5,
                teams=teams,
            )

        except Exception as e:
            print(f"HCA scraping failed: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _extract_hca_alternative(self, page: Page) -> dict:
        """Alternative HCA extraction method using simpler DOM parsing."""
        return page.evaluate("""
            () => {
                const result = {
                    teams: [],
                    national_avg: null,
                };

                // Find all table rows
                const allRows = document.querySelectorAll('tr');

                let rank = 0;
                allRows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 2) return;

                    // Look for team name in first cell or anchor
                    const firstCell = cells[0];
                    const anchor = firstCell.querySelector('a');
                    const teamName = anchor ? anchor.textContent.trim() : firstCell.textContent.trim();

                    if (!teamName || teamName.length < 2) return;

                    // Look for numeric HCA value
                    for (let i = 1; i < cells.length; i++) {
                        const text = cells[i].textContent.trim();
                        const num = parseFloat(text);
                        // HCA values typically 1.5 - 7.0
                        if (!isNaN(num) && num > 1 && num < 8) {
                            rank++;
                            result.teams.push({
                                team: teamName,
                                conference: '',
                                hca: num,
                                hca_rank: rank,
                            });
                            break;
                        }
                    }
                });

                if (result.teams.length > 0) {
                    const sum = result.teams.reduce((acc, t) => acc + t.hca, 0);
                    result.national_avg = sum / result.teams.length;
                }

                return result;
            }
        """)

    def fetch_hca_data(self, season: int = 2025) -> Optional[HCASnapshot]:
        """Fetch HCA data for a season.

        Args:
            season: Season year (e.g., 2025)

        Returns:
            HCASnapshot with all team HCA data, or None on failure
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()

            try:
                # Login
                if not self.login(page):
                    raise RuntimeError("Login failed")

                # Scrape HCA data
                return self.scrape_hca(page, season)

            finally:
                browser.close()


def load_hca_snapshot(snapshot_path: Path) -> Optional[HCASnapshot]:
    """Load HCA snapshot from JSON file.

    Args:
        snapshot_path: Path to JSON snapshot file

    Returns:
        HCASnapshot or None if file doesn't exist
    """
    if not snapshot_path.exists():
        return None

    try:
        return HCASnapshot.from_json(snapshot_path.read_text())
    except Exception as e:
        print(f"Error loading HCA snapshot: {e}")
        return None


def get_team_hca(team_name: str, snapshot: Optional[HCASnapshot] = None) -> float:
    """Get home court advantage for a team.

    Falls back to national average if team not found, or 3.5 if no snapshot.

    Args:
        team_name: Team name to look up
        snapshot: HCA snapshot (loads latest if None)

    Returns:
        HCA value in points
    """
    if snapshot is None:
        # Try to load latest snapshot
        data_dir = Path("data")
        hca_files = sorted(data_dir.glob("kenpom_hca_*.json"), reverse=True)
        if hca_files:
            snapshot = load_hca_snapshot(hca_files[0])

    if snapshot is None:
        return 3.5  # Default fallback

    team_hca = snapshot.get_team_hca(team_name)
    if team_hca is not None:
        return team_hca

    # Fall back to national average
    return snapshot.national_avg_hca


def main():
    """CLI entry point for scraping KenPom HCA data."""
    scraper = HCAScraper(headless=True)
    snapshot = scraper.fetch_hca_data(season=2025)

    if snapshot:
        # Save to JSON
        today = date.today().isoformat()
        json_path = Path(f"data/kenpom_hca_{today}.json")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(snapshot.to_json())
        print(f"HCA snapshot saved to: {json_path}")

        # Also save as CSV
        csv_path = Path(f"data/kenpom_hca_{today}.csv")
        df = snapshot.to_dataframe()
        df.to_csv(csv_path, index=False)
        print(f"HCA CSV saved to: {csv_path}")

        # Print summary
        print(f"\n{'=' * 50}")
        print(f"KENPOM HOME COURT ADVANTAGE - {today}")
        print(f"{'=' * 50}")
        print(f"Teams scraped: {len(snapshot.teams)}")
        print(f"National average HCA: {snapshot.national_avg_hca:.2f}")

        # Top 10 HCAs
        sorted_teams = sorted(snapshot.teams, key=lambda t: t.hca, reverse=True)
        print("\nTop 10 Home Court Advantages:")
        for i, team in enumerate(sorted_teams[:10], 1):
            print(f"  {i:2}. {team.team}: {team.hca:.2f}")

        # Bottom 10 HCAs
        print("\nLowest 10 Home Court Advantages:")
        for i, team in enumerate(sorted_teams[-10:], 1):
            print(f"  {i:2}. {team.team}: {team.hca:.2f}")

    else:
        print("ERROR: Failed to scrape HCA data")


if __name__ == "__main__":
    main()
