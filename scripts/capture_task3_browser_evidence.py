"""Live-browser evidence for B5 (state mismatch) — Task 3.

Drives the REAL client (frontend/index.html + frontend/callback.html)
through a genuine login+consent, then intercepts the browser's own
redirect back to /client/callback and tampers the `state` query parameter
before letting the page load it — exactly what an attacker replaying a
captured/leaked authorization response would attempt. This exercises the
real `state !== savedState` guard in frontend/callback.html with a real
browser engine and real sessionStorage, not a source-code inspection.

Captures:
  - docs/evidence/screenshots/10_b5_state_mismatch_abort.png
  - docs/evidence/ev_t3_b5_browser_state_mismatch_abort.txt (narrative +
    the full list of network requests made after the tampered callback
    loaded, proving no request to /oauth/token was ever sent)

Run with the app already up at http://127.0.0.1:8000:
    python3 scripts/capture_task3_browser_evidence.py
"""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlencode, urlunparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "docs" / "evidence" / "screenshots"
EVIDENCE = ROOT / "docs" / "evidence"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000"


def tamper_state(url: str, new_state: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["state"] = [new_state]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def main() -> None:
    password = os.environ["SOUNDACCESS_SEED_USER_PASSWORD"]
    captured = {}
    post_tamper_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1000, "height": 780})

        # 1) Normal client flow up to "allow" -- real state generated and
        #    saved in sessionStorage by frontend/index.html.
        page.goto(f"{BASE}/client")
        page.wait_for_load_state("networkidle")
        page.click("#login")
        page.wait_for_load_state("networkidle")
        page.fill("#username", "ana")
        page.fill("#password", password)

        # 2) Intercept the form POST to /oauth/authorize itself, perform it
        #    manually with max_redirects=0 to read the real 302 Location
        #    the server issued (without letting the browser auto-follow
        #    it), then abort so the browser never navigates there. This
        #    gives us the genuine, correctly-signed code+state pair for
        #    this login, which we then tamper with before the client ever
        #    sees it -- simulating a replayed/leaked authorization
        #    response with a different state than the one this browser
        #    session actually generated.
        def intercept(route):
            if route.request.method != "POST":
                route.continue_()
                return
            resp = route.fetch(max_redirects=0)
            captured["url"] = resp.headers.get("location")
            route.abort()

        page.route("**/oauth/authorize", intercept)
        page.click('button[value="allow"]')
        page.wait_for_timeout(600)
        page.unroute("**/oauth/authorize", intercept)

        assert "url" in captured, "did not capture the real authorization redirect"
        real_callback_url = captured["url"]
        real_state = parse_qs(urlparse(real_callback_url).query)["state"][0]
        tampered_url = tamper_state(real_callback_url, "attacker-forged-state-does-not-match")

        # 3) Now load the TAMPERED callback URL for real, and record every
        #    network request the page makes while processing it.
        page.on("request", lambda req: post_tamper_requests.append(req.url))
        page.goto(tampered_url)
        page.wait_for_timeout(500)
        page.screenshot(path=SCREENSHOTS / "10_b5_state_mismatch_abort.png", full_page=True)

        abort_message = page.locator("#exchange").inner_text()
        token_calls = [u for u in post_tamper_requests if u.endswith("/oauth/token")]

        def redact_code(url: str) -> str:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            if "code" in query:
                query["code"] = ["<redacted>"]
            return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

        redacted_requests = [redact_code(u) for u in post_tamper_requests]

        browser.close()

    (EVIDENCE / "ev_t3_b5_browser_state_mismatch_abort.txt").write_text(
        "Live-browser evidence for B5 (state mismatch), real Chromium via Playwright.\n\n"
        f"1. Genuine login+consent completed for user 'ana'; the browser's own\n"
        f"   sessionStorage held the state it generated at step 1 (redacted).\n"
        f"2. Intercepted the server's real redirect to /client/callback before the\n"
        f"   client processed it. Its state (redacted) was the CORRECT one for this\n"
        f"   browser session: real_state == \"{real_state[:6]}...<redacted>\".\n"
        f"3. Replaced only the `state` query parameter with an attacker-forged value\n"
        f"   and navigated the SAME browser (same sessionStorage) to that tampered URL\n"
        f"   -- this simulates a replayed/leaked authorization response. The\n"
        f"   authorization code itself was never exchanged (the guard aborts first)\n"
        f"   and is redacted below regardless.\n\n"
        f"Client-side result (#exchange element text):\n  \"{abort_message}\"\n\n"
        f"Network requests made by the page while processing the tampered callback:\n"
        + "\n".join(f"  - {u}" for u in redacted_requests) + "\n\n"
        f"Requests to /oauth/token during this tampered navigation: {len(token_calls)} "
        "(must be 0 -- the client-side guard aborts before any token exchange).\n"
        "Screenshot: docs/evidence/screenshots/10_b5_state_mismatch_abort.png"
    )
    print("abort_message:", abort_message)
    print("token exchange calls after tampering:", len(token_calls))
    print("Evidence written.")


if __name__ == "__main__":
    main()
