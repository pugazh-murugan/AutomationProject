import re
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright

# ---------- settings: change only these ----------
KEYWORD = ".NET Angular Developer"
LOCATION = "Bengaluru, Karnataka, India"
EASY_APPLY_ONLY = True
POSTED_WITHIN = "r604800"      # r86400 = 24 hours, r604800 = 1 week, r2592000 = 1 month
SHOW_FIRST = 5                  # how many jobs to open and print
# --------------------------------------------------

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        ".sessions/linkedin",
        headless=False,
        no_viewport=True,
        args=["--start-maximized"],
    )
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        params = {"keywords": KEYWORD, "location": LOCATION, "f_TPR": POSTED_WITHIN}
        if EASY_APPLY_ONLY:
            params["f_AL"] = "true"
        url = "https://www.linkedin.com/jobs/search/?" + urlencode(params)

        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        # Diagnostics: shows what LinkedIn really searched
        print("Opened:", page.url)
        if "login" in page.url or "authwall" in page.url:
            print("Not logged in. Run login.py again.")
        else:
            # scroll the results list so more cards load
            for _ in range(4):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1000)

            # collect job ids from every link that points to a job
            hrefs = page.eval_on_selector_all(
                "a[href*='/jobs/view/']", "els => els.map(e => e.href)"
            )
            ids = []
            for h in hrefs:
                m = re.search(r"/jobs/view/(\d+)", h)
                if m and m.group(1) not in ids:
                    ids.append(m.group(1))

            print("Jobs found:", len(ids))

            for job_id in ids[:SHOW_FIRST]:
                page.goto(f"https://www.linkedin.com/jobs/view/{job_id}/",
                          wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                title = page.locator("h1").first.inner_text() if page.locator("h1").count() else "?"
                print(job_id, "|", title.strip())
    finally:
        ctx.close()