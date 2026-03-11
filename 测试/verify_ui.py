"""Playwright script to verify the scene-axis pipeline UI."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    # 1. Visit the project page for our test project
    project_id = "c09af74b-54fd-4e4c-9d67-56ea543c9f9c"
    page.goto(f"http://localhost:3000/zh/projects/{project_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Screenshot the project page
    page.screenshot(path="/tmp/project_page.png", full_page=True)
    print("Screenshot 1: Project page saved to /tmp/project_page.png")

    # 2. Check for the project list page
    page.goto("http://localhost:3000/zh")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    page.screenshot(path="/tmp/home_page.png", full_page=True)
    print("Screenshot 2: Home page saved to /tmp/home_page.png")

    # 3. Go back to project detail and inspect DOM
    page.goto(f"http://localhost:3000/zh/projects/{project_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Check what text/elements are visible
    body_text = page.inner_text("body")
    print(f"\n--- Page body text (first 2000 chars) ---")
    print(body_text[:2000])

    page.screenshot(path="/tmp/project_detail.png", full_page=True)
    print("\nScreenshot 3: Project detail saved to /tmp/project_detail.png")

    browser.close()
