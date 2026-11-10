from playwright.sync_api import sync_playwright

URL = ("https://www.linkedin.com/jobs/search-results/"
       "?keywords=.NET%20Angular%20Developer&f_TPR=r604800&f_AL=true")

CANDIDATES = [
    "a[href*='/jobs/view/']",
    "li[data-occludable-job-id]",
    "[data-job-id]",
    "div[role='listitem']",
    "h1",
    "button:has-text('Easy Apply')",
]

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        ".sessions/linkedin", headless=False, no_viewport=True,
        args=["--start-maximized"],
    )
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        print("URL:", page.url)
        for sel in CANDIDATES:
            print(page.locator(sel).count(), sel)
        page.screenshot(path="debug.png")
    finally:
        ctx.close()