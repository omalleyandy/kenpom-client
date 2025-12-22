"""Explore overtime.ag website structure to understand odds scraping."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Load environment variables
load_dotenv()

OV_CUSTOMER_ID = os.getenv("OV_CUSTOMER_ID")
OV_PASSWORD = os.getenv("OV_PASSWORD")

print(f"OV_CUSTOMER_ID loaded: {bool(OV_CUSTOMER_ID)}")
print(f"OV_PASSWORD loaded: {bool(OV_PASSWORD)}")

if not OV_CUSTOMER_ID or not OV_PASSWORD:
    print("ERROR: Missing OV_CUSTOMER_ID or OV_PASSWORD in .env file")
    sys.exit(1)


def explore_overtime():
    """Explore overtime.ag to understand page structure."""
    with sync_playwright() as p:
        # Launch browser (headed mode for exploration)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to overtime.ag...")
        page.goto("https://overtime.ag/sports#/", wait_until="networkidle")

        # Take initial screenshot
        screenshots_dir = Path("data/screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        screenshot_path = screenshots_dir / "overtime_initial.png"
        page.screenshot(path=screenshot_path)
        print(f"Initial screenshot saved to {screenshot_path}")

        # Check if login is required
        print("\nChecking for login elements...")
        page.wait_for_timeout(2000)

        # Try to find login form elements
        # Common selectors for username/customer ID fields
        username_selectors = [
            'input[name="username"]',
            'input[name="customerid"]',
            'input[name="customerId"]',
            'input[id="username"]',
            'input[id="customerid"]',
            'input[placeholder*="Customer"]',
            'input[type="text"]',
        ]

        username_field = None
        for selector in username_selectors:
            try:
                field = page.locator(selector).first
                if field.is_visible(timeout=1000):
                    username_field = field
                    print(f"Found username field with selector: {selector}")
                    break
            except Exception:
                continue

        if username_field:
            print("Login form found - attempting to authenticate...")

            # Fill in credentials
            assert OV_CUSTOMER_ID is not None  # Validated at startup
            username_field.fill(OV_CUSTOMER_ID)
            page.wait_for_timeout(500)

            # Find password field
            password_field = page.locator('input[type="password"]').first
            assert OV_PASSWORD is not None  # Validated at startup
            password_field.fill(OV_PASSWORD)
            page.wait_for_timeout(500)

            page.screenshot(path=screenshots_dir / "overtime_login_form.png")
            print("Login form filled - screenshot saved")

            # Find and click submit button
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                'input[type="submit"]',
            ]

            for selector in submit_selectors:
                try:
                    submit = page.locator(selector).first
                    if submit.is_visible(timeout=1000):
                        submit.click()
                        print(f"Clicked submit button: {selector}")
                        break
                except Exception:
                    continue

            page.wait_for_timeout(3000)
            page.screenshot(path=screenshots_dir / "overtime_after_login.png")
            print("Login attempted - screenshot saved")
        else:
            print("No login form found - may already be logged in")

        # Look for NCAA Basketball
        print("\nSearching for NCAA Basketball section...")
        page.wait_for_timeout(2000)

        # Try to find basketball/ncaa links
        ncaa_links = page.locator("text=/NCAA|Basketball|NCAAB/i").all()
        print(f"Found {len(ncaa_links)} NCAA/Basketball related elements")

        # Take screenshot of current state
        page.screenshot(path=screenshots_dir / "overtime_main_page.png")

        # Print page title and URL
        print(f"\nPage title: {page.title()}")
        print(f"Current URL: {page.url}")

        # Get all visible text to understand structure
        print("\nVisible text on page (first 500 chars):")
        try:
            body_text = page.inner_text("body")
            # Handle Unicode encoding issues on Windows
            print(body_text[:500].encode("utf-8", errors="ignore").decode("utf-8"))
        except Exception as e:
            print(f"Could not print body text: {e}")

        # Wait for user to inspect before closing
        print("\n\nBrowser will remain open for 30 seconds for manual inspection...")
        page.wait_for_timeout(30000)

        browser.close()


if __name__ == "__main__":
    try:
        explore_overtime()
    except Exception as e:
        print(f"\nERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
