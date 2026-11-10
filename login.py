from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        ".sessions/linkedin",          # cookies are saved in this folder
        headless=False,
        no_viewport=True,
        args=["--start-maximized"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.linkedin.com/login")

    input("Log in by hand in the browser window (OTP/captcha too). "
          "When you can see your LinkedIn feed, come back here and press Enter... ")

    page.goto("https://www.linkedin.com/feed/")
    print("URL:", page.url)
    print("Logged in:", page.locator("#global-nav, nav.global-nav").first.is_visible())
    ctx.close()