import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")
from fetch_medas_districts import URL, settle

TOPIC = "Örgün Eğitim İstatistikleri"

with sync_playwright() as play:
    browser = play.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    page.set_default_timeout(60000)
    page.goto(URL, wait_until="networkidle")
    page.locator("select").first.select_option(label=TOPIC)
    settle(page)
    items = page.locator(".z-listitem")
    n = items.count()
    print("olcum sayisi:", n)
    for i in range(n):
        print(i, " ".join(items.nth(i).inner_text().split()))
    browser.close()
