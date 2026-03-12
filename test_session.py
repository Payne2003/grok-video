from playwright.sync_api import sync_playwright
import json
import os

SESSION_PATH = r"D:\grok-video-tool\accounts\account_02\session_state.json"

def test_session():

    if not os.path.exists(SESSION_PATH):
        print("❌ Không tìm thấy session")
        return

    with open(SESSION_PATH) as f:
        data = json.load(f)

    cookies = data.get("cookies", [])

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False)

        context = browser.new_context()

        context.add_cookies(cookies)

        page = context.new_page()

        print("Mở Grok imagine...")

        page.goto("https://grok.com/imagine")

        page.wait_for_timeout(5000)

        url = page.url

        if "login" in url or "signin" in url:
            print("❌ Session account_02 KHÔNG hoạt động")
        else:
            print("✅ Session account_02 hoạt động")

        browser.close()

if __name__ == "__main__":
    test_session()
