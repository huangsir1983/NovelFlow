"""Playwright script to upload a novel and watch the import progress UI."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    # Use a fresh project (the one we created via API is already importing)
    # Create a new one via API first
    import urllib.request
    import json as jsonlib
    req = urllib.request.Request(
        "http://localhost:8000/api/projects",
        data=jsonlib.dumps({
            "name": "ui-pipeline-test",
            "description": "test from playwright",
            "import_source": "novel"
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        project = jsonlib.loads(resp.read())
    project_id = project["id"]
    print(f"Created project: {project_id}")

    # Navigate to the project page
    page.goto(f"http://localhost:3000/zh/projects/{project_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Screenshot: initial upload page
    page.screenshot(path="/tmp/01_upload_page.png", full_page=True)
    print("Screenshot: 01_upload_page.png")

    # Upload the test novel file
    file_input = page.locator("input[type='file']")
    file_input.set_input_files("G:/涛项目/claude版/模块一/测试/我和沈词的长子.txt")

    # Wait for the import steps to appear
    time.sleep(3)
    page.screenshot(path="/tmp/02_import_started.png", full_page=True)
    print("Screenshot: 02_import_started.png")

    # Wait and take periodic screenshots
    for i in range(10):
        time.sleep(10)
        page.screenshot(path=f"/tmp/03_progress_{i}.png", full_page=True)
        body_text = page.inner_text("body")
        print(f"Screenshot: 03_progress_{i}.png")
        # Check for key indicators
        if "视觉提示词" in body_text or "error" in body_text.lower() or "知识" in body_text:
            print(f"Detected completion or error at iteration {i}")
            break

    # Final screenshot
    page.screenshot(path="/tmp/04_final.png", full_page=True)
    print("Screenshot: 04_final.png")

    # Print page text
    print("\n--- Final page text ---")
    print(page.inner_text("body")[:3000])

    browser.close()
