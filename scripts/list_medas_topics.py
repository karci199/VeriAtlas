"""List every topic in the MEDAS main dropdown, to find where school/classroom/branch
data would live (separate from the ADNKS-based "Ulusal Eğitim İstatistikleri").

Run:  uv run python scripts/list_medas_topics.py
"""

import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")
from fetch_medas_districts import URL  # noqa: E402


def main() -> None:
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.set_default_timeout(60000)
        page.goto(URL, wait_until="networkidle")
        options = page.locator("select").first.locator("option").all_inner_texts()
        for o in options:
            print(o.strip())
        browser.close()


if __name__ == "__main__":
    main()
