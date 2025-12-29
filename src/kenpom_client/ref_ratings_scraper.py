"""Scraper for KenPom Referee Ratings (FAA - Fouls Above Average) data.

This module provides functionality to scrape referee ratings from kenpom.com/officials.php
using Playwright for browser automation.

FAA (Fouls Above Average) measures how individual officials deviate from average
foul-calling tendencies. A positive FAA means the referee calls more fouls than average,
while a negative FAA means fewer fouls.

Reference: https://kenpom.substack.com/p/a-path-to-slightly-more-consistent
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
class RefRating:
    """Rating data for a single referee."""

    name: str  # Referee name
    faa: float  # Fouls Above Average (positive = more fouls, negative = fewer)
    rank: int  # Rank among all referees (1 = highest FAA / most fouls)
    games: Optional[int] = None  # Number of games officiated this season
    rating: Optional[float] = None  # KenPom official rating
    conference: Optional[str] = None  # Primary conference association (if available)


@dataclass
class RefRatingsSnapshot:
    """Snapshot of all referee FAA ratings."""

    date: str  # Date of snapshot (YYYY-MM-DD)
    season: int  # Season year (e.g., 2025)
    avg_faa: float  # Average FAA (should be ~0 by definition)
    refs: list[RefRating]  # All referee ratings

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        data = [asdict(r) for r in self.refs]
        df = pd.DataFrame(data)
        df["snapshot_date"] = self.date
        df["season"] = self.season
        return df

    def get_ref_faa(self, ref_name: str) -> Optional[float]:
        """Get FAA for a specific referee (case-insensitive fuzzy match).

        Args:
            ref_name: Referee name to search for

        Returns:
            FAA value, or None if not found
        """
        ref_lower = ref_name.lower()

        # Try exact match first
        for r in self.refs:
            if r.name.lower() == ref_lower:
                return r.faa

        # Try partial match (last name)
        for r in self.refs:
            if ref_lower in r.name.lower() or r.name.lower() in ref_lower:
                return r.faa

        return None

    def get_crew_faa(self, ref_names: list[str]) -> float:
        """Get combined FAA for a crew of referees.

        Args:
            ref_names: List of referee names

        Returns:
            Sum of FAA values for the crew (0.0 if none found)
        """
        total = 0.0
        for name in ref_names:
            faa = self.get_ref_faa(name)
            if faa is not None:
                total += faa
        return total

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "date": self.date,
                "season": self.season,
                "avg_faa": self.avg_faa,
                "refs": [asdict(r) for r in self.refs],
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "RefRatingsSnapshot":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        refs = [RefRating(**r) for r in data["refs"]]
        return cls(
            date=data["date"],
            season=data["season"],
            avg_faa=data["avg_faa"],
            refs=refs,
        )


class RefRatingsScraper:
    """Scraper for KenPom Referee Ratings data."""

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

    def _handle_cloudflare(self, page: Page) -> None:
        """Handle Cloudflare verification challenge.

        Waits for automatic verification or prompts user if stuck.
        """
        cloudflare_indicators = [
            "text=Verifying you are human",
            "text=Verify you are human",
            "text=Checking your browser",
            "text=needs to review the security",
            "text=Just a moment",
            "text=completing the action below",
            "#challenge-running",
            "#challenge-stage",
            "iframe[src*='challenges.cloudflare.com']",
            "iframe[src*='turnstile']",
        ]

        is_cloudflare = False
        for selector in cloudflare_indicators:
            try:
                if page.locator(selector).is_visible(timeout=1000):
                    is_cloudflare = True
                    break
            except Exception:
                continue

        if not is_cloudflare:
            return

        print("\n" + "=" * 60)
        print("CLOUDFLARE VERIFICATION DETECTED")
        print("=" * 60)
        print("Waiting for automatic verification...")

        # Wait up to 10 seconds for automatic verification
        for i in range(10):
            page.wait_for_timeout(1000)

            # Check if a clickable checkbox appeared (Turnstile)
            turnstile_selectors = [
                "iframe[src*='challenges.cloudflare.com']",
                "iframe[src*='turnstile']",
                "text=completing the action below",
            ]

            checkbox_appeared = False
            for selector in turnstile_selectors:
                try:
                    if page.locator(selector).is_visible(timeout=500):
                        checkbox_appeared = True
                        break
                except Exception:
                    continue

            if checkbox_appeared and not self.headless:
                print("\n" + "=" * 60)
                print("CLOUDFLARE CHECKBOX DETECTED")
                print("=" * 60)
                print("Click the 'Verify you are human' checkbox in the browser.")
                print("DO NOT close the browser!")
                print("=" * 60)
                input("\nPress ENTER after clicking the checkbox...")
                page.wait_for_timeout(3000)

                still_verifying = False
                for selector in cloudflare_indicators:
                    try:
                        if page.locator(selector).is_visible(timeout=1000):
                            still_verifying = True
                            break
                    except Exception:
                        continue

                if not still_verifying:
                    print("Cloudflare verification completed!")
                    return
                continue

            still_verifying = False
            for selector in cloudflare_indicators:
                try:
                    if page.locator(selector).is_visible(timeout=500):
                        still_verifying = True
                        break
                except Exception:
                    continue

            if not still_verifying:
                print("Cloudflare verification completed!")
                page.wait_for_timeout(2000)
                return

            if i == 5:
                print("Still waiting...")

        # If still stuck, try refreshing
        print("Verification stuck, trying page refresh...")
        page.reload(wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

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

            # Handle Cloudflare verification if present
            self._handle_cloudflare(page)

            # Check if already logged in
            try:
                if page.locator("a:has-text('Logout')").is_visible(timeout=2000):
                    print("Already logged in")
                    return True
            except Exception:
                pass

            print("Looking for login form on main page...")

            screenshots_dir = Path("data/screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)

            # Try multiple selectors for email field
            email_selectors = [
                'input[name="email"]',
                'input[type="email"]',
                'input[placeholder="E-mail"]',
                "input#email",
                'input[placeholder*="email" i]',
            ]

            email_field = None
            for selector in email_selectors:
                try:
                    field = page.locator(selector)
                    if field.is_visible(timeout=2000):
                        email_field = field
                        print(f"Found email field with selector: {selector}")
                        break
                except Exception:
                    continue

            if not email_field:
                print("Could not find email field.")
                page.screenshot(path=str(screenshots_dir / "ref_ratings_login_failed.png"))

                if not self.headless:
                    print("\n" + "=" * 60)
                    print("LOGIN FORM NOT FOUND")
                    print("=" * 60)
                    print("Please log in manually in the browser window.")
                    print("DO NOT close the browser!")
                    print("=" * 60)
                    input("\nPress ENTER after you are logged in...")
                    page.wait_for_timeout(3000)

                    try:
                        if page.locator("a:has-text('Logout')").is_visible(timeout=3000):
                            print("Manual login successful!")
                            return True
                    except Exception:
                        pass

                return False

            assert self.username is not None
            email_field.fill(self.username)
            page.wait_for_timeout(300)

            password_field = page.locator('input[name="password"], input[type="password"]').first
            assert self.password is not None
            password_field.fill(self.password)
            page.wait_for_timeout(300)

            submit_button = page.locator('input[type="submit"][value="Login!"]')
            if not submit_button.is_visible(timeout=2000):
                submit_button = page.locator('input[type="submit"], button[type="submit"]').first

            submit_button.click()
            print("Submitted login form...")

            page.wait_for_timeout(3000)

            # Verify login success
            try:
                if page.locator("a:has-text('Logout')").is_visible(timeout=3000):
                    print("Login successful")
                    return True
            except Exception:
                pass

            print("WARNING: May still be on login page, proceeding anyway...")
            return True

        except Exception as e:
            print(f"Login failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def scrape_ref_ratings(self, page: Page, season: int = 2025) -> Optional[RefRatingsSnapshot]:
        """Scrape referee ratings from kenpom.com/officials.php.

        Args:
            page: Playwright page object
            season: Season year to scrape

        Returns:
            RefRatingsSnapshot with all referee ratings, or None on failure
        """
        try:
            print(f"Navigating to Ref Ratings page for season {season}...")

            # Try menu navigation first (Miscellany menu -> Ref Ratings)
            try:
                print("Attempting menu navigation to Ref Ratings...")
                misc_menu = page.locator('a:has-text("Miscellany")')
                if misc_menu.is_visible(timeout=3000):
                    misc_menu.hover()
                    page.wait_for_timeout(500)

                    ref_link = page.locator('a:has-text("Ref Ratings")')
                    if ref_link.is_visible(timeout=2000):
                        ref_link.click()
                        page.wait_for_timeout(3000)
                        print("Successfully navigated via Miscellany menu")
                    else:
                        raise Exception("Ref Ratings link not visible in menu")
                else:
                    raise Exception("Miscellany menu not visible")
            except Exception as e:
                print(f"Menu navigation failed ({e}), using direct URL...")
                page.goto(
                    f"https://kenpom.com/officials.php?y={season}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                page.wait_for_timeout(3000)

            # Take screenshot for debugging
            screenshots_dir = Path("data/screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshots_dir / "kenpom_ref_ratings_page.png"))
            print(f"Screenshot saved to {screenshots_dir / 'kenpom_ref_ratings_page.png'}")

            # Scroll to load all referees
            print("Scrolling to load all referees...")
            prev_count = 0
            for scroll_attempt in range(10):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(500)

                current_count = page.evaluate("() => document.querySelectorAll('table tr').length")

                if current_count == prev_count and scroll_attempt > 2:
                    print(f"All referees loaded ({current_count} rows)")
                    break
                prev_count = current_count

            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # Extract referee data from table
            # Table structure from officials.php:
            # | Rank | Name + FAA subscript | Rating | Gms | Last Game |
            # FAA is shown as subscript text after the name (e.g., "Kipp Kissinger -0.4")
            ref_data = page.evaluate("""
                () => {
                    const result = {
                        refs: [],
                        avg_faa: 0,
                    };

                    // Find the main data table (the one with "Officials Rankings" data)
                    const tables = document.querySelectorAll('table');
                    console.log('Found', tables.length, 'tables');

                    // Find table with referee data - look for Rating/Gms headers
                    let table = null;
                    for (const t of tables) {
                        const headerText = t.textContent.toLowerCase();
                        if (headerText.includes('rating') && headerText.includes('gms')) {
                            table = t;
                            break;
                        }
                    }

                    if (!table) {
                        // Fallback to first table with multiple rows
                        for (const t of tables) {
                            if (t.querySelectorAll('tr').length > 5) {
                                table = t;
                                break;
                            }
                        }
                    }

                    if (!table) {
                        console.log('No table found');
                        return result;
                    }

                    // Table structure: | Rank | Name + FAA subscript | Rating | Gms | Last Game |
                    // The FAA is embedded in the name cell as subscript text (e.g., "Kipp Kissinger -0.4")

                    const allRows = table.querySelectorAll('tr');
                    console.log('Total rows:', allRows.length);

                    let faaSum = 0;

                    allRows.forEach((row, idx) => {
                        // Skip header rows
                        if (row.querySelector('th')) return;

                        const cells = Array.from(row.querySelectorAll('td'));
                        // Need at least: rank, name+faa, rating, gms
                        if (cells.length < 4) return;

                        // Cell 0: Rank number (we'll use our own counter)
                        // Cell 1: Name cell with FAA as subscript
                        // Cell 2: Rating
                        // Cell 3: Gms (games count)

                        const nameCell = cells[1];
                        if (!nameCell) return;

                        // Get the referee name from the anchor tag
                        const nameLink = nameCell.querySelector('a');
                        if (!nameLink) return;
                        const name = nameLink.textContent.trim();
                        if (!name || name.length < 2) return;

                        // Get FAA from the full cell text (includes subscript)
                        // Full text is like "Kipp Kissinger -0.4" or "Paul Szelc +1.8"
                        const fullText = nameCell.textContent.trim();

                        // Extract FAA: it's the signed number at the end after the name
                        // Pattern: name followed by space and signed decimal like " -0.4" or " +1.8"
                        const faaMatch = fullText.match(/([+-]?\\d+\\.\\d+)\\s*$/);
                        if (!faaMatch) {
                            console.log('No FAA found in:', fullText);
                            return;
                        }
                        const faa = parseFloat(faaMatch[1]);
                        if (isNaN(faa)) return;

                        // Get Rating from cell 2
                        const ratingText = cells[2]?.textContent.trim();
                        const rating = parseFloat(ratingText);

                        // Get Games from cell 3
                        const gamesText = cells[3]?.textContent.trim();
                        const games = parseInt(gamesText, 10);

                        faaSum += faa;
                        result.refs.push({
                            name: name,
                            faa: faa,
                            rank: result.refs.length + 1,
                            games: isNaN(games) ? null : games,
                            rating: isNaN(rating) ? null : rating,
                            conference: null,
                        });
                    });

                    // Calculate average FAA
                    if (result.refs.length > 0) {
                        result.avg_faa = faaSum / result.refs.length;
                    }

                    // Sort by FAA descending (highest FAA = most fouls)
                    result.refs.sort((a, b) => b.faa - a.faa);
                    // Re-rank after sorting
                    result.refs.forEach((r, idx) => { r.rank = idx + 1; });

                    console.log('Extracted', result.refs.length, 'referees');
                    return result;
                }
            """)

            print(f"Extracted {len(ref_data['refs'])} referees from table")

            if not ref_data["refs"]:
                print("Primary extraction failed, trying alternative method...")
                ref_data = self._extract_refs_alternative(page)

            if not ref_data["refs"]:
                print("ERROR: Could not extract referee data")
                return None

            # Convert to RefRating objects
            refs = [
                RefRating(
                    name=r["name"],
                    faa=r["faa"],
                    rank=r["rank"],
                    games=r.get("games"),
                    rating=r.get("rating"),
                    conference=r.get("conference"),
                )
                for r in ref_data["refs"]
            ]

            return RefRatingsSnapshot(
                date=date.today().isoformat(),
                season=season,
                avg_faa=ref_data.get("avg_faa", 0.0),
                refs=refs,
            )

        except Exception as e:
            print(f"Referee ratings scraping failed: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _extract_refs_alternative(self, page: Page) -> dict:
        """Alternative extraction method using simpler DOM parsing."""
        return page.evaluate("""
            () => {
                const result = {
                    refs: [],
                    avg_faa: 0,
                };

                const allRows = document.querySelectorAll('tr');
                let faaSum = 0;

                allRows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    // Need at least: rank, name+faa, rating, gms
                    if (cells.length < 4) return;

                    // Cell 1 has name + FAA subscript
                    const nameCell = cells[1];
                    if (!nameCell) return;

                    const nameLink = nameCell.querySelector('a');
                    if (!nameLink) return;
                    const name = nameLink.textContent.trim();
                    if (!name || name.length < 2) return;

                    // Extract FAA from full cell text
                    const fullText = nameCell.textContent.trim();
                    const faaMatch = fullText.match(/([+-]?\\d+\\.\\d+)\\s*$/);
                    if (!faaMatch) return;

                    const faa = parseFloat(faaMatch[1]);
                    if (isNaN(faa)) return;

                    // Get Rating from cell 2
                    const rating = parseFloat(cells[2]?.textContent.trim());

                    // Get Games from cell 3
                    const games = parseInt(cells[3]?.textContent.trim(), 10);

                    faaSum += faa;
                    result.refs.push({
                        name: name,
                        faa: faa,
                        rank: result.refs.length + 1,
                        games: isNaN(games) ? null : games,
                        rating: isNaN(rating) ? null : rating,
                        conference: null,
                    });
                });

                if (result.refs.length > 0) {
                    result.avg_faa = faaSum / result.refs.length;
                    // Sort by FAA descending
                    result.refs.sort((a, b) => b.faa - a.faa);
                    result.refs.forEach((r, idx) => { r.rank = idx + 1; });
                }

                return result;
            }
        """)

    def fetch_ref_ratings(self, season: int = 2025) -> Optional[RefRatingsSnapshot]:
        """Fetch referee ratings for a season.

        Args:
            season: Season year (e.g., 2025)

        Returns:
            RefRatingsSnapshot with all referee ratings, or None on failure
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = context.new_page()

            try:
                if not self.login(page):
                    raise RuntimeError("Login failed")

                return self.scrape_ref_ratings(page, season)

            finally:
                browser.close()


def load_ref_ratings_snapshot(snapshot_path: Path) -> Optional[RefRatingsSnapshot]:
    """Load referee ratings snapshot from JSON file.

    Args:
        snapshot_path: Path to JSON snapshot file

    Returns:
        RefRatingsSnapshot or None if file doesn't exist
    """
    if not snapshot_path.exists():
        return None

    try:
        return RefRatingsSnapshot.from_json(snapshot_path.read_text())
    except Exception as e:
        print(f"Error loading referee ratings snapshot: {e}")
        return None


def get_ref_faa(ref_name: str, snapshot: Optional[RefRatingsSnapshot] = None) -> Optional[float]:
    """Get FAA for a referee.

    Args:
        ref_name: Referee name to look up
        snapshot: Referee ratings snapshot (loads latest if None)

    Returns:
        FAA value, or None if not found
    """
    if snapshot is None:
        data_dir = Path("data")
        ref_files = sorted(data_dir.glob("kenpom_ref_ratings_*.json"), reverse=True)
        if ref_files:
            snapshot = load_ref_ratings_snapshot(ref_files[0])

    if snapshot is None:
        return None

    return snapshot.get_ref_faa(ref_name)


def get_crew_faa(ref_names: list[str], snapshot: Optional[RefRatingsSnapshot] = None) -> float:
    """Get combined FAA for a crew of referees.

    Args:
        ref_names: List of referee names
        snapshot: Referee ratings snapshot (loads latest if None)

    Returns:
        Sum of FAA values for the crew (0.0 if no snapshot)
    """
    if snapshot is None:
        data_dir = Path("data")
        ref_files = sorted(data_dir.glob("kenpom_ref_ratings_*.json"), reverse=True)
        if ref_files:
            snapshot = load_ref_ratings_snapshot(ref_files[0])

    if snapshot is None:
        return 0.0

    return snapshot.get_crew_faa(ref_names)


def main():
    """CLI entry point for scraping KenPom referee ratings."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape Referee Ratings (FAA) from KenPom",
        prog="fetch-refs",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (CAPTCHA cannot be completed)",
    )
    parser.add_argument(
        "--y",
        type=int,
        default=2025,
        help="Season year (default: 2025)",
    )
    args = parser.parse_args()

    scraper = RefRatingsScraper(headless=args.headless)
    print(f"Running in {'headless' if args.headless else 'headed'} mode")
    print("If CAPTCHA appears, complete it in the browser window")
    print("-" * 50)

    snapshot = scraper.fetch_ref_ratings(season=args.y)

    if snapshot:
        # Save to JSON
        today = date.today().isoformat()
        json_path = Path(f"data/kenpom_ref_ratings_{today}.json")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(snapshot.to_json())
        print(f"Referee ratings snapshot saved to: {json_path}")

        # Also save as CSV
        csv_path = Path(f"data/kenpom_ref_ratings_{today}.csv")
        df = snapshot.to_dataframe()
        df.to_csv(csv_path, index=False)
        print(f"Referee ratings CSV saved to: {csv_path}")

        # Print summary
        print(f"\n{'=' * 60}")
        print(f"KENPOM REFEREE RATINGS (FAA) - {today}")
        print(f"{'=' * 60}")
        print(f"Referees scraped: {len(snapshot.refs)}")
        print(f"Average FAA: {snapshot.avg_faa:.3f}")
        print()
        print("FAA = Fouls Above Average")
        print("  Positive FAA = calls more fouls than average")
        print("  Negative FAA = calls fewer fouls than average")

        # Top 10 (most fouls)
        print("\nTop 10 (Most Fouls - Highest FAA):")
        for ref in snapshot.refs[:10]:
            games_str = f" ({ref.games} games)" if ref.games else ""
            print(f"  {ref.rank:3}. {ref.name}: {ref.faa:+.2f}{games_str}")

        # Bottom 10 (fewest fouls)
        print("\nBottom 10 (Fewest Fouls - Lowest FAA):")
        for ref in snapshot.refs[-10:]:
            games_str = f" ({ref.games} games)" if ref.games else ""
            print(f"  {ref.rank:3}. {ref.name}: {ref.faa:+.2f}{games_str}")

    else:
        print("ERROR: Failed to scrape referee ratings")


if __name__ == "__main__":
    main()
