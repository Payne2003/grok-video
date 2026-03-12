from playwright.sync_api import sync_playwright
from auth.session_manager import SessionManager


def run_auth():

    with sync_playwright() as p:

        print("Connecting to Chrome...")

        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")

        context = browser.contexts[0]

        page = context.pages[0]

        page.goto("https://grok.com")

        input("Login xong nhấn ENTER...")

        cookies = context.cookies()

        SessionManager().save(cookies)

        print("Session saved!")


if __name__ == "__main__":
    run_auth()
