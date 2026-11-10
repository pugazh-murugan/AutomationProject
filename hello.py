from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)   # headless=False = you can see the window
    page = browser.new_page()
    page.goto("https://www.linkedin.com/login")
    print("Page title:", page.title())
    time.sleep(5)
    browser.close()