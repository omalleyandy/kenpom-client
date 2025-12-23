"""Debug script to inspect the officials.php page structure."""
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://kenpom.com/")
    page.wait_for_timeout(2000)

    # Login
    page.fill('input[name="email"]', os.getenv("KENPOM_EMAIL"))
    page.fill('input[name="password"]', os.getenv("KENPOM_PASSWORD"))
    page.click('input[type="submit"]')
    page.wait_for_timeout(3000)

    # Navigate to officials page
    page.goto("https://kenpom.com/officials.php")
    page.wait_for_timeout(3000)

    # Print table headers
    headers = page.eval_on_selector_all("table th", "els => els.map(e => e.textContent)")
    print("Headers:", headers)

    # Print first 5 data rows
    rows = page.evaluate("""
        () => {
            const rows = document.querySelectorAll('table tr');
            return Array.from(rows).slice(0, 8).map(row => {
                const cells = row.querySelectorAll('td, th');
                return Array.from(cells).map(c => c.textContent.trim());
            });
        }
    """)
    print("\nSample rows:")
    for i, row in enumerate(rows):
        print(f"  Row {i}: {row}")

    input("\nPress Enter to close...")
    browser.close()
