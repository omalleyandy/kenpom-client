"""Debug script for overtime.ag NCAA basketball scraping."""

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import json

load_dotenv()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()

        # Login
        print("Logging in...")
        page.goto("https://overtime.ag/sports#/", wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.locator('input[placeholder*="Customer"]').first.fill(
            os.getenv("OV_CUSTOMER_ID")
        )
        page.locator('input[type="password"]').first.fill(os.getenv("OV_PASSWORD"))
        page.locator('button:has-text("Login")').first.click()
        page.wait_for_timeout(4000)

        # Navigate directly to College Basketball URL
        print("Navigating to College Basketball...")
        page.goto(
            "https://overtime.ag/sports#/Basketball/College_Basketball",
            wait_until="networkidle",
        )
        page.wait_for_timeout(3000)

        # Click on Basketball to expand if needed
        try:
            bball = page.locator("#img_Basketball")
            if bball.is_visible(timeout=2000):
                bball.click()
                page.wait_for_timeout(1500)
        except Exception:
            pass

        # Scroll down to load all games
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

        # Take screenshot
        page.screenshot(path="data/screenshots/college_basketball_direct.png")
        print("Screenshot saved to data/screenshots/college_basketball_direct.png")

        # Extract game data from DOM
        js_code = """
        () => {
            const games = [];
            const gameLines = document.querySelectorAll('.gameLineInfo');

            gameLines.forEach((container, idx) => {
                try {
                    const team1 = container.querySelector('[ng-bind*="Team1ID"]');
                    const team2 = container.querySelector('[ng-bind*="Team2ID"]');

                    if (!team1 || !team2) return;

                    const spread1Btn = container.querySelector('[id^="S1_"] .ng-binding');
                    const spread2Btn = container.querySelector('[id^="S2_"] .ng-binding');
                    const total1Btn = container.querySelector('[id^="L1_"] .ng-binding');
                    const timeEl = container.querySelector('[ng-bind*="formatGameTime"]');

                    games.push({
                        away: team1.textContent.trim(),
                        home: team2.textContent.trim(),
                        away_spread: spread1Btn ? spread1Btn.textContent.trim() : null,
                        home_spread: spread2Btn ? spread2Btn.textContent.trim() : null,
                        total: total1Btn ? total1Btn.textContent.trim() : null,
                        time: timeEl ? timeEl.textContent.trim() : null
                    });
                } catch(e) {}
            });

            return games;
        }
        """
        games = page.evaluate(js_code)

        print(f"\nFound {len(games)} games:")
        print("=" * 70)
        for g in games:
            print(f"{g['away']} @ {g['home']}")
            if g["away_spread"]:
                print(f"  Spread: {g['away_spread']} / {g['home_spread']}")
            if g["total"]:
                print(f"  Total: {g['total']}")
            print()

        # Save to JSON for analysis
        with open("data/overtime_debug_games.json", "w") as f:
            json.dump(games, f, indent=2)
        print("Games saved to data/overtime_debug_games.json")

        browser.close()


if __name__ == "__main__":
    main()
