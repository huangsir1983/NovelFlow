"""Verify completed pipeline UI state."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    # Check the completed project
    page.goto("http://localhost:3000/zh/projects/c78ea70c-6b0a-4744-a072-886c51f58f79")
    page.wait_for_load_state("networkidle")
    time.sleep(3)
    page.screenshot(path="/tmp/05_completed_project.png", full_page=True)
    print("Screenshot: 05_completed_project.png")

    # Also check the other project that's still running
    page.goto("http://localhost:3000/zh/projects/c09af74b-54fd-4e4c-9d67-56ea543c9f9c")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    page.screenshot(path="/tmp/06_running_project.png", full_page=True)
    print("Screenshot: 06_running_project.png")

    browser.close()
