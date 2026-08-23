"""Drive the real running application with Playwright and capture screenshots
of the Authorization Code + PKCE flow end to end, as required by the work
plan (browser-based verification, not just source inspection).

Run with the app already up at http://127.0.0.1:8000 and .env loaded:
    python3 scripts/capture_browser_evidence.py
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000"


def main() -> None:
    password = os.environ["SOUNDACCESS_SEED_USER_PASSWORD"]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1000, "height": 780})

        page.goto(f"{BASE}/client")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=OUT / "01_client_home.png")

        page.click("#login")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=OUT / "02_authorize_login_consent.png")

        page.fill("#username", "ana")
        page.fill("#password", password)
        page.screenshot(path=OUT / "03_credentials_filled.png")

        page.click('button[value="allow"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "04_callback_token_exchanged.png", full_page=True)

        page.click("#btn-catalog")
        page.wait_for_timeout(300)
        page.screenshot(path=OUT / "05_api_catalog_200.png", full_page=True)

        page.click("#btn-me")
        page.wait_for_timeout(300)
        page.screenshot(path=OUT / "06_api_me_200.png", full_page=True)

        page.click("#btn-create")
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "07_api_playlist_created_201.png", full_page=True)

        page.click("#btn-read")
        page.wait_for_timeout(300)
        page.screenshot(path=OUT / "08_api_playlist_read_200.png", full_page=True)

        page.goto(f"{BASE}/docs")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=OUT / "09_swagger_ui.png", full_page=True)

        browser.close()
    print("Screenshots written to", OUT)


if __name__ == "__main__":
    main()
